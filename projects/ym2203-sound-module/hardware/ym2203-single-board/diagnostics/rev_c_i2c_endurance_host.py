# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Three-minute FM/SSG + I2C KEEP endurance using the proven v1.3 target."""
import time
import rev_c_i2c_fm_staged_host as staged


DURATION_MS = 180000
REPORT_MS = 30000
KEEP_PAUSE_MS = 200


def live_remote(i2c):
    mixer = staged.mixer
    if getattr(mixer.shared.Remote, "ack_wait_ms", None) != 10:
        raise RuntimeError("Install v1.3 rev_c_i2c_ssg_host.py and soft reset")
    remote = mixer.shared.preflight(i2c, signature=mixer.SIGNATURE, remote_factory=mixer.Remote)
    print("PASS: initial I2C checks while FM capture STOPPED")
    remote.command(mixer.START, mixer.STOP)
    print("PASS: live capture START acknowledged")
    expected = bytes((remote.ack, mixer.START, mixer.STOP, 0))
    for index in range(8):
        actual = mixer.read_at(i2c, 0x10, 4)
        if actual != expected:
            raise RuntimeError("Endurance START read mismatch: index=%d actual=%r" % (index,actual))
    for unused in range(8):
        remote.command(mixer.KEEP, mixer.STOP)
    print("PASS: 8 stable reads + 8 KEEP commands with FM capture running")
    return remote


def endure(remote):
    # Only the separate HOST prints progress. The Rev C native-audio loop and
    # its no-USB-output/no-explicit-GC rules are unchanged.
    started = time.ticks_ms()
    commands = wraps = maximum_ms = reports = 0
    while True:
        elapsed = time.ticks_diff(time.ticks_ms(), started)
        remaining = DURATION_MS - elapsed
        if remaining <= 0:
            break
        time.sleep_ms(min(KEEP_PAUSE_MS, remaining))
        previous = remote.ack
        before = time.ticks_ms()
        remote.command(staged.mixer.KEEP, staged.mixer.BOTH)
        maximum_ms = max(maximum_ms, time.ticks_diff(time.ticks_ms(), before))
        commands += 1
        if remote.ack < previous:
            wraps += 1
        elapsed = time.ticks_diff(time.ticks_ms(), started)
        if reports < 6 and elapsed >= (reports + 1) * REPORT_MS:
            reports += 1
            print("ENDURANCE %d/6 / elapsed_ms=%d KEEP=%d ack=%d wraps=%d max_command_ms=%d" %
                  (reports, elapsed, commands, remote.ack, wraps, maximum_ms))
    if wraps < 1 or reports != 6:
        raise RuntimeError("Endurance coverage incomplete: KEEP=%d wraps=%d reports=%d" %
                           (commands, wraps, reports))
    print("ENDURANCE COMPLETE / elapsed_ms=%d KEEP=%d wraps=%d max_command_ms=%d" %
          (elapsed, commands, wraps, maximum_ms))
    return commands, wraps, maximum_ms


def check_live(i2c):
    mixer = staged.mixer
    remote = live_remote(i2c)
    print("LIVE ACK: idle gap=%d ms; lease=1000 ms" % remote.ack_wait_ms)
    print("Three-minute continuous FM ~440 Hz + SSG ~220 Hz. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    remote.command(mixer.BOTH, mixer.BOTH)
    print("ENDURANCE START / 180 seconds / no intentional gaps or mute intervals")
    commands, wraps, maximum_ms = endure(remote)
    remote.command(mixer.STOP, mixer.STOP)
    print("STOP acknowledged / 1 second silence")
    time.sleep_ms(1000)
    print("LEASE TEST / one short FM+SSG tone / auto-mute after about 1 second")
    remote.command(mixer.BOTH, mixer.BOTH)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 4)
    if actual != bytes((remote.ack, mixer.BOTH, mixer.STOP, 1)):
        raise RuntimeError("Endurance final lease mute failed: %r" % actual)
    print("PASS: both sources lease-muted without STOP")
    time.sleep_ms(400)
    remote.command(mixer.STOP, mixer.STOP)
    # The target closes I2C after FINISH, so compare this value with its final
    # log rather than trying to read a reply after it has disabled the bus.
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: three-minute live FM/SSG + I2C KEEP, ACK wrap and final lease mute verified")


def check(i2c):
    if getattr(staged.mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for live-control READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    staged.mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C live FM+SSG endurance HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
