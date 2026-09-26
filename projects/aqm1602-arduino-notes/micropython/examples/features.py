# SPDX-License-Identifier: BSD-2-Clause
"""Visible feature demo for the documented Pico 2 W wiring; about 20 seconds."""
from machine import I2C, Pin
from time import sleep_ms
from aqm1602 import Aqm1602


def run(lcd):
    lcd.begin(supply=Aqm1602.V3_3, contrast=35)
    lcd.create_char(0, (0, 4, 14, 31, 14, 4, 0, 0))
    lcd.set_cursor(0, 0)
    lcd.write_byte(0)
    lcd.text(" Custom glyph")
    lcd.set_cursor(0, 1)
    lcd.text("Cursor / blink")
    lcd.set_cursor_visible(True)
    lcd.set_blink(True)
    print("STEP 1: diamond glyph, cursor and blinking block")
    sleep_ms(4000)
    lcd.move_cursor(lcd.LEFT)
    sleep_ms(500)
    lcd.move_cursor(lcd.RIGHT)
    lcd.set_cursor_visible(False)
    lcd.set_blink(False)
    print("STEP 2: scroll left four positions, then right four")
    for direction in (lcd.LEFT, lcd.RIGHT):
        for _ in range(4):
            lcd.scroll_display(direction)
            sleep_ms(400)
    lcd.home()
    print("STEP 3: display off, then on with text retained")
    lcd.set_display(False)
    sleep_ms(1000)
    lcd.set_display(True)
    sleep_ms(2000)
    lcd.clear()
    lcd.text("Right to left:")
    lcd.set_entry_mode(lcd.LEFT)
    lcd.set_cursor(15, 1)
    lcd.text("ABC")
    print("STEP 4: CBA at the right end of the second line")
    sleep_ms(4000)
    lcd.set_entry_mode(lcd.RIGHT)
    lcd.clear()
    lcd.text("Overwrite test:")
    lcd.set_cursor(0, 1)
    lcd.text("100")
    sleep_ms(1500)
    lcd.set_cursor(0, 1)
    lcd.text("%3d" % 99)
    print("STEP 5: second line is a space followed by 99")
    sleep_ms(3000)
    lcd.clear()
    lcd.text("AQM1602 / Pico2W")
    lcd.set_cursor(0, 1)
    lcd.text("Features done")
    lcd.set_cursor(15, 1)
    lcd.write_byte(0)
    print("DONE: all I2C writes ACKed; visual result must be checked separately")


i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=100_000)
lcd = Aqm1602(i2c)
run(lcd)
