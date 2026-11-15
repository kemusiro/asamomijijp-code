# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Separate Pico controller for silent, staged I2C initialization isolation."""
import time
from machine import Pin, I2C
from rev_c_i2c_host_check import checked_write, read_at


SIGNATURE = b"RCISO01!"
PHASE_COUNT = 6
TRANSITION_MS = 3000


def check_phase(i2c, phase):
    expected = SIGNATURE + bytes((phase, phase ^ 255))
    # Keep the first transaction identical to the failing FM host pointer write.
    for index in range(32):
        actual = read_at(i2c, 0, 10, repeated=not bool(index & 1))
        if actual != expected:
            raise RuntimeError("Isolation phase/header mismatch: phase=%d index=%d actual=%r" %
                               (phase, index, actual))
    for index, value in enumerate((0, 255, 85, 170)):
        data = bytes((value for unused in range(32)))
        checked_write(i2c, b"\x20" + data)
        if read_at(i2c, 0x20, 32, repeated=bool(index & 1)) != data:
            raise RuntimeError("Isolation RAM mismatch: phase=%d pattern=%d" % (phase, index))
    checked_write(i2c, b"\x00\x00")
    if read_at(i2c, 0, 10) != expected:
        raise RuntimeError("Isolation read-only header changed")


def check(i2c):
    for phase in range(PHASE_COUNT):
        print("PHASE %d CHECK / 32 headers + four RAM patterns / expect NO sound" % phase)
        check_phase(i2c, phase)
        print("PHASE %d PASS" % phase)
        checked_write(i2c, bytes((0x7F if phase == PHASE_COUNT - 1 else 0x7E, 0xA5)))
        if phase < PHASE_COUNT - 1:
            # No retries/replayed commands. I2C is intentionally disabled while
            # the target adds resources; the next check starts after this pause.
            print("WAIT: 3 seconds for target initialization")
            time.sleep_ms(TRANSITION_MS)
    print("HOST PASS: all six silent initialization phases verified")


def run():
    print("YM2203 Rev C / silent I2C initialization isolation HOST v1 / OTHER Pico only")
    print("SDA=GP0 SCL=GP1 hardware I2C0 10kHz. Start after target PHASE 0 READY.")
    try:
        i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=10000, timeout=500000)
        print("BUS:", i2c)
        check(i2c)
    finally:
        Pin(0, Pin.IN, pull=None)
        Pin(1, Pin.IN, pull=None)
        print("HOST SAFE: GP0/GP1=input")


if __name__ == "__main__":
    run()
