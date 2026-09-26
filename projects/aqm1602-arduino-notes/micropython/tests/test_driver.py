# SPDX-License-Identifier: BSD-2-Clause
"""Runs on CPython and MicroPython. No GPIO, real I2C, or flash writes."""
import sys

sys.path.insert(0, "micropython")
import aqm1602 as driver

Aqm1602 = driver.Aqm1602


class FakeI2C:
    def __init__(self):
        self.sent = []
        self.fail_at = None
        self.short_at = None
        self.failure = OSError(5)

    def writeto(self, address, data):
        index = len(self.sent)
        self.sent.append((address, bytes(data)))
        if index == self.fail_at:
            raise self.failure
        return 1 if index == self.short_at else len(data)


def expect_error(kind, call):
    try:
        call()
    except kind:
        return
    raise AssertionError("expected " + str(kind))


def commands(bus):
    assert all(address == 0x3E and len(data) == 2 and data[0] == 0 for address, data in bus.sent)
    return [data[1] for _, data in bus.sent]


def make_lcd(**kwargs):
    bus = FakeI2C()
    lcd = Aqm1602(bus)
    lcd.begin(**kwargs)
    bus.sent.clear()
    return lcd, bus


def test_begin(delays):
    for supply, power in ((Aqm1602.V5, 0x52), (Aqm1602.V3_3, 0x56)):
        bus = FakeI2C()
        lcd = Aqm1602(bus)
        assert not lcd.ready and not bus.sent
        expect_error(RuntimeError, lcd.home)
        delays.clear()
        lcd.begin(supply=supply)
        assert lcd.ready and lcd.last_error is None
        assert commands(bus) == [0x38,0x39,0x14,0x73,power,0x6C,0x38,8,1,6,12]
        assert delays[0] == 100000 and delays[7] == 201000
        assert 3000 in delays and all(t >= 100 for t in delays)
    for mode, bits in ((Aqm1602.TWO_LINES,8), (Aqm1602.ONE_LINE,0), (Aqm1602.DOUBLE_HEIGHT,4)):
        for setting in range(8):
            bus = FakeI2C()
            lcd = Aqm1602(bus)
            lcd.begin(mode=mode, bias=Aqm1602.BIAS_ONE_FOURTH,
                      oscillator=setting, follower_ratio=setting)
            data = commands(bus)
            assert data[0:3] == [0x30 | bits,0x31 | bits,0x18 | setting]
            assert data[5] == 0x68 | setting and data[6] == 0x30 | bits


def test_controls():
    lcd, bus = make_lcd()
    lcd.set_cursor_visible(True)
    lcd.set_blink(True)
    lcd.set_display(False)
    lcd.set_display(True)
    lcd.set_cursor_visible(False)
    lcd.set_blink(False)
    lcd.move_cursor(lcd.LEFT)
    lcd.move_cursor(lcd.RIGHT)
    lcd.scroll_display(lcd.LEFT)
    lcd.scroll_display(lcd.RIGHT)
    assert commands(bus) == [14,15,11,15,13,12,16,20,24,28]
    bus.sent.clear()
    lcd.set_entry_mode(lcd.LEFT, True)
    lcd.clear()
    lcd.home()
    assert commands(bus) == [5,1,5,2]
    for contrast in range(64):
        bus.sent.clear()
        lcd.set_contrast(contrast)
        assert commands(bus) == [0x39,0x70 | (contrast & 15),0x54 | (contrast >> 4),0x38]
    bus.sent.clear()
    lcd.set_booster(False)
    lcd.set_contrast(35)
    lcd.set_booster(True)
    assert commands(bus) == [0x39,0x53,0x38,0x39,0x73,0x52,0x38,0x39,0x56,0x38]
    bus.sent.clear()
    lcd.set_bias_and_oscillator(lcd.BIAS_ONE_FOURTH,7)
    lcd.set_follower(False,0)
    lcd.set_follower(True,4)
    assert commands(bus) == [0x39,0x1F,0x38,0x39,0x60,0x38,0x39,0x6C,0x38]


def test_ram():
    lcd, bus = make_lcd()
    lcd.set_cursor(0,1)
    assert lcd.text("ABC") == 3 and lcd.bytes_written == 3
    assert bus.sent == [(0x3E,b'\x00\xc0'),(0x3E,b'\x40A'),(0x3E,b'\x40B'),(0x3E,b'\x40C')]
    lcd.set_entry_mode(lcd.LEFT, True)
    bus.sent.clear()
    glyph = bytes((0,4,14,31,14,4,0,0))
    lcd.create_char(7,glyph)
    assert bus.sent[:2] == [(0x3E,b'\x00\x06'),(0x3E,b'\x00\x78')]
    assert [data[1] for _,data in bus.sent[2:10]] == list(glyph)
    assert all(data[0] == 0x40 for _,data in bus.sent[2:10])
    assert bus.sent[-2:] == [(0x3E,b'\x00\x80'),(0x3E,b'\x00\x05')]
    bus.sent.clear()
    lcd.set_cgram_address(63)
    lcd.write_byte(31)
    lcd.set_ddram_address(0x67)
    lcd.write_byte(0)
    assert [data for _,data in bus.sent] == [b'\x00\x7f',b'\x40\x1f',b'\x00\xe7',b'\x40\x00']
    bus.sent.clear()
    data = bytes(range(100))
    assert lcd.write(data) == 100
    assert [item[1][1] for item in bus.sent] == list(data)
    assert lcd.write(bytearray()) == 0


def test_validation():
    lcd, bus = make_lcd()
    for call in (
        lambda: lcd.set_cursor(16,0), lambda: lcd.set_cursor(0,2),
        lambda: lcd.set_cursor(-1,0), lambda: lcd.set_cursor(1.5,0),
        lambda: lcd.set_ddram_address(0x28), lambda: lcd.set_ddram_address(0x68),
        lambda: lcd.set_cgram_address(64), lambda: lcd.set_contrast(64),
        lambda: lcd.write_byte(256), lambda: lcd.write_byte(True),
        lambda: lcd.create_char(8,bytes(8)), lambda: lcd.create_char(0,bytes(7)),
        lambda: lcd.create_char(0,[32]*8), lambda: lcd.set_mode("unknown"),
        lambda: lcd.set_entry_mode("unknown"), lambda: lcd.move_cursor("unknown"),
        lambda: lcd.scroll_display("unknown"), lambda: lcd.set_display(1),
        lambda: lcd.set_follower(True,8), lambda: lcd.set_booster(1),
        lambda: lcd.set_bias_and_oscillator("unknown",4),
        lambda: lcd.set_bias_and_oscillator(lcd.BIAS_ONE_FIFTH,8),
        lambda: lcd.text("日本語"), lambda: lcd.text("A\nB"),
        lambda: lcd.begin(supply="12V"), lambda: lcd.begin(contrast=64),
        lambda: lcd.begin(mode="unknown"), lambda: lcd.begin(bias="unknown"),
        lambda: lcd.begin(oscillator=8), lambda: lcd.begin(follower_ratio=8),
    ):
        expect_error(ValueError,call)
        assert not bus.sent and lcd.ready
    expect_error(TypeError, lambda: lcd.write("ABC"))
    expect_error(TypeError, lambda: lcd.text(123))
    lcd.set_mode(lcd.ONE_LINE)
    lcd.set_ddram_address(0x4F)
    expect_error(ValueError, lambda: lcd.set_ddram_address(0x50))
    expect_error(ValueError, lambda: lcd.set_cursor(0,1))
    lcd.set_mode(lcd.DOUBLE_HEIGHT)
    lcd.set_ddram_address(0x27)
    expect_error(ValueError, lambda: lcd.set_ddram_address(0x28))
    expect_error(ValueError, lambda: lcd.create_char(0,bytes(8)))
    bus.sent.clear()
    lcd.set_contrast(35)
    assert commands(bus) == [0x35,0x73,0x56,0x34]
    lcd.begin(supply=lcd.V5)
    expect_error(ValueError, lambda: lcd.set_booster(True))


def test_failures():
    for index in range(11):
        bus = FakeI2C()
        lcd = Aqm1602(bus)
        bus.fail_at = index
        expect_error(OSError,lcd.begin)
        assert not lcd.ready and lcd.last_error is bus.failure and len(bus.sent) == index+1
        expect_error(RuntimeError,lambda: lcd.text("ABC"))
        assert len(bus.sent) == index+1 and lcd.last_error is bus.failure
        bus.fail_at = None
        lcd.begin()
        assert lcd.ready and lcd.last_error is None
    for operation, length in (("contrast",4),("glyph",12),("follower",3),("oscillator",3),("mode",2),("clear",2)):
        for index in range(length):
            lcd, bus = make_lcd()
            bus.fail_at = index
            actions = {
                "contrast": lambda: lcd.set_contrast(20),
                "glyph": lambda: lcd.create_char(0,bytes(8)),
                "follower": lambda: lcd.set_follower(True,4),
                "oscillator": lambda: lcd.set_bias_and_oscillator(lcd.BIAS_ONE_FIFTH,4),
                "mode": lambda: lcd.set_mode(lcd.ONE_LINE),
                "clear": lcd.clear,
            }
            expect_error(OSError,actions[operation])
            assert not lcd.ready and len(bus.sent) == index+1
    for index in range(3):
        lcd, bus = make_lcd()
        bus.fail_at = index
        expect_error(OSError, lambda: lcd.write(b"ABC"))
        assert lcd.bytes_written == index and len(bus.sent) == index+1 and not lcd.ready
    lcd, bus = make_lcd()
    bus.short_at = 0
    expect_error(OSError,lambda: lcd.write_byte(65))
    assert not lcd.ready and lcd.bytes_written == 0
    lcd, bus = make_lcd()
    bus.fail_at = 1
    bus.failure = KeyboardInterrupt()
    expect_error(KeyboardInterrupt, lambda: lcd.set_contrast(20))
    assert not lcd.ready


def main():
    delays = []
    original_ms, original_us = driver.sleep_ms, driver.sleep_us
    driver.sleep_ms = lambda ms: delays.append(ms * 1000)
    driver.sleep_us = lambda us: delays.append(us)
    try:
        test_begin(delays)
        test_controls()
        test_ram()
        test_validation()
        test_failures()
        print("PASS: MicroPython driver initialization, controls, RAM, validation, failures")
    finally:
        driver.sleep_ms, driver.sleep_us = original_ms, original_us


main()
