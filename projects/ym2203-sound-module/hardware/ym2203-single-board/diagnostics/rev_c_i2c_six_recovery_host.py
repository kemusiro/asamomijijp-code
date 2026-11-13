# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Release HOST pins at transaction boundaries, then verify lease/recovery."""
import time
from machine import Pin, I2C
import rev_c_i2c_six_host as six


mixer = six.mixer
ROUNDS = 3
DISCONNECTED_MS = 1800


class RecoveredRemote(six.Remote):
    def __init__(self, i2c, expected_ack):
        # This attaches to the SAME running target, never to a fresh/reset one.
        # No command is sent until identity, unchanged ACK and lease cleanup agree.
        if mixer.read_at(i2c, 0, 8) != six.SIGNATURE:
            raise RuntimeError("Recovery target signature mismatch")
        actual = mixer.read_at(i2c, 0x10, 6)
        expected = bytes((expected_ack, mixer.KEEP, 0, 1, 0, 0))
        if actual != expected:
            raise RuntimeError("Recovery lease/state mismatch: expected=%r actual=%r" % (expected, actual))
        self.i2c = i2c
        self.ack = expected_ack


def hold_chord(i2c, remote):
    six.hold(i2c, remote, 0x7F, 1, 63)


def recover(i2c, remote, index):
    six.verify(i2c, remote, mixer.KEEP, 1, 63)
    expected_ack = remote.ack
    print("RECOVERY %d/%d / HOST PINS RELEASED / no I2C for %d ms" %
          (index, ROUNDS, DISCONNECTED_MS))
    # Only HOST GP0/1 change function; no cable/power changes or mid-frame abort.
    Pin(0, Pin.IN, pull=None)
    Pin(1, Pin.IN, pull=None)
    time.sleep_ms(DISCONNECTED_MS)
    print("RECOVERY %d/%d / REBIND / expect silence until explicit restart" % (index, ROUNDS))
    # Keep ObservedI2C's counters; recreate only its underlying hardware bus.
    i2c.bus = I2C(0, sda=Pin(0), scl=Pin(1), freq=10000, timeout=500000)
    recovered = RecoveredRemote(i2c, expected_ack)
    print("RECOVERY %d/%d / ATTACH PASS / ack=%d lease=1 mask=0 busy=0" %
          (index, ROUNDS, recovered.ack))
    # STOP clears the latched expiry. START is deliberately NOT sent again.
    recovered.command(mixer.STOP, 0)
    six.verify(i2c, recovered, mixer.STOP, 0, 0)
    print("RECOVERY %d/%d / STOP acknowledged / lease cleared; resume six voices" % (index, ROUNDS))
    recovered.command(0x7F, 1)
    hold_chord(i2c, recovered)
    print("RECOVERY %d/%d PASS / six voices restored" % (index, ROUNDS))
    return recovered


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=six.SIGNATURE, remote_factory=six.Remote)
    six.verify(i2c, remote, mixer.KEEP, 0, 0)
    remote.command(mixer.START, 0)
    six.verify(i2c, remote, mixer.START, 0, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: six-voice START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Three HOST release/rebind cycles. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    remote.command(0x7F, 1)
    hold_chord(i2c, remote)
    for index in range(ROUNDS):
        remote = recover(i2c, remote, index + 1)
    remote.command(mixer.STOP, 0)
    six.verify(i2c, remote, mixer.STOP, 0, 0)
    print("FINAL STOP / all sources off / 1 second silence")
    time.sleep_ms(1000)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: three HOST pin releases, lease cleanup, same-target reattachment and explicit restarts")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    six.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for six-voice READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C six-voice recovery HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
