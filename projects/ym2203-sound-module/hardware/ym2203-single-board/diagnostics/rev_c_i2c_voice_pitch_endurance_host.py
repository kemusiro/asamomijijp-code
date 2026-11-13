# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Three-minute changing six-voice score using the unchanged pitch target."""
import time
import rev_c_i2c_voice_pitch_host as pitch


mixer = pitch.mixer
DURATION_MS = 180000
REPORT_MS = 30000
PAUSE_MS = 100


class Session:
    def __init__(self, i2c, remote, pitches):
        self.i2c, self.remote, self.pitches = i2c, remote, pitches
        self.groups = self.commands = self.wraps = self.max_check_ms = self.elapsed_ms = 0
        self.last = 0x7F

    def verify(self):
        pitch.verify(self.i2c, self.remote, self.last, 1, 63, self.pitches)

    def record(self, previous, before):
        if self.remote.ack != (previous + 1) & 255:
            raise RuntimeError("Dynamic pitch ACK sequence mismatch")
        self.commands += 1
        self.wraps += int(self.remote.ack < previous)
        self.max_check_ms = max(self.max_check_ms, time.ticks_diff(time.ticks_ms(), before))

    def group(self):
        # Catch an unexpected expiry before any subsequent command.
        self.verify()
        for voice in range(6):
            note = pitch.MELODY[(self.groups + pitch.INITIAL[voice]) % len(pitch.MELODY)]
            previous, before = self.remote.ack, time.ticks_ms()
            self.last = pitch.select(self.i2c, self.remote, voice, note, 1, 63, self.pitches)
            self.record(previous, before)
        previous, before = self.remote.ack, time.ticks_ms()
        self.remote.command(mixer.KEEP, 1)
        self.last = mixer.KEEP
        self.verify()
        self.record(previous, before)
        self.groups += 1


def endure(i2c, remote, pitches):
    session = Session(i2c, remote, pitches)
    started = time.ticks_ms()
    reports = 0
    while time.ticks_diff(time.ticks_ms(), started) < DURATION_MS:
        session.group()
        time.sleep_ms(PAUSE_MS)
        session.elapsed_ms = time.ticks_diff(time.ticks_ms(), started)
        while reports < 6 and session.elapsed_ms >= (reports + 1) * REPORT_MS:
            reports += 1
            print("DYNAMIC PITCH %d/6 / elapsed_ms=%d groups=%d updates=%d KEEP=%d commands=%d ack=%d wraps=%d max_check_ms=%d" %
                  (reports, session.elapsed_ms, session.groups, session.groups * 6,
                   session.groups, session.commands, remote.ack, session.wraps, session.max_check_ms))
    if session.groups < 9 or session.commands < 256 or session.wraps < 1 or reports != 6:
        raise RuntimeError("Dynamic pitch endurance coverage incomplete")
    session.verify()
    print("DYNAMIC PITCH COMPLETE / elapsed_ms=%d groups=%d updates=%d KEEP=%d commands=%d wraps=%d max_check_ms=%d" %
          (session.elapsed_ms, session.groups, session.groups * 6, session.groups,
           session.commands, session.wraps, session.max_check_ms))
    return session


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=pitch.SIGNATURE, remote_factory=pitch.Remote)
    pitches = bytearray(pitch.INITIAL)
    pitch.verify(i2c, remote, mixer.KEEP, 0, 0, pitches)
    remote.command(mixer.START, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    pitch.verify(i2c, remote, mixer.KEEP, 0, 0, pitches)
    pitch.reset_pitches(i2c, remote, pitches)
    print("PASS: per-voice START, eight KEEP commands and muted initial pitches")
    print("Three-minute changing six-voice score. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    remote.command(0x7F, 1)
    pitch.verify(i2c, remote, 0x7F, 1, 63, pitches)
    print("DYNAMIC PITCH START / 180 seconds / all six voices stay keyed; no intentional gaps")
    session = endure(i2c, remote, pitches)
    remote.command(mixer.STOP, 0)
    pitch.verify(i2c, remote, mixer.STOP, 0, 0, pitches)
    print("STOP acknowledged / 1 second silence")
    time.sleep_ms(1000)
    pitch.reset_pitches(i2c, remote, pitches)
    print("LEASE TEST / original six-voice chord; auto-mute after about 1 second")
    remote.command(0x7F, 1)
    time.sleep_ms(1600)
    pitch.verify(i2c, remote, 0x7F, 0, 0, pitches, expired=1)
    print("PASS: all six voices lease-muted; original pitch indices retained")
    remote.command(mixer.STOP, 0)
    pitch.verify(i2c, remote, mixer.STOP, 0, 0, pitches)
    final_ack = (remote.ack + 1) & 255
    if final_ack != (session.groups * 7 + 59) & 255:
        raise RuntimeError("Dynamic pitch final ACK accounting mismatch")
    print("EXPECTED VOICE PITCH: updates=%d writes=%d cancelled=0 pending=-1 step=2" %
          (session.groups * 6 + 12, session.groups * 12 + 24))
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final_ack)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: three-minute changing six voices, full pitch integrity, ACK wrap and final lease cleanup")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    pitch.six.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for per-voice pitch READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C dynamic six-voice endurance HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
