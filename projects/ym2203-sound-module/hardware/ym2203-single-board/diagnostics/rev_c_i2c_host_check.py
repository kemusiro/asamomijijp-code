# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Run on a separate Pico/Pico 2; GP0/1 connect to Rev C JHOST SDA/SCL."""
import time
from machine import Pin, SoftI2C


ADDRESS = 0x42
SIGNATURE = b"RCI2C01!"
FREQUENCY = 10000  # first electrical/target test, not the final bus speed


def checked_write(i2c, data, stop=True):
    if i2c.writeto(ADDRESS, data, stop) != len(data):
        raise RuntimeError("Short I2C write")


def read_at(i2c, register, count, repeated=True):
    checked_write(i2c, bytes((register,)), not repeated)
    data = i2c.readfrom(ADDRESS, count)
    if len(data) != count:
        raise RuntimeError("Short I2C read")
    return data


def check(i2c):
    found = i2c.scan()
    print("SCAN:", [hex(address) for address in found])
    if ADDRESS not in found:
        raise RuntimeError("No target at 0x42; check READY, wiring and pull-ups")
    if read_at(i2c, 0, 8) != SIGNATURE:
        raise RuntimeError("Diagnostic signature mismatch")
    print("PASS: signature", SIGNATURE)
    for index in range(22):
        if index < 4:
            value = (0, 255, 85, 170)[index]
            data = bytes((value for unused in range(32)))
        elif index < 12:
            data = bytes((1 << (index - 4) for unused in range(32)))
        elif index < 20:
            data = bytes((255 ^ (1 << (index - 12)) for unused in range(32)))
        else:
            data = bytes((n if index == 20 else 255 - n for n in range(32)))
        checked_write(i2c, b"\x20" + data)
        # Cover both STOP-separated and repeated-start pointer/read sequences.
        if read_at(i2c, 0x20, 32, repeated=bool(index & 1)) != data:
            raise RuntimeError("I2C RAM mismatch at pattern %d" % (index + 1))
    print("PASS: 22 patterns x 32 bytes; STOP and repeated-start reads")
    checked_write(i2c, b"\x00\x00")  # identity must stay read-only
    if read_at(i2c, 0, 8) != SIGNATURE:
        raise RuntimeError("Read-only identity was overwritten")
    if read_at(i2c, 0xFE, 10) != b"\x00\x00" + SIGNATURE:
        raise RuntimeError("Address wrap/read boundary mismatch")
    print("PASS: read-only identity and address wrap")
    checked_write(i2c, b"\x7F\xA5")
    print("HOST PASS: silent I2C link complete; finish command sent.")


def run():
    print("YM2203 Rev C / I2C host check v1 / OTHER Pico only")
    print("SDA=GP0 SCL=GP1; start the Rev C target first. Expect NO sound.")
    try:
        i2c = SoftI2C(sda=Pin(0), scl=Pin(1), freq=FREQUENCY, timeout=500000)
        time.sleep_ms(100)
        check(i2c)
    finally:
        Pin(0, Pin.IN, pull=None)
        Pin(1, Pin.IN, pull=None)
        print("HOST SAFE: GP0/GP1=input")


if __name__ == "__main__":
    run()
