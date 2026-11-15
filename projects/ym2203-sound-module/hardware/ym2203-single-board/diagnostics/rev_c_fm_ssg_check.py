# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""FM/SSG analogue mixer and independent-mute diagnostic, using live FM.

Reuses the validated live converter, receiver, memory handling and cleanup.
SSG register changes happen while the line is muted and reception is stopped.
"""
from rev_c_bus_check import SSG_MASKS
import rev_c_fm_live as live


HOLD_BLOCKS = 178  # 2.0025 seconds
PRIME_BLOCKS = 12  # 135 ms > the I2S queue latency
SINGLE_PERIOD = 284  # 62500 / 284 = 220.07 Hz
CHORD_PERIODS = (239, 190, 159)  # approximately C4/E4/G4
SINGLE_LEVEL = 10  # no higher than the previous SSG-only diagnostic
CHORD_LEVEL = 7


class MixerBus(live.LiveBus):
    def write_ssg(self, register, value):
        if type(register) is not int or register not in (0, 1, 2, 3, 4, 5, 7, 8, 9, 10):
            raise ValueError("Only tone periods, mixer and fixed SSG levels are used")
        if type(value) is not int or value < 0 or value & ~SSG_MASKS[register]:
            raise ValueError("SSG value exceeds implemented register bits")
        if register == 7 and value not in (0x3F, 0x3E, 0x38):
            raise ValueError("Keep SSG noise disabled")
        if register >= 8 and value not in (0, CHORD_LEVEL, SINGLE_LEVEL):
            raise ValueError("Only diagnostic fixed levels 0, 7 and 10 are allowed")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        self._write_port(1, value)
        self.wait_ready()

    def checked(self, register, value):
        self.write_ssg(register, value)
        if self.read_ssg(register) != value:
            raise RuntimeError("Mixer diagnostic SSG readback mismatch reg=0x%02X" % register)

    def ssg(self, mode):
        if mode not in ("off", "single", "chord"):
            raise ValueError("SSG mode must be off, single or chord")
        for register in (8, 9, 10):
            self.checked(register, 0)
        self.checked(7, 0x3F)
        if mode == "off":
            return
        periods = (SINGLE_PERIOD,) if mode == "single" else CHORD_PERIODS
        for channel, period in enumerate(periods):
            self.checked(channel * 2, period & 255)
            self.checked(channel * 2 + 1, period >> 8)
        self.checked(7, 0x3E if mode == "single" else 0x38)
        level = SINGLE_LEVEL if mode == "single" else CHORD_LEVEL
        for channel in range(len(periods)):
            self.checked(8 + channel, level)


def hold(stream, pcm, audio, blocks=HOLD_BLOCKS):
    peak = 0
    for unused in range(blocks):
        peak = max(peak, live.step(stream, pcm, audio))
    return peak


def prepare(bus, stream, pcm, audio, silence, fm, ssg):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.write_fm(0x28, 0)
    bus.ssg(ssg)
    # The inherited prepare() leaves the FM pitch at the verified ~440 Hz.
    if fm:
        bus.write_fm(0x28, 0x10)
    # Flush old PCM before opening the line. No SSG writes in the live hot loop.
    live._send(audio, silence, 200)
    stream.start()
    bus.dac_allow.value(1)
    hold(stream, pcm, audio, PRIME_BLOCKS)
    bus.line_allow.value(1)


def gap(bus, stream, audio, silence):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.write_fm(0x28, 0)
    bus.ssg("off")
    live._send(audio, silence, 1000)


def sequence(bus, stream, pcm, audio, silence):
    print("1 FM ONLY / about 440 Hz / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, True, "off")
    hold(stream, pcm, audio)
    gap(bus, stream, audio, silence)

    print("2 SSG A ONLY / about 220 Hz / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, False, "single")
    hold(stream, pcm, audio)
    gap(bus, stream, audio, silence)

    print("3 FM + SSG A / high + low / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, True, "single")
    hold(stream, pcm, audio)
    print("4 DAC MUTE / SSG A should remain / 2 seconds")
    bus.dac_allow.value(0)
    hold(stream, pcm, audio)
    print("5 DAC RESTORE / FM + SSG A / 2 seconds")
    bus.dac_allow.value(1)
    hold(stream, pcm, audio)
    print("6 LINE MUTE / both should disappear / 2 seconds")
    bus.line_allow.value(0)
    hold(stream, pcm, audio)
    print("7 LINE RESTORE / FM + SSG A / 2 seconds")
    bus.line_allow.value(1)
    hold(stream, pcm, audio)
    gap(bus, stream, audio, silence)

    print("8 FM + SSG A/B/C / four voices / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, True, "chord")
    hold(stream, pcm, audio)
    gap(bus, stream, audio, silence)

    print("9 SOURCES OFF / line and DAC enabled / should be silent / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, False, "off")
    peak = hold(stream, pcm, audio)
    if peak > 64:
        raise RuntimeError("FM did not return to silence in mixer diagnostic")
    bus.line_allow.value(0)
    stream.stop()
    print("MIXER: sequence complete; compare all nine sections and both L/R.")


def run():
    live.run(
        bus_factory=MixerBus, sequence=sequence,
        title="YM2203 Rev C / live FM + SSG mixer check v1",
        description="Nine FM/SSG/mute comparisons. Sound starts in about 5 seconds.",
        completion="DONE: report sections 1..9 on L/R, mute independence, balance and distortion."
    )


if __name__ == "__main__":
    run()
