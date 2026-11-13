# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Quiet four-operator FM, live register changes and envelope retriggering."""
import rev_c_fm_live as live
from rev_c_fm_ssg_check import MixerBus, hold, PRIME_BLOCKS


CARRIER_LEVEL = 64
MOD_LEVELS = (96, 64, 40, 24)
MULTIPLES = (1, 2, 3)
CHANGE_BLOCKS = 89  # about one second; the stream keeps running during writes
SLOTS = (0, 4, 8, 12)
MODULATORS = (0, 4, 8)  # register order; logical operator 2/3 order is interleaved

_ALLOWED = {0x28: (0, 1, 2, 0xF0), 0xB0: (0, 7), 0xA4: (0x24,), 0xA0: (0x0E,)}
for _slot in SLOTS:
    for _base, _values in (
        (0x30, (1,) if _slot == 12 else MULTIPLES),
        (0x40, (CARRIER_LEVEL,) if _slot == 12 else (127,) + MOD_LEVELS),
        (0x50, (31,)), (0x60, (0, 12)), (0x70, (0,)),
        (0x80, (15, 0x8F)), (0x90, (0,)),
    ):
        _ALLOWED[_base + _slot] = _values


class TimbreBus(MixerBus):
    # Keep inherited prepare()/write_fm() unchanged for the proven silent preflight.
    def _write_tone(self, register, value):
        if type(register) is not int or type(value) is not int:
            raise ValueError("FM register/data must be integers")
        if register not in _ALLOWED or value not in _ALLOWED[register]:
            raise ValueError("Outside the quiet four-operator diagnostic policy")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        self._write_port(1, value)
        self.wait_ready()

    def keys_off(self):
        for channel in range(3):
            self._write_tone(0x28, channel)

    def configure(self, preset):
        if preset not in ("pure", "serial", "decay"):
            raise ValueError("Unknown FM timbre preset")
        self.keys_off()
        for slot in SLOTS:
            level = CARRIER_LEVEL if slot == 12 else 127 if preset == "pure" else 40
            for base, value in (
                (0x30, 1), (0x40, level), (0x50, 31),
                (0x60, 12 if preset == "decay" else 0), (0x70, 0),
                (0x80, 0x8F if preset == "decay" else 15), (0x90, 0),
            ):
                self._write_tone(base + slot, value)
        self._write_tone(0xB0, 7 if preset == "pure" else 0)
        self._write_tone(0xA4, 0x24)
        self._write_tone(0xA0, 0x0E)

    def modulation(self, level):
        if type(level) is not int or level not in MOD_LEVELS:
            raise ValueError("Unsupported modulator level")
        for slot in MODULATORS:
            self._write_tone(0x40 + slot, level)

    def multiple(self, value):
        if type(value) is not int or value not in MULTIPLES:
            raise ValueError("Unsupported modulator multiple")
        for slot in MODULATORS:
            self._write_tone(0x30 + slot, value)

    def key_on(self):
        self._write_tone(0x28, 0xF0)


def prepare(bus, stream, pcm, audio, silence, preset):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.keys_off()
    bus.ssg("off")
    live._send(audio, silence, 200)
    bus.configure(preset)
    stream.start()
    bus.dac_allow.value(1)
    hold(stream, pcm, audio, PRIME_BLOCKS)
    bus.line_allow.value(1)
    # Start after priming so the attack is heard, including the decaying preset.
    bus.key_on()


def gap(bus, stream, audio, silence):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.keys_off()
    live._send(audio, silence, 1000)


def sequence(bus, stream, pcm, audio, silence):
    print("1 PURE / near-sine reference / about 440 Hz / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, "pure")
    if hold(stream, pcm, audio) < 128:
        raise RuntimeError("No clear reference carrier")
    gap(bus, stream, audio, silence)

    print("2 FOUR OPERATORS / serial FM / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, "serial")
    if hold(stream, pcm, audio) < 128:
        raise RuntimeError("No clear four-operator FM signal")

    print("3 LIVE MODULATION / no key-off between changes")
    for level in MOD_LEVELS:
        print("  MODULATOR TL=%d / 1 second (smaller TL = stronger modulation)" % level)
        bus.modulation(level)
        hold(stream, pcm, audio, CHANGE_BLOCKS)

    print("4 LIVE MULTIPLE / no key-off between changes")
    bus.modulation(40)
    for value in MULTIPLES:
        print("  MODULATOR MULTI=%d / 1 second (carrier stays at 1)" % value)
        bus.multiple(value)
        hold(stream, pcm, audio, CHANGE_BLOCKS)
    gap(bus, stream, audio, silence)

    print("5 ENVELOPE / decaying note, key-off, then retrigger")
    prepare(bus, stream, pcm, audio, silence, "decay")
    for repeat in range(2):
        if repeat:
            bus.key_on()
        print("  DECAY %d/2 / 2 seconds" % (repeat + 1))
        hold(stream, pcm, audio)
        bus.keys_off()
        print("  KEY OFF / 1 second")
        hold(stream, pcm, audio, CHANGE_BLOCKS)

    print("6 SOURCES OFF / DAC and line remain enabled / 2 seconds")
    if hold(stream, pcm, audio) > 64:
        raise RuntimeError("FM envelope did not return to silence")
    bus.line_allow.value(0)
    stream.stop()
    print("TIMBRE: all six sections sent.")


def run():
    live.run(
        bus_factory=TimbreBus, sequence=sequence,
        title="YM2203 Rev C / four-operator FM timbre check v1",
        description="Six comparisons; SSG stays off. Sound starts in about 5 seconds.",
        completion="DONE: report timbre changes, live parameter response, two decays, L/R and distortion."
    )


if __name__ == "__main__":
    run()
