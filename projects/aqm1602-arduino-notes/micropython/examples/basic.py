# SPDX-License-Identifier: BSD-2-Clause
from machine import I2C, Pin
from aqm1602 import Aqm1602

# Pico 2 W, LCD 3.3 V, onboard pull-ups enabled: SDA=GP16, SCL=GP17.
i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=100_000)
addresses = i2c.scan()
print("I2C addresses:", [hex(address) for address in addresses])
if Aqm1602.ADDRESS not in addresses:
    raise RuntimeError("AQM1602 did not ACK at 0x3E")

lcd = Aqm1602(i2c)
lcd.begin(supply=Aqm1602.V3_3, contrast=35)
lcd.text("AQM1602 / Pico2W")
lcd.set_cursor(0, 1)
lcd.text("MicroPython 1.29")
print("LCD writes completed; ready:", lcd.ready)
# A successful I2C write is not a visual check. Confirm both lines on the LCD.
