# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Manual PCM5102A/line-path diagnostic; YM2203 stays in hardware reset.

Requires unchanged rev_c_bus_check.py and official Pico 2 MicroPython.
No GPIO activity or sound on import. This does not decode YM FM data.
"""

import math
import struct
from machine import Pin
from rev_c_bus_check import RevCBus, I2S_OUTPUT_GPIO, _check_platform, _emergency_stop


RATE = 48_000
BITS = 16
FRAME_BYTES = 4  # signed little-endian int16 L, int16 R
CHUNK_MS = 10
FRAMES = RATE * CHUNK_MS // 1000
IBUF = 4096
TONE_HZ = 1000
PEAK = 4096  # -18.06 dBFS peak; no full-scale test signal.
TONE_MS = 2000
MUTE_MS = 1000
FLUSH_MS = 100  # > (IBUF + DMA/FIFO) / (RATE * FRAME_BYTES)


def _buffers():
    silence = bytearray(FRAMES * FRAME_BYTES)
    steady = bytearray(len(silence))
    fade_in = bytearray(len(silence))
    fade_out = bytearray(len(silence))
    # Build one exactly symmetric period to avoid floating-point DC/phase drift.
    half = [int(PEAK * math.sin(2 * math.pi * frame / 48)) for frame in range(24)]
    cycle = half + [-sample for sample in half]
    for frame in range(FRAMES):
        sample = cycle[frame % 48]
        # Rev C uses only DAC OUTL, then duplicates the analogue mono to L/R.
        # OUTR is unconnected: deliberately send digital zero to that channel.
        struct.pack_into("<hh", steady, frame * FRAME_BYTES, sample, 0)
        struct.pack_into(
            "<hh", fade_in, frame * FRAME_BYTES, int(sample * frame / (FRAMES - 1)), 0
        )
        struct.pack_into(
            "<hh", fade_out, frame * FRAME_BYTES,
            int(sample * (FRAMES - 1 - frame) / (FRAMES - 1)), 0
        )
    return silence, steady, fade_in, fade_out


def _write(audio, data):
    # Blocking mode must accept the complete buffer. Do not ignore a short write.
    written = audio.write(data)
    if written != len(data):
        raise RuntimeError("Short I2S write: %r of %d bytes" % (written, len(data)))


def _send(audio, data, milliseconds):
    if milliseconds % CHUNK_MS:
        raise ValueError("Duration must be a multiple of CHUNK_MS")
    for unused in range(milliseconds // CHUNK_MS):
        _write(audio, data)


def _tone(audio, buffers):
    silence, steady, fade_in, fade_out = buffers
    _write(audio, fade_in)
    _send(audio, steady, TONE_MS - 2 * CHUNK_MS)
    _write(audio, fade_out)
    # write() queues data; keep the clocks running until the last sample drains.
    _send(audio, silence, FLUSH_MS)


def run():
    _check_platform()
    print("YM2203 Rev C / PCM5102A DAC check v1")
    print("External 5V on; host I2C disconnected. Start both volume controls low.")
    print("YM stays in reset. Expect THREE 1 kHz tones, with two mute tests.")
    bus = None
    audio = None
    try:
        bus = RevCBus()
        # Deliberately do not call bus.start(): RESET_RELEASE must remain zero.
        # Import after safe GPIO setup, so missing I2S also leaves the board muted.
        try:
            from machine import I2S
        except ImportError:
            raise RuntimeError("machine.I2S unavailable; report MicroPython version")
        buffers = _buffers()
        silence, steady, unused_in, unused_out = buffers
        sd, sck, ws = I2S_OUTPUT_GPIO  # approved GP10/11/12, unchanged
        audio = I2S(
            0, sck=Pin(sck), ws=Pin(ws), sd=Pin(sd), mode=I2S.TX,
            bits=BITS, format=I2S.STEREO, rate=RATE, ibuf=IBUF
        )
        print("I2S: DATA=GP10 BCLK=GP11 LRCK=GP12; 48 kHz / 16-bit stereo")
        print("Clocks run while muted. Sound starts in about 5 seconds.")
        _send(audio, silence, 5000)
        # ARM enables the DAC/line gates, but RESET_RELEASE remains zero.
        # CS/WR/RD stay high and data GPIOs stay inputs throughout this test.
        bus.arm.value(1)
        bus.dac_allow.value(1)
        _send(audio, silence, FLUSH_MS)
        bus.line_allow.value(1)
        print("TONE 1 / 1000 Hz / 2 seconds / both headphone channels")
        _tone(audio, buffers)

        print("DAC MUTE / 1 second / should be silent")
        bus.dac_allow.value(0)
        _send(audio, steady, MUTE_MS)
        _send(audio, silence, FLUSH_MS)
        bus.dac_allow.value(1)
        _send(audio, silence, FLUSH_MS)
        print("TONE 2 / 1000 Hz / 2 seconds")
        _tone(audio, buffers)

        print("LINE MUTE / 1 second / should be silent")
        bus.line_allow.value(0)
        _send(audio, steady, MUTE_MS)
        _send(audio, silence, FLUSH_MS)
        bus.line_allow.value(1)
        print("TONE 3 / 1000 Hz / 2 seconds")
        _tone(audio, buffers)
    except BaseException:
        print("FAIL or interrupted. Save the full message before retrying.")
        raise
    finally:
        # Mute/reset BEFORE stopping clocks, including on Ctrl+C/write errors.
        try:
            if bus is None:
                _emergency_stop()
            else:
                bus.close()
        finally:
            try:
                if audio is not None:
                    audio.deinit()
            finally:
                for gpio in I2S_OUTPUT_GPIO:
                    Pin(gpio, Pin.OUT, pull=None, value=0)
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 I2S=stopped")
    print("DONE: samples sent; report 3 tones, both L/R, and both mute intervals.")


if __name__ == "__main__":
    run()
