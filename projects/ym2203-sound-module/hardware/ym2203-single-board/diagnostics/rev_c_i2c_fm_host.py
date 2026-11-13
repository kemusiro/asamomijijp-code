# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Hardware-I2C controller for continuous live FM/SSG mixer diagnostics."""
import time
import rev_c_i2c_ssg_host as shared
from rev_c_i2c_host_check import checked_write, read_at


SIGNATURE = b"RCMIX02!"
STOP, FM, SSG, BOTH, DAC_MUTE, LINE_MUTE, KEEP, FINISH = range(8)
START = 8


class Remote(shared.Remote):
    max_opcode = START
    max_mode = LINE_MUTE
    keep_opcode = KEEP
    # The target samples I2C once per 11.25 ms audio block and commits commands
    # only while the slave FSM is idle. A 10 ms read-poll gap can hide every idle
    # sample. Leave >3 blocks idle after writes and between status polls. This
    # is cooperative-diagnostic pacing, not a requirement for an IRQ-based API.
    ack_wait_ms = 40


def check(i2c):
    if getattr(shared.Remote, "ack_wait_ms", None) != 10:
        raise RuntimeError("Install updated rev_c_i2c_ssg_host.py and soft reset")
    print("LIVE ACK: idle gap=%d ms; lease and acknowledgement timeouts remain 1000 ms" % Remote.ack_wait_ms)
    remote = shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    print("PASS: initial I2C checks while FM capture STOPPED")
    print("START: request continuous FM capture")
    remote.command(START, STOP)
    print("PASS: live capture START acknowledged")
    expected = bytes((remote.ack, START, STOP, 0))
    for index in range(8):
        status = read_at(i2c, 0x10, 4)
        if status != expected:
            raise RuntimeError("I2C failed after live START: index=%d actual=%r" % (index,status))
    for unused in range(8):
        remote.command(KEEP, STOP)
    print("PASS: 8 stable reads + 8 KEEP commands with FM capture running")
    print("Nine comparisons. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    for mode, label in ((FM, "1 FM ONLY / high ~440 Hz"),
                        (SSG, "2 SSG ONLY / low ~220 Hz")):
        print(label + " / 2 seconds")
        remote.command(mode, mode)
        remote.hold(mode)
        remote.command(STOP, STOP)
        print("STOP acknowledged / 1 second")
        time.sleep_ms(1000)
    for mode, label in ((BOTH, "3 FM + SSG / high + low"),
                        (DAC_MUTE, "4 DAC MUTE / only low SSG remains"),
                        (BOTH, "5 DAC RESTORE / high + low"),
                        (LINE_MUTE, "6 LINE MUTE / both should disappear"),
                        (BOTH, "7 LINE RESTORE / high + low")):
        print(label + " / 2 seconds")
        remote.command(mode, mode)
        remote.hold(mode)
    print("8 STOP / both sources and output gates off / 2 seconds")
    remote.command(STOP, STOP)
    time.sleep_ms(2000)
    print("9 LEASE / FM + SSG / no keepalive; both mute after about 1 second")
    remote.command(BOTH, BOTH)
    time.sleep_ms(1600)
    status = read_at(i2c, 0x10, 4)
    if status != bytes((remote.ack, BOTH, STOP, 1)):
        raise RuntimeError("Live FM/SSG lease mute failed: %r" % status)
    print("PASS: both sources lease-muted without a STOP command")
    time.sleep_ms(400)
    remote.command(STOP, STOP)
    checked_write(i2c, bytes((0x20, FINISH)))
    print("HOST PASS: concurrent live FM/I2C commands, independent mutes and lease mute verified.")


def run():
    shared.run(check_fn=check, title="YM2203 Rev C / I2C + live FM mixer HOST check v1.1 / OTHER Pico only")


if __name__ == "__main__":
    run()
