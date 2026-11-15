# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Three-minute six-voice chord plus I2C KEEP/status checks; target unchanged."""
import time
import rev_c_i2c_six_host as six


mixer = six.mixer
DURATION_MS = 180000
REPORT_MS = 30000
KEEP_PAUSE_MS = 200


def endure(i2c, remote):
    started = time.ticks_ms()
    commands = wraps = maximum_ms = maximum_cycle_ms = reports = 0
    while True:
        remaining = DURATION_MS - time.ticks_diff(time.ticks_ms(), started)
        if remaining <= 0:
            break
        time.sleep_ms(min(KEEP_PAUSE_MS, remaining))
        previous = remote.ack
        before = time.ticks_ms()
        remote.command(mixer.KEEP, 1)
        maximum_ms = max(maximum_ms, time.ticks_diff(time.ticks_ms(), before))
        six.verify(i2c, remote, mixer.KEEP, 1, 63)
        maximum_cycle_ms = max(maximum_cycle_ms, time.ticks_diff(time.ticks_ms(), before))
        commands += 1
        if remote.ack < previous:
            wraps += 1
        elapsed = time.ticks_diff(time.ticks_ms(), started)
        if reports < 6 and elapsed >= (reports + 1) * REPORT_MS:
            reports += 1
            print("SIX ENDURANCE %d/6 / elapsed_ms=%d KEEP=%d ack=%d wraps=%d max_command_ms=%d max_check_ms=%d" %
                  (reports, elapsed, commands, remote.ack, wraps, maximum_ms, maximum_cycle_ms))
    if commands < 256 or wraps < 1 or reports != 6:
        raise RuntimeError("Six-voice endurance coverage incomplete: KEEP=%d wraps=%d reports=%d" %
                           (commands, wraps, reports))
    print("SIX ENDURANCE COMPLETE / elapsed_ms=%d KEEP=%d wraps=%d max_command_ms=%d max_check_ms=%d" %
          (elapsed, commands, wraps, maximum_ms, maximum_cycle_ms))
    return commands, wraps, maximum_ms, maximum_cycle_ms


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=six.SIGNATURE, remote_factory=six.Remote)
    six.verify(i2c, remote, mixer.KEEP, 0, 0)
    remote.command(mixer.START, 0)
    six.verify(i2c, remote, mixer.START, 0, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: six-voice START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Three-minute FM C4/E4/G4 + SSG C3/E3/G3 chord. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    remote.command(0x7F, 1)
    six.verify(i2c, remote, 0x7F, 1, 63)
    print("SIX ENDURANCE START / 180 seconds / no intentional gaps or mute intervals")
    endure(i2c, remote)
    remote.command(mixer.STOP, 0)
    six.verify(i2c, remote, mixer.STOP, 0, 0)
    print("STOP acknowledged / 1 second silence")
    time.sleep_ms(1000)
    print("LEASE TEST / short six-voice chord; auto-mute after about 1 second")
    remote.command(0x7F, 1)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 6)
    if actual != bytes((remote.ack, 0x7F, 0, 1, 0, 0)):
        raise RuntimeError("Six-voice endurance lease cleanup failed: %r" % actual)
    print("PASS: all six voices lease-muted and chip cleanup completed")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: three-minute six-voice chord, KEEP/status integrity, ACK wrap and lease cleanup")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    six.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for six-voice READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C six-voice endurance HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
