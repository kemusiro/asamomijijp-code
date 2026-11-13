# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Silent, manual bus diagnostic for the physical YM2203 single board Rev C.

Run with official Pico 2 MicroPython, not WebLab or desktop Python. This is not
the production I2C/USB-MIDI/FM firmware. No automatic execution on import.
The approved GPIO map is unchanged. All SSG levels and both audio allows stay 0.
"""

import sys
import time
from machine import Pin


DATA_GPIO = tuple(range(8))
CONTROL_GPIO = {
    "a0": 8,
    "reset_release": 9,
    "cs_n": 13,
    "wr_n": 14,
    "rd_n": 15,
    "line_allow": 19,
    "arm": 22,
    "dac_allow": 26,
}
# U3 drives these signals; the Pico must never drive them during this test.
FM_INPUT_GPIO = (16, 17, 18, 28)
I2S_OUTPUT_GPIO = (10, 11, 12)
SETTLE_US = 10
WRITE_HOLD_US = 10
POST_WRITE_US = 20
BUSY_TIMEOUT_MS = 100
SSG_MASKS = (255, 15, 255, 15, 255, 15, 31, 255, 31, 31, 31)


def _check_platform():
    if sys.implementation.name != "micropython" or "RP2350" not in getattr(
        sys.implementation, "_machine", ""
    ):
        raise RuntimeError("Use official Pico 2 MicroPython on the physical Rev C board")


def _emergency_stop():
    # Also usable if construction was interrupted before a board object existed.
    Pin(CONTROL_GPIO["arm"], Pin.OUT, pull=None, value=0)
    Pin(CONTROL_GPIO["line_allow"], Pin.OUT, pull=None, value=0)
    Pin(CONTROL_GPIO["dac_allow"], Pin.OUT, pull=None, value=0)
    Pin(CONTROL_GPIO["reset_release"], Pin.OUT, pull=None, value=0)
    time.sleep_us(SETTLE_US)
    for gpio in DATA_GPIO:
        Pin(gpio, Pin.IN, pull=None)


class RevCBus:
    io_version = "1.1"  # indexed data loops; no enumerate/tuple churn per port

    def __init__(self):
        # ARM first: reset YM, block both data paths, and force line/DAC mute.
        self.arm = Pin(CONTROL_GPIO["arm"], Pin.OUT, pull=None, value=0)
        self.line_allow = Pin(CONTROL_GPIO["line_allow"], Pin.OUT, pull=None, value=0)
        self.dac_allow = Pin(CONTROL_GPIO["dac_allow"], Pin.OUT, pull=None, value=0)
        self.reset_release = Pin(CONTROL_GPIO["reset_release"], Pin.OUT, pull=None, value=0)
        self.cs_n = Pin(CONTROL_GPIO["cs_n"], Pin.OUT, pull=None, value=1)
        self.wr_n = Pin(CONTROL_GPIO["wr_n"], Pin.OUT, pull=None, value=1)
        self.rd_n = Pin(CONTROL_GPIO["rd_n"], Pin.OUT, pull=None, value=1)
        self.a0 = Pin(CONTROL_GPIO["a0"], Pin.OUT, pull=None, value=0)
        self.data = tuple(Pin(gpio, Pin.IN, pull=None) for gpio in DATA_GPIO)
        self.fm_inputs = tuple(Pin(gpio, Pin.IN, pull=None) for gpio in FM_INPUT_GPIO)
        self.i2s_outputs = tuple(
            Pin(gpio, Pin.OUT, pull=None, value=0) for gpio in I2S_OUTPUT_GPIO
        )
        self.active = False

    def close(self):
        self.line_allow.value(0)
        self.arm.value(0)
        time.sleep_us(SETTLE_US)
        self.active = False
        self.reset_release.value(0)
        self.dac_allow.value(0)
        self.cs_n.value(1)
        self.wr_n.value(1)
        self.rd_n.value(1)
        self._inputs()

    def _inputs(self):
        for pin in self.data:
            pin.init(Pin.IN, pull=None)

    def start(self):
        self.close()
        time.sleep_ms(2)
        self.arm.value(1)
        self.active = True
        time.sleep_ms(2)
        self.reset_release.value(1)
        time.sleep_ms(2)

    def _require_active(self):
        if not self.active:
            raise RuntimeError("The YM bus is held in reset")

    def _read_port(self, port):
        self._require_active()
        self.cs_n.value(1)
        self.wr_n.value(1)
        # Release all MCU outputs before RD switches U2 on and A3 off.
        self._inputs()
        self.a0.value(port)
        time.sleep_us(SETTLE_US)
        try:
            self.rd_n.value(0)
            time.sleep_us(SETTLE_US)
            self.cs_n.value(0)
            time.sleep_us(SETTLE_US)
            value = 0
            # enumerate() creates iterator/tuple objects on MicroPython. This
            # path also runs during continuous FM capture, where an automatic
            # heap collection can exceed one 11.25ms audio opportunity.
            bit = 0
            while bit < 8:
                value |= self.data[bit].value() << bit
                bit += 1
            return value
        finally:
            # Let YM release its outputs before switching A3 back on.
            self.cs_n.value(1)
            time.sleep_us(SETTLE_US)
            self.rd_n.value(1)
            time.sleep_us(SETTLE_US)
            # Data GPIOs remain inputs until the next explicit write.

    def _write_port(self, port, value):
        self._require_active()
        self.cs_n.value(1)
        self.wr_n.value(1)
        self.rd_n.value(1)
        time.sleep_us(SETTLE_US)
        bit = 0
        while bit < 8:
            self.data[bit].init(Pin.OUT, pull=None, value=(value >> bit) & 1)
            bit += 1
        self.a0.value(port)
        time.sleep_us(SETTLE_US)
        try:
            self.cs_n.value(0)
            time.sleep_us(SETTLE_US)
            self.wr_n.value(0)
            time.sleep_us(WRITE_HOLD_US)
        finally:
            self.wr_n.value(1)
            time.sleep_us(SETTLE_US)
            self.cs_n.value(1)
            time.sleep_us(POST_WRITE_US)

    def status(self):
        return self._read_port(0)

    def wait_ready(self):
        start = time.ticks_ms()
        while True:
            status = self.status()
            if not status & 0x80:
                return status
            if time.ticks_diff(time.ticks_ms(), start) >= BUSY_TIMEOUT_MS:
                raise RuntimeError("BUSY timeout (status=0x%02X)" % status)
            time.sleep_us(SETTLE_US)

    def write_ssg(self, register, value):
        if type(register) is not int or not 0 <= register < len(SSG_MASKS):
            raise ValueError("Only SSG registers 0x00..0x0A are used by this test")
        if type(value) is not int or value < 0 or value & ~SSG_MASKS[register]:
            raise ValueError("SSG data exceeds the implemented register bits")
        if register >= 8 and value != 0:
            raise ValueError("This silent diagnostic never enables SSG volume")
        if register == 7 and value != 0x3F:
            raise ValueError("This silent diagnostic keeps tone and noise disabled")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        self._write_port(1, value)
        self.wait_ready()

    def read_ssg(self, register):
        if type(register) is not int or not 0 <= register < len(SSG_MASKS):
            raise ValueError("Only SSG registers 0x00..0x0A are used by this test")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        return self._read_port(1) & SSG_MASKS[register]


def _readback(bus, register, patterns):
    for expected in patterns:
        bus.write_ssg(register, expected)
        # Repeated reads also exercise write-to-read and read-to-write turnaround.
        for unused in range(3):
            actual = bus.read_ssg(register)
            if actual != expected:
                raise RuntimeError(
                    "Readback mismatch reg=0x%02X expected=0x%02X actual=0x%02X"
                    % (register, expected, actual)
                )
    bus.write_ssg(register, 0)
    print("PASS reg=0x%02X patterns=%d" % (register, len(patterns)))


def _diagnose(bus):
    bus.start()
    status = bus.wait_ready()
    print("STATUS after reset: 0x%02X" % status)
    if status & 3:
        raise RuntimeError("Timer flags remain set after hardware reset")
    # Mute at both the chip and analogue switch; never release LINE_ALLOW.
    for register in (8, 9, 10):
        bus.write_ssg(register, 0)
        if bus.read_ssg(register) != 0:
            raise RuntimeError("SSG volume did not read back as zero")
    bus.write_ssg(7, 0x3F)
    if bus.read_ssg(7) != 0x3F:
        raise RuntimeError("SSG mixer did not read back as 0x3F")
    patterns = (0, 255, 85, 170)
    patterns += tuple(1 << bit for bit in range(8))
    patterns += tuple(255 ^ (1 << bit) for bit in range(8))
    for register in (0, 2, 4):
        _readback(bus, register, patterns)
    for register in (1, 3, 5):
        _readback(bus, register, (0, 15, 5, 10))


def run():
    _check_platform()
    print("YM2203 Rev C / silent bus check v1")
    print("Keep host I2C and AMS-22 disconnected. External 5V must be on.")
    bus = None
    try:
        bus = RevCBus()
        _diagnose(bus)
    except BaseException:
        print("FAIL or interrupted. Stop here; do not start an audio test.")
        raise
    finally:
        if bus is None:
            _emergency_stop()
        else:
            bus.close()
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0")
    print("PASS: silent bus read/write check complete; YM is held in reset.")


if __name__ == "__main__":
    run()
