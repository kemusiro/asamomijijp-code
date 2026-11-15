# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Ten cycles of FM/SSG chords, six voices, independent mutes and STOP."""
import time
import rev_c_i2c_six_host as six


mixer = six.mixer
ROUNDS = 10
SECTIONS = ((0x47, 1, 7, "FM CHORD / high C4 E4 G4"),
            (0x78, 1, 56, "SSG CHORD / low C3 E3 G3"),
            (0x7F, 1, 63, "SIX VOICES / both chords"),
            (4, 4, 63, "DAC MUTE / only SSG chord"),
            (3, 1, 63, "DAC RESTORE / six voices"),
            (5, 5, 63, "LINE MUTE / all disappear"),
            (3, 1, 63, "LINE RESTORE / six voices"),
            (0, 0, 0, "STOP / all sources off"))


class Session:
    def __init__(self, i2c, remote):
        self.i2c, self.remote = i2c, remote
        self.last = mixer.KEEP
        self.mode = self.mask = 0
        self.commands = self.wraps = self.maximum_ms = 0

    def verify(self):
        six.verify(self.i2c, self.remote, self.last, self.mode, self.mask)

    def record(self, previous, maximum):
        count = (self.remote.ack - previous) & 255
        if not 1 <= count <= maximum:
            raise RuntimeError("Six-cycle ACK count mismatch: old=%d new=%d" % (previous, self.remote.ack))
        self.commands += count
        if self.remote.ack < previous:
            self.wraps += 1

    def section(self, command, mode, mask):
        # Inspect the prior state before STOP or a mask could clear an error.
        self.verify()
        previous = self.remote.ack
        before = time.ticks_ms()
        self.remote.command(command, mode)
        self.maximum_ms = max(self.maximum_ms, time.ticks_diff(time.ticks_ms(), before))
        self.record(previous, 1)
        self.last, self.mode, self.mask = command, mode, mask
        self.verify()
        if mode:
            previous = self.remote.ack
            self.remote.hold(mode)
            # <=10 KEEP operations per two-second hold with 200ms pauses;
            # no unobserved full ACK wrap can be hidden by this modulo delta.
            self.record(previous, 10)
            self.last = mixer.KEEP
        else:
            time.sleep_ms(2000)
        self.verify()


def cycles(i2c, remote):
    session = Session(i2c, remote)
    started = time.ticks_ms()
    for index in range(ROUNDS):
        for section_index, (command, mode, mask, label) in enumerate(SECTIONS):
            print("SIX CYCLE %d/%d SECTION %d/8 / %s / about 2 seconds" %
                  (index + 1, ROUNDS, section_index + 1, label))
            session.section(command, mode, mask)
        print("SIX CYCLE %d/%d PASS / elapsed_ms=%d commands=%d ack=%d wraps=%d max_command_ms=%d" %
              (index + 1, ROUNDS, time.ticks_diff(time.ticks_ms(), started), session.commands,
               remote.ack, session.wraps, session.maximum_ms))
    if session.commands < 256 or session.wraps < 1:
        raise RuntimeError("Six-cycle ACK-wrap coverage incomplete")
    print("SIX CYCLES COMPLETE / rounds=%d commands=%d wraps=%d max_command_ms=%d" %
          (ROUNDS, session.commands, session.wraps, session.maximum_ms))
    return session


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=six.SIGNATURE, remote_factory=six.Remote)
    six.verify(i2c, remote, mixer.KEEP, 0, 0)
    remote.command(mixer.START, 0)
    six.verify(i2c, remote, mixer.START, 0, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: six-voice START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Ten cycles of eight source/mute sections. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    cycles(i2c, remote)
    print("LEASE TEST / short six-voice chord; auto-mute after about 1 second")
    remote.command(0x7F, 1)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 6)
    if actual != bytes((remote.ack, 0x7F, 0, 1, 0, 0)):
        raise RuntimeError("Six-cycle final lease cleanup failed: %r" % actual)
    print("PASS: all six voices lease-muted and chip cleanup completed")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: ten six-voice/mute cycles, mask integrity, ACK wrap and final lease cleanup")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    six.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for six-voice READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C six-voice mode-cycle HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
