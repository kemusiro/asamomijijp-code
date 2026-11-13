# SPDX-License-Identifier: MIT
# Streaming player for Web Lab YM2203 event files; no music data is embedded.
from gc import collect
from os import stat
from web_lab_ym2203_v1 import _integer, _MAX_EVENTS, _MAX_DURATION_MS


def _u32(data, offset=0):
    return (data[offset] | data[offset + 1] << 8 |
            data[offset + 2] << 16 | data[offset + 3] << 24)


def _bytes32(value):
    return bytes((value & 255, value >> 8 & 255, value >> 16 & 255, value >> 24))


class YM2203BinPlayer:
    """WYM1: 16-byte header followed by ordered <uint32 ms, uint8 reg, uint8 value>."""
    def __init__(self, sound):
        self.sound = sound

    def _validate(self, data, size, event_count=None, period_ms=None):
        if event_count is None:
            header = data.read(16)
            if len(header) != 16 or header[:4] != b"WYM1":
                raise ValueError("Expected WYM1 header")
            event_count, period_ms = _u32(header, 4), _u32(header, 8)
            if _u32(header, 12) != 4000000:
                raise ValueError("Only one 4 MHz YM2203 is supported")
            offset = 16
        else:
            offset = 0
        _integer(event_count, 1, _MAX_EVENTS, "Event count")
        _integer(period_ms, 1, _MAX_DURATION_MS, "Period")
        if size != offset + event_count * 6:
            raise ValueError("Event file length mismatch")
        previous = 0
        for start in range(0, event_count, 42):
            if start % (42 * 16) == 0:
                collect()
            chunk = data.read(min(42, event_count - start) * 6)
            if len(chunk) != min(42, event_count - start) * 6:
                raise ValueError("Truncated event data")
            for at in range(0, len(chunk), 6):
                ms = _u32(chunk, at)
                if not previous <= ms <= period_ms:
                    raise ValueError("Event times must be ordered and within period")
                previous = ms
        data.seek(offset)
        return {"event_count": event_count, "period_ms": period_ms,
                "clock_hz": 4000000, "header_bytes": offset}

    def inspect(self, path):
        """Validate the whole file without changing sound or queue state."""
        with open(path, "rb") as data:
            return self._validate(data, stat(path)[6])

    def play(self, path, repeat_ms=None, volume=20):
        """Validate, reset, upload in 252-byte chunks, then start the reservation."""
        return self._play(path, repeat_ms, volume)

    def play_raw(self, path, event_count, period_ms, repeat_ms=None, volume=20):
        """Explicit compatibility for old headerless six-byte event files."""
        _integer(event_count, 1, _MAX_EVENTS, "Event count")
        _integer(period_ms, 1, _MAX_DURATION_MS, "Period")
        return self._play(path, repeat_ms, volume, event_count, period_ms)

    def _play(self, path, repeat_ms, volume, event_count=None, period_ms=None):
        _integer(volume, 0, 100, "Volume")
        with open(path, "rb") as data:
            info = self._validate(data, stat(path)[6], event_count, period_ms)
            period = info["period_ms"]
            duration = self.sound._reservation_duration(period, repeat_ms)
            # Validation precedes all I2C mutations, including reset and gain.
            try:
                self.sound.reset()
                self.sound.volume(volume)
                for start in range(0, info["event_count"], 42):
                    if start % (42 * 16) == 0:
                        collect()  # Outside the current synchronous WASM/JS bridge.
                    expected = min(42, info["event_count"] - start) * 6
                    chunk = data.read(expected)
                    if len(chunk) != expected:
                        raise ValueError("Event file changed during upload")
                    self.sound.i2c.writeto(self.sound.address, b"\x05" + chunk)
                if self.sound.status()["queued"] != info["event_count"]:
                    raise ValueError("Unexpected sound module queue count")
                packet = b"\x06" + _bytes32(duration)
                if repeat_ms is not None:
                    packet += _bytes32(period)
                self.sound.i2c.writeto(self.sound.address, packet)
            except BaseException:
                try:
                    self.sound.reset()
                except Exception:
                    pass
                raise
        return duration

    def stop(self):
        self.sound.reset()
