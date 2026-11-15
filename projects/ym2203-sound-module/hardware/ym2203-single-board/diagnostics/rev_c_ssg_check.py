# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Manual SSG A/B/C analogue-path check for the physical Rev C board.

Save the unchanged rev_c_bus_check.py on the Pico first. No automatic sound on
import. FM/PCM5102A remain muted; this test deliberately enables LINE_ALLOW.
"""

import time
from rev_c_bus_check import RevCBus, SSG_MASKS, _check_platform, _diagnose, _emergency_stop


MASTER_CLOCK_HZ = 4_000_000
# Reset prescaler: SSG clock = master / 4; tone = SSG clock / (16 * period).
TONE_PERIOD = 142
TONE_HZ = MASTER_CLOCK_HZ / (64 * TONE_PERIOD)
SSG_LEVEL = 10  # Fixed level, 0..15; keep this first diagnostic below maximum.
TONE_MS = 2000
GAP_MS = 1000
ROUNDS = 2
MIXERS = (0x3E, 0x3D, 0x3B)  # One tone at a time; all noise paths disabled.


class RevCSSGBus(RevCBus):
    def write_ssg(self, register, value):
        if type(register) is not int or not 0 <= register < len(SSG_MASKS):
            raise ValueError("Only SSG registers 0x00..0x0A are used by this test")
        if type(value) is not int or value < 0 or value & ~SSG_MASKS[register]:
            raise ValueError("SSG data exceeds the implemented register bits")
        if register >= 8 and value > SSG_LEVEL:
            raise ValueError("This diagnostic limits fixed SSG volume to 10")
        if register == 7 and value not in (0x3F,) + MIXERS:
            raise ValueError("Enable only one tone and keep all noise disabled")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        self._write_port(1, value)
        self.wait_ready()

    def checked(self, register, value):
        self.write_ssg(register, value)
        actual = self.read_ssg(register)
        if actual != value:
            raise RuntimeError(
                "SSG setup mismatch reg=0x%02X expected=0x%02X actual=0x%02X"
                % (register, value, actual)
            )

    def silence(self):
        # Mute the analogue switch before any register or channel change.
        self.line_allow.value(0)
        for register in (8, 9, 10):
            self.checked(register, 0)
        self.checked(7, 0x3F)

    def tone(self, channel):
        if type(channel) is not int or not 0 <= channel <= 2:
            raise ValueError("SSG channel must be 0, 1 or 2")
        self.silence()
        self.checked(channel * 2, TONE_PERIOD & 255)
        self.checked(channel * 2 + 1, TONE_PERIOD >> 8)
        self.checked(7, MIXERS[channel])
        self.checked(8 + channel, SSG_LEVEL)
        time.sleep_ms(50)
        # This is the only deliberate audio enable, after all readbacks pass.
        self.line_allow.value(1)
        try:
            time.sleep_ms(TONE_MS)
        finally:
            self.line_allow.value(0)
        self.silence()


def run():
    _check_platform()
    print("YM2203 Rev C / SSG A-B-C check v1")
    print("Connect JLINE to AMS-22 LINE IN. Start both volume controls low.")
    print("FM/DAC stay muted. This test WILL produce sound after the bus check.")
    bus = None
    try:
        bus = RevCSSGBus()
        _diagnose(bus)
        print("BUS check passed. SSG tones start in 5 seconds.")
        time.sleep_ms(5000)
        for repetition in range(ROUNDS):
            for channel in range(3):
                print(
                    "SSG %s / round %d of %d / %.2f Hz / 2 seconds"
                    % ("ABC"[channel], repetition + 1, ROUNDS, TONE_HZ)
                )
                bus.tone(channel)
                print("MUTE / 1 second")
                time.sleep_ms(GAP_MS)
    except BaseException:
        print("FAIL or interrupted. Save the full message before retrying.")
        raise
    finally:
        if bus is None:
            _emergency_stop()
        else:
            bus.close()
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0")
    print("DONE: sequence sent. Report whether A, B and C were heard on both L/R.")


if __name__ == "__main__":
    run()
