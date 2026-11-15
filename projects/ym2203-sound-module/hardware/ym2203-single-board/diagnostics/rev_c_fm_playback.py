# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Capture a YM FM waveform, then replay one captured period through the DAC.

This bounded diagnostic does not implement real-time conversion. It requires
the companion bus, capture and DAC diagnostics. Import never enables audio.
"""
import gc
import struct
import time
from machine import Pin
from rev_c_bus_check import I2S_OUTPUT_GPIO, _check_platform, _diagnose, _emergency_stop
from rev_c_fm_capture import Capture, RevCFMBus, analyze, report
from rev_c_dac_check import RATE, BITS, IBUF, FLUSH_MS, _send, _write


TARGET_PEAK = 4096  # same -18 dBFS ceiling as the verified 1 kHz DAC check
ROUNDS = 3
TONE_SECONDS = 2
GAP_MS = 1000


def decode(word):
    if type(word) is not int or not 0 <= word < 8192:
        raise ValueError("FM word must be an unsigned 13-bit integer")
    exponent = word >> 10
    if exponent == 0:
        raise ValueError("YM3014 exponent code zero is invalid")
    # Offset-binary 10-bit mantissa, with exponent bits transmitted directly.
    # Drop the DAC's half-LSB analogue offset so its nominal zero maps to PCM 0.
    return ((word & 1023) - 512) << (exponent - 1)


def _pcm(result):
    if set(result["bit_counts"]) != {24}:
        raise RuntimeError("Replay requires the verified 24-clock FM framing")
    if not 54_000 <= result["sh_hz"] <= 57_000:
        raise RuntimeError("FM sample rate is outside the 4 MHz diagnostic range")
    return [decode(word) for word in result["data"]]


def make_buffers(off1, on, off2):
    quiet1, values, quiet2 = _pcm(off1), _pcm(on), _pcm(off2)
    if not quiet1 or not quiet2 or max(abs(v) for v in quiet1 + quiet2) > 2:
        raise RuntimeError("Decoded key-off data is not near PCM zero")
    if len(values) < 256 or min(values) >= -16 or max(values) <= 16:
        raise RuntimeError("Decoded FM wave does not have both positive and negative signal")
    crossings = []
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if a <= 0 < b:
            crossings.append(i - 1 + (-a) / (b - a))
    if len(crossings) < 2:
        raise RuntimeError("Not enough complete FM periods captured")
    periods = [b - a for a, b in zip(crossings, crossings[1:])]
    period = sum(periods) / len(periods)
    frequency = on["sh_hz"] / period
    if not 400 <= frequency <= 480 or any(abs(p - period) > period * 0.05 for p in periods):
        raise RuntimeError("Decoded FM waveform does not match the intended ~440 Hz tone")
    # Use a complete zero-crossing-to-zero-crossing period, rather than loop a
    # partial 8 ms capture. Integer output length introduces <1% pitch rounding.
    length = round(RATE / frequency)
    start, end = crossings[:2]
    wave = []
    for i in range(length):
        position = start + (end - start) * i / length
        index = int(position)
        fraction = position - index
        wave.append(values[index] * (1 - fraction) + values[index + 1] * fraction)
    dc = sum(wave) / length
    peak = max(abs(v - dc) for v in wave)
    if peak < 16:
        raise RuntimeError("Captured FM wave is too small for this diagnostic")
    wave = [max(-TARGET_PEAK, min(TARGET_PEAK, round((v - dc) * TARGET_PEAK / peak))) for v in wave]
    frames = length * 4
    steady = bytearray(frames * 4)
    fade_in = bytearray(len(steady))
    fade_out = bytearray(len(steady))
    for i in range(frames):
        value = wave[i % length]
        struct.pack_into("<hh", steady, i * 4, value, 0)
        struct.pack_into("<hh", fade_in, i * 4, int(value * i / (frames - 1)), 0)
        struct.pack_into("<hh", fade_out, i * 4, int(value * (frames - 1 - i) / (frames - 1)), 0)
    silence = bytearray(RATE // 100 * 4)  # 10 ms, for the verified DAC _send helper
    repetitions = max(2, round(TONE_SECONDS * RATE / frames))
    info = {"source_hz": frequency, "playback_hz": RATE / length,
            "source_min": min(values), "source_max": max(values),
            "frames_per_chunk": frames, "chunks": repetitions,
            "tone_ms": repetitions * frames * 1000 / RATE}
    return (silence, steady, fade_in, fade_out), info


def run():
    _check_platform()
    print("YM2203 Rev C / captured FM playback v1")
    print("Keep host I2C disconnected. Start both volume controls low.")
    print("First capture silently; then replay captured FM THREE times at ~440 Hz.")
    bus = capture = audio = None
    try:
        bus = RevCFMBus()
        _diagnose(bus)
        bus.prepare()
        capture = Capture()
        capture.open()
        results = []
        for name, key in (("KEY OFF 1", 0), ("KEY ON", 0x10), ("KEY OFF 2", 0)):
            bus.write_fm(0x28, key)
            time.sleep_ms(300)
            result = analyze(capture.read(), keep_frames=True)
            report(name, result)
            results.append(result)
        # Reset the chip before any audio enable. Stop capture DMA before I2S.
        bus.close()
        capture.close()
        capture = None
        buffers, info = make_buffers(*results)
        del results, result
        gc.collect()
        print("PCM: input range=%d..%d source=%.2f Hz playback=%.2f Hz" %
              (info["source_min"], info["source_max"], info["source_hz"], info["playback_hz"]))
        print("Playback peak capped at 4096/32768. YM remains in hardware reset.")
        from machine import I2S
        sd, sck, ws = I2S_OUTPUT_GPIO
        # The stopped capture SM stays claimed; machine.I2S allocates a free SM.
        # The verified capture program (4 words) and I2S (8) fit one PIO block.
        audio = I2S(0, sck=Pin(sck), ws=Pin(ws), sd=Pin(sd), mode=I2S.TX,
                    bits=BITS, format=I2S.STEREO, rate=RATE, ibuf=IBUF)
        silence, steady, fade_in, fade_out = buffers
        print("Clocks run muted. Sound starts in about 5 seconds.")
        _send(audio, silence, 5000)
        bus.arm.value(1)  # RESET_RELEASE deliberately stays zero
        bus.dac_allow.value(1)
        _send(audio, silence, FLUSH_MS)
        for repetition in range(ROUNDS):
            print("FM REPLAY %d / %.2f Hz / about 2 seconds / both L/R" %
                  (repetition + 1, info["playback_hz"]))
            bus.line_allow.value(1)
            try:
                _write(audio, fade_in)
                for unused in range(info["chunks"] - 2):
                    _write(audio, steady)
                _write(audio, fade_out)
                _send(audio, silence, FLUSH_MS)
            finally:
                bus.line_allow.value(0)
            print("MUTE / 1 second")
            _send(audio, silence, GAP_MS)
    except BaseException:
        print("FAIL or interrupted. Save the full log before retrying.")
        raise
    finally:
        try:
            if bus is None:
                _emergency_stop()
            else:
                bus.close()
        finally:
            try:
                if capture is not None:
                    capture.close()
            finally:
                try:
                    if audio is not None:
                        audio.deinit()
                finally:
                    for gpio in I2S_OUTPUT_GPIO:
                        Pin(gpio, Pin.OUT, pull=None, value=0)
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 capture/I2S=stopped")
    print("DONE: captured FM replay sent. Report 3 tones, both L/R, and silent gaps.")


if __name__ == "__main__":
    run()
