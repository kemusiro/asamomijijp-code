# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""External controller for Rev C fixed SSG tones and lease-mute check."""
import time
from machine import Pin, I2C
from rev_c_i2c_host_check import checked_write, read_at


SIGNATURE = b"RCSSG01!"
STOP, TONE_A, TONE_B, TONE_C, KEEP, FINISH = range(6)


class ObservedI2C:
    """Keep counters and only the last read, with hardware clocking underneath."""
    def __init__(self, bus):
        self.bus = bus
        self.read_calls = self.read_bytes = self.write_calls = self.write_bytes = 0
        self.last_read = None

    def writeto(self, address, data, stop=True):
        self.write_calls += 1
        written = self.bus.writeto(address, data, stop)
        self.write_bytes += written
        return written

    def readfrom(self, address, count):
        self.read_calls += 1
        data = self.bus.readfrom(address, count)
        self.read_bytes += len(data)
        self.last_read = data
        return data


class Remote:
    max_opcode = FINISH
    max_mode = 3
    keep_opcode = KEEP
    ack_wait_ms = 10

    def __init__(self, i2c):
        self.i2c = i2c
        status = read_at(i2c, 0x10, 4)
        if status != b"\x00\x00\x00\x00":
            raise RuntimeError("Initial SSG status is not fresh/valid: %r; soft reset both boards" % status)
        self.ack = status[0]

    def command(self, value, channel):
        checked_write(self.i2c, bytes((0x20, value)))
        started = time.ticks_ms()
        while True:
            time.sleep_ms(self.ack_wait_ms)
            status = read_at(self.i2c, 0x10, 4)
            changed = status[0] != self.ack
            invalid = status[1] > self.max_opcode or status[2] > self.max_mode or status[3] > 1
            if invalid or (changed and (status[0] != (self.ack + 1) & 255 or
                                       status[1:] != bytes((value, channel, 0)))):
                raise RuntimeError("SSG command/status mismatch: previous_ack=%d command=%d actual=%r" %
                                   (self.ack, value, status))
            if changed:
                self.ack = status[0]
                return
            if time.ticks_diff(time.ticks_ms(), started) >= 1000:
                raise RuntimeError("SSG command acknowledgement timeout: previous_ack=%d command=%d expected_mode=%d actual=%r" %
                                   (self.ack, value, channel, status))

    def hold(self, channel):
        started = time.ticks_ms()
        while True:
            remaining = 2000 - time.ticks_diff(time.ticks_ms(), started)
            if remaining <= 0:
                return
            time.sleep_ms(min(200, remaining))
            self.command(self.keep_opcode, channel)


def preflight(i2c, signature=SIGNATURE, remote_factory=Remote):
    # No scan: RP2's zero-length address probes use a software-I2C fallback.
    # Nonempty pointer writes and reads below use the hardware peripheral.
    if read_at(i2c, 0, 8) != signature:
        raise RuntimeError("Run the matching I2C target first; signature mismatch/no 0x42")
    remote = remote_factory(i2c)
    remote.command(STOP, 0)
    print("PASS: target signature and acknowledged STOP")
    expected = bytes((remote.ack, STOP, 0, 0))
    for index in range(64):
        status = read_at(i2c, 0x10, 4)
        if status != expected:
            raise RuntimeError("Read integrity failed before sound: index=%d actual=%r" % (index, status))
    for unused in range(32):
        remote.command(remote.keep_opcode, 0)
    print("PASS: 64 stable status reads + 32 acknowledged KEEP commands while muted")
    return remote


def check(i2c):
    remote = preflight(i2c)
    print("Six tones then one short watchdog tone. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    for repetition in range(2):
        for channel in (TONE_A, TONE_B, TONE_C):
            print("SSG %s / round %d/2 / about 440 Hz / 2 seconds" %
                  ("ABC"[channel - 1], repetition + 1))
            remote.command(channel, channel)
            remote.hold(channel)
            remote.command(STOP, 0)
            print("STOP acknowledged / 1 second")
            time.sleep_ms(1000)
    print("WATCHDOG / SSG A; no keepalive / should mute itself after about 1 second")
    remote.command(TONE_A, TONE_A)
    time.sleep_ms(1600)
    status = read_at(i2c, 0x10, 4)
    if status != bytes((remote.ack, TONE_A, 0, 1)):
        raise RuntimeError("SSG lease did not expire/mute: %r" % status)
    print("PASS: lease expired and source muted without a STOP command")
    time.sleep_ms(400)
    remote.command(STOP, 0)
    checked_write(i2c, bytes((0x20, FINISH)))
    print("HOST PASS: SSG commands, acknowledged stops and lease mute verified.")


def run(check_fn=None, title=None):
    print(title or "YM2203 Rev C / I2C SSG host check v1.2 / OTHER Pico only")
    print("HARDWARE I2C0 SDA=GP0 SCL=GP1 10kHz; start both volumes low.")
    i2c = None
    try:
        bus = I2C(0, sda=Pin(0), scl=Pin(1), freq=10000, timeout=500000)
        i2c = ObservedI2C(bus)
        print("BUS:", bus)
        if check_fn is None:
            check(i2c)
        else:
            check_fn(i2c)
    finally:
        # The target's one-second lease also mutes after a host failure/Ctrl+C.
        Pin(0, Pin.IN, pull=None)
        Pin(1, Pin.IN, pull=None)
        if i2c is not None:
            print("HOST I2C STATS: reads=%d read_bytes=%d writes=%d write_bytes=%d last_read=%r" %
                  (i2c.read_calls, i2c.read_bytes, i2c.write_calls, i2c.write_bytes, i2c.last_read))
        print("HOST SAFE: GP0/GP1=input; wait for target lease mute if interrupted")


if __name__ == "__main__":
    run()
