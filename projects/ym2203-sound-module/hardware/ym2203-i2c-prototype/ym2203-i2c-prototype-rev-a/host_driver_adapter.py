# SPDX-License-Identifier: MIT
# MicroPython host-side adapter; NOT firmware for the sound module MCU.
from web_lab_ym2203_v1 import YM2203 as _YM2203


class YM2203I2CHardware(_YM2203):
    """Use explicit opcode 00 for register writes on a physical I2C bus."""

    def write_register(self, register, value):
        if type(register) is not int or not 0 <= register <= 255:
            raise ValueError("Register is out of range")
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError("Register value is out of range")
        self.i2c.writeto(self.address, bytes((0, register, value)))
        if register == 7:
            self._mixer = value
