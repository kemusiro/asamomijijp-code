# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""FM channels 1/2/3 and six-voice analogue output; uses validated live core."""
import rev_c_fm_live as live
from rev_c_fm_ssg_check import MixerBus, hold, PRIME_BLOCKS


FM_LEVEL = 64  # 12 dB below TL48: leave digital headroom for three carriers
FM_PITCHES = ((0x22, 0x69), (0x23, 0x0A), (0x23, 0x9D))  # C4/E4/G4
BASS_PERIODS = (478, 379, 319)  # C3/E3/G3, approximately 131/165/196 Hz
BASS_LEVEL = 7

_ALLOWED = {0x28: (0, 1, 2, 0x10, 0x11, 0x12)}
for _channel in range(3):
    _ALLOWED[0xB0 + _channel] = (7,)
    _ALLOWED[0xA4 + _channel] = (FM_PITCHES[_channel][0],)
    _ALLOWED[0xA0 + _channel] = (FM_PITCHES[_channel][1],)
    for _slot in (0, 4, 8, 12):
        _offset = _channel + _slot
        for _base, _value in ((0x30, 1), (0x40, FM_LEVEL if _slot == 0 else 127),
                              (0x50, 31), (0x60, 0), (0x70, 0), (0x80, 15), (0x90, 0)):
            _ALLOWED[_base + _offset] = (_value,)


class SixVoiceBus(MixerBus):
    def _write_three(self, register, value):
        if type(register) is not int or type(value) is not int:
            raise ValueError("FM register/data must be integers")
        if register not in _ALLOWED or value not in _ALLOWED[register]:
            raise ValueError("Outside the quiet three-carrier diagnostic policy")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        self._write_port(1, value)
        self.wait_ready()

    def fm_mask(self, channels):
        # Validate all inputs before issuing any key changes.
        if any(type(c) is not int or not 0 <= c <= 2 for c in channels):
            raise ValueError("FM channels must be 0, 1, 2")
        for channel in range(3):
            self._write_three(0x28, channel | (0x10 if channel in channels else 0))

    def configure_three(self):
        self.fm_mask(())
        for channel in range(3):
            for slot in (0, 4, 8, 12):
                for base, value in ((0x30, 1), (0x40, FM_LEVEL if slot == 0 else 127),
                                    (0x50, 31), (0x60, 0), (0x70, 0), (0x80, 15), (0x90, 0)):
                    self._write_three(base + slot + channel, value)
            self._write_three(0xB0 + channel, 7)
            high, low = FM_PITCHES[channel]
            self._write_three(0xA4 + channel, high)
            self._write_three(0xA0 + channel, low)

    def bass(self):
        self.ssg("off")
        for channel, period in enumerate(BASS_PERIODS):
            self.checked(2 * channel, period & 255)
            self.checked(2 * channel + 1, period >> 8)
        self.checked(7, 0x38)
        for channel in range(3):
            self.checked(8 + channel, BASS_LEVEL)


def prepare(bus, stream, pcm, audio, silence, channels, bass=False):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.fm_mask(())
    if bass:
        bus.bass()
    else:
        bus.ssg("off")
    bus.fm_mask(channels)
    live._send(audio, silence, 200)
    stream.start()
    bus.dac_allow.value(1)
    hold(stream, pcm, audio, PRIME_BLOCKS)
    bus.line_allow.value(1)


def gap(bus, stream, audio, silence):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.fm_mask(())
    bus.ssg("off")
    live._send(audio, silence, 1000)


def sequence(bus, stream, pcm, audio, silence):
    # The inherited preflight uses the already-verified TL48 single carrier.
    # Only after that succeeds, configure all three at the quieter TL64.
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.configure_three()
    for channel, name in enumerate(("C4", "E4", "G4")):
        print("%d FM CH%d ONLY / %s / 2 seconds" % (channel + 1, channel + 1, name))
        prepare(bus, stream, pcm, audio, silence, (channel,))
        peak = hold(stream, pcm, audio)
        if peak < 128:
            raise RuntimeError("No clear FM signal on channel %d" % (channel + 1))
        gap(bus, stream, audio, silence)
        print("  FM CH%d digital peak=%d" % (channel + 1, peak))

    print("4 FM CH1+2+3 / C4 E4 G4 chord / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, (0, 1, 2))
    peak = hold(stream, pcm, audio)
    gap(bus, stream, audio, silence)
    print("  THREE FM digital peak=%d" % peak)

    print("5 SIX VOICES / FM high chord + SSG low chord / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, (0, 1, 2), bass=True)
    hold(stream, pcm, audio)
    print("6 DAC MUTE / only SSG low chord should remain / 2 seconds")
    bus.dac_allow.value(0)
    hold(stream, pcm, audio)
    print("7 DAC RESTORE / six voices / 2 seconds")
    bus.dac_allow.value(1)
    hold(stream, pcm, audio)
    print("8 LINE MUTE / all six voices should disappear / 2 seconds")
    bus.line_allow.value(0)
    hold(stream, pcm, audio)
    print("9 LINE RESTORE / six voices / 2 seconds")
    bus.line_allow.value(1)
    hold(stream, pcm, audio)
    gap(bus, stream, audio, silence)

    print("10 ALL SOURCES OFF / DAC and line on / should be silent / 2 seconds")
    prepare(bus, stream, pcm, audio, silence, ())
    if hold(stream, pcm, audio) > 64:
        raise RuntimeError("FM channels did not all return to silence")
    bus.line_allow.value(0)
    stream.stop()
    print("SIX VOICE: all ten sections sent.")


def run():
    live.run(
        bus_factory=SixVoiceBus, sequence=sequence,
        title="YM2203 Rev C / FM three-channel + six-voice check v1",
        description="Ten comparisons. Solo FM is quieter. Sound starts in about 5 seconds.",
        completion="DONE: report FM CH1/2/3, both chords, independent mutes, L/R and distortion."
    )


if __name__ == "__main__":
    run()
