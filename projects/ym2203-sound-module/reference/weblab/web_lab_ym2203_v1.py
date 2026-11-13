# SPDX-License-Identifier: MIT
# Driver for Web Lab's experimental I2C module, not a physical YM2203 I2C interface.
from gc import collect as _collect

# Original demonstration patches: algorithm, multiples, total levels, decay, sustain/release.
_PRESETS = {
    "soft": (4, (1, 1, 1, 1), (40, 40, 20, 24), 10, 0x47),
    "bright": (7, (1, 2, 3, 4), (26, 38, 42, 46), 10, 0x47),
    "bell": (4, (1, 3, 1, 7), (50, 24, 48, 26), 12, 0x87),
}
_MAX_DURATION_MS = 0xFFFFFFFF
_MAX_EVENTS = 131071


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + " is out of range")
    return value


def _frequency(note):
    _integer(note, 0, 127, "MIDI note")
    return 440 * 2 ** ((note - 69) / 12)


class YM2203:
    PRESETS = ("soft", "bright", "bell")

    def __init__(self, i2c, address=0x44):
        self.i2c = i2c
        self.address = _integer(address, 0, 127, "I2C address")
        self._mixer = 0x3F
        self.status()  # Probe the module protocol without starting sound.

    def status(self):
        # Avoid GC inside the current synchronous JS proxy (ADR 0048).
        _collect()
        data = self.i2c.readfrom(self.address, 6)
        if len(data) != 6 or data[0] != 1:
            raise ValueError("Unsupported sound module protocol")
        return {"version": data[0], "queued": data[1] | data[2] << 8 | data[4] << 16 | data[5] << 24,
                "volume": data[3]}

    def reset(self):
        """Silence/reset the chip and discard reservations; amplifier volume is kept."""
        self.i2c.writeto(self.address, b"\x03")
        self._mixer = 0x3F

    def volume(self, percent):
        self.i2c.writeto(self.address, bytes((4, _integer(percent, 0, 100, "Volume"))))

    def write_register(self, register, value):
        _integer(register, 0, 255, "Register")
        _integer(value, 0, 255, "Register value")
        self.i2c.writeto_mem(self.address, register, bytes((value,)))
        if register == 7:
            self._mixer = value

    def _write_pairs(self, pairs):
        packet = bytearray((0,))
        for register, value in pairs:
            packet.extend((register, value))
        self.i2c.writeto(self.address, packet)

    def fm_tone(self, preset="soft", channel=0):
        """Apply a built-in FM patch to channel 0, 1 or 2."""
        _integer(channel, 0, 2, "FM channel")
        if preset not in self.PRESETS:
            raise ValueError("Unknown FM preset")
        algorithm, multiples, levels, decay, sustain_release = _PRESETS[preset]
        pairs = [(0x28, channel)]  # End the previous note before changing the patch.
        for slot, multiple, level in zip((0, 4, 8, 12), multiples, levels):
            offset = channel + slot
            pairs.extend(((0x30 + offset, multiple), (0x40 + offset, level),
                          (0x50 + offset, 31), (0x60 + offset, decay),
                          (0x70 + offset, 2), (0x80 + offset, sustain_release)))
        pairs.append((0xB0 + channel, algorithm))
        self._write_pairs(pairs)

    def _fm_pitch(self, note, channel):
        hz = _frequency(note)
        for block in range(8):
            fnum = round(hz * (1 << 21) / (4_000_000 / 72) / (1 << block))
            if 1 <= fnum <= 2047:
                return ((0xA4 + channel, (block << 3) | (fnum >> 8)),
                        (0xA0 + channel, fnum & 255))
        raise ValueError("MIDI note is outside the FM frequency range")

    def fm_note(self, note, channel=0):
        _integer(channel, 0, 2, "FM channel")
        pitch = self._fm_pitch(note, channel)
        self._write_pairs(((0x28, channel),) + pitch + ((0x28, 0xF0 | channel),))

    def fm_off(self, channel=0):
        self.write_register(0x28, _integer(channel, 0, 2, "FM channel"))

    def _ssg_pitch(self, note, channel):
        period = round(125_000 / _frequency(note))
        if not 1 <= period <= 4095:
            raise ValueError("MIDI note is outside the SSG frequency range")
        return ((channel * 2, period & 255), (channel * 2 + 1, period >> 8))

    def _ssg_enable(self, channel):
        self.write_register(7, (self._mixer | 0x38) & ~(1 << channel))

    def ssg_note(self, note, channel=0, volume=11):
        _integer(channel, 0, 2, "SSG channel")
        _integer(volume, 0, 15, "SSG volume")
        pitch = self._ssg_pitch(note, channel)
        self._ssg_enable(channel)
        self._write_pairs(pitch + ((8 + channel, volume),))

    def ssg_off(self, channel=0):
        self.write_register(8 + _integer(channel, 0, 2, "SSG channel"), 0)

    def reserve(self, notes, source="fm", channel=0, step_ms=300,
                gate_ms=250, tail_ms=300, ssg_volume=11, repeat_ms=None):
        """Reserve MIDI notes (None = rest). Return the playback duration in ms.

        Configure the FM patch first. This method does not reset other channels.
        Call reset() to silence all channels before an isolated comparison.
        Validation completes before any reservation is sent over I2C.
        repeat_ms repeats this bounded pattern for the specified total duration.
        """
        if source not in ("fm", "ssg"):
            raise ValueError("Source must be fm or ssg")
        _integer(channel, 0, 2, "Channel")
        _integer(step_ms, 1, _MAX_DURATION_MS, "Step")
        _integer(gate_ms, 1, step_ms, "Gate")
        _integer(tail_ms, 0, _MAX_DURATION_MS, "Tail")
        _integer(ssg_volume, 0, 15, "SSG volume")
        events = []
        duration = 0
        for index, note in enumerate(notes):
            ms = index * step_ms
            duration = ms + step_ms + tail_ms
            if duration > _MAX_DURATION_MS:
                raise ValueError("Reservation exceeds uint32 milliseconds")
            if note is None:
                # Explicit silence also makes an all-rest sequence playable.
                pairs = ((0x28, channel),) if source == "fm" else ((8 + channel, 0),)
            elif source == "fm":
                pairs = self._fm_pitch(note, channel) + ((0x28, 0xF0 | channel),)
            else:
                pairs = self._ssg_pitch(note, channel) + ((8 + channel, ssg_volume),)
            for register, value in pairs:
                events.append((ms, register, value))
            if note is not None:
                off = (0x28, channel) if source == "fm" else (8 + channel, 0)
                events.append((ms + gate_ms, off[0], off[1]))
            if len(events) > _MAX_EVENTS:
                raise ValueError("Reservation exceeds 131071 events")
        if not events:
            raise ValueError("Reservation requires at least one note or rest")
        loop_ms = duration if repeat_ms is not None else None
        duration = self._reservation_duration(duration, repeat_ms)
        if self.status()["queued"]:
            raise ValueError("Module queue is not empty; call reset() first")
        if source == "ssg":
            self._ssg_enable(channel)
        else:
            self.fm_off(channel)  # Retrigger the first note even after immediate playback.
        self._reserve_events(events, duration, loop_ms)
        return duration

    def _reservation_duration(self, period_ms, repeat_ms):
        if repeat_ms is None:
            return period_ms
        if period_ms < 100:
            raise ValueError("Loop period must be at least 100 ms")
        return _integer(repeat_ms, period_ms, _MAX_DURATION_MS, "Repeat duration")

    def _reserve_events(self, events, duration, loop_ms=None):
        # uint16 packets remain byte-compatible for ordinary short samples.
        wide = duration > 65535 or loop_ms is not None
        batch = 42 if wide else 63
        try:
            for start in range(0, len(events), batch):
                # Temporary until the WASM buffer bridge can safely yield during
                # GC. Collect in Python, outside its synchronous JS callbacks.
                if start % (batch * 16) == 0:
                    _collect()
                packet = bytearray((5 if wide else 1,))
                for ms, register, value in events[start:start + batch]:
                    packet.extend((ms & 255, (ms >> 8) & 255))
                    if wide:
                        packet.extend(((ms >> 16) & 255, ms >> 24))
                    packet.extend((register, value))
                self.i2c.writeto(self.address, packet)
            packet = bytearray((6 if wide else 2, duration & 255, (duration >> 8) & 255))
            if wide:
                packet.extend(((duration >> 16) & 255, duration >> 24))
            if loop_ms is not None:
                packet.extend((loop_ms & 255, (loop_ms >> 8) & 255,
                               (loop_ms >> 16) & 255, loop_ms >> 24))
            self.i2c.writeto(self.address, packet)
        except Exception:
            # A failed transfer may have committed earlier batches. Do not leave
            # a partial queue available for a later accidental play.
            try:
                self.reset()
            except Exception:
                pass
            raise
