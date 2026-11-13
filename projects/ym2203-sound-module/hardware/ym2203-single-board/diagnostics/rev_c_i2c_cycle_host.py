# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Ten cycles of fixed-source/mute changes using the proven v1.3 target."""
import time
import rev_c_i2c_endurance_host as endurance


ROUNDS = 10
# Restore is BOTH again: the internal source mask stays unchanged during mutes.
SECTIONS = ((1, "FM ONLY / high ~440 Hz"),
            (2, "SSG ONLY / low ~220 Hz"),
            (3, "FM + SSG"),
            (4, "DAC MUTE / only SSG remains"),
            (3, "DAC RESTORE / both"),
            (5, "LINE MUTE / both disappear"),
            (3, "LINE RESTORE / both"),
            (0, "STOP / both sources off"))


class Session:
    def __init__(self, i2c, remote):
        self.i2c, self.remote = i2c, remote
        self.mode = 0
        self.last_opcode = endurance.staged.mixer.KEEP  # live_remote's final command
        self.commands = self.wraps = self.maximum_ms = 0

    def verify(self):
        actual = endurance.staged.mixer.read_at(self.i2c, 0x10, 4)
        expected = bytes((self.remote.ack, self.last_opcode, self.mode, 0))
        if actual != expected:
            raise RuntimeError("Cycle state changed unexpectedly: expected=%r actual=%r" % (expected,actual))

    def record(self, previous, maximum):
        # A single mode command advances by 1. The inherited two-second hold
        # sends <=10 KEEP commands (200ms pauses + 40ms ACK waits), hence no
        # unobserved full 256-command wrap can occur between these samples.
        count = (self.remote.ack - previous) & 255
        if not 1 <= count <= maximum:
            raise RuntimeError("Cycle ACK accounting failed: previous=%d current=%d" %
                               (previous, self.remote.ack))
        self.commands += count
        if self.remote.ack < previous:
            self.wraps += 1

    def section(self, mode):
        # Check the previous state before a new mode command could clear a
        # lease-expired flag. Do not silently restart after an unintended mute.
        self.verify()
        previous = self.remote.ack
        before = time.ticks_ms()
        self.remote.command(mode, mode)
        self.maximum_ms = max(self.maximum_ms, time.ticks_diff(time.ticks_ms(), before))
        self.record(previous, 1)
        self.mode = self.last_opcode = mode
        if mode:
            previous = self.remote.ack
            self.remote.hold(mode)
            self.record(previous, 10)
            self.last_opcode = endurance.staged.mixer.KEEP
        else:
            time.sleep_ms(2000)
        self.verify()


def cycles(i2c, remote):
    session = Session(i2c, remote)
    started = time.ticks_ms()
    for round_index in range(ROUNDS):
        for section_index, (mode, label) in enumerate(SECTIONS):
            print("CYCLE %d/%d SECTION %d/8 / %s / about 2 seconds" %
                  (round_index + 1, ROUNDS, section_index + 1, label))
            session.section(mode)
        print("CYCLE %d/%d PASS / elapsed_ms=%d commands=%d ack=%d wraps=%d max_mode_command_ms=%d" %
              (round_index + 1, ROUNDS, time.ticks_diff(time.ticks_ms(), started),
               session.commands, remote.ack, session.wraps, session.maximum_ms))
    if session.wraps < 1:
        raise RuntimeError("Cycle test incomplete: no ACK counter wrap observed")
    print("CYCLES COMPLETE / rounds=%d commands=%d wraps=%d max_mode_command_ms=%d" %
          (ROUNDS, session.commands, session.wraps, session.maximum_ms))
    return session


def check_live(i2c):
    mixer = endurance.staged.mixer
    remote = endurance.live_remote(i2c)
    print("LIVE ACK: idle gap=%d ms; lease=1000 ms" % remote.ack_wait_ms)
    print("Ten cycles of eight FM/SSG/mute sections. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    cycles(i2c, remote)
    # The last cycle ended with an acknowledged STOP and a two-second gap.
    print("LEASE TEST / one short FM+SSG tone / auto-mute after about 1 second")
    remote.command(mixer.BOTH, mixer.BOTH)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 4)
    if actual != bytes((remote.ack, mixer.BOTH, mixer.STOP, 1)):
        raise RuntimeError("Cycle final lease mute failed: %r" % actual)
    print("PASS: both sources lease-muted without STOP")
    time.sleep_ms(400)
    remote.command(mixer.STOP, mixer.STOP)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: ten FM/SSG/mute cycles, state readbacks, ACK wrap and final lease mute verified")


def check(i2c):
    if getattr(endurance.staged.mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    endurance.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for live-control READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    endurance.staged.mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C live FM+SSG mode-cycle HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
