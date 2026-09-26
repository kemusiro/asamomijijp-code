# SPDX-License-Identifier: BSD-2-Clause
"""Write-only AQM1602XA-RN-GBW driver for MicroPython machine.I2C/SoftI2C."""

try:
    from time import sleep_ms, sleep_us
except ImportError:  # CPython host tests.
    from time import sleep

    def sleep_ms(value):
        sleep(value / 1000)

    def sleep_us(value):
        sleep(value / 1000000)


class Aqm1602:
    ADDRESS = 0x3E
    V5 = "5V"
    V3_3 = "3.3V"
    TWO_LINES = "two_lines"
    ONE_LINE = "one_line"
    DOUBLE_HEIGHT = "double_height"
    LEFT = "left"
    RIGHT = "right"
    BIAS_ONE_FIFTH = "1/5"
    BIAS_ONE_FOURTH = "1/4"

    def __init__(self, i2c):
        # Construction does not touch the I2C bus or change its configuration.
        self._i2c = i2c
        self._buffer = bytearray(2)
        self._ready = False
        self._last_error = None
        self._bytes_written = 0
        self._mode = self.TWO_LINES
        self._supply = self.V3_3
        self._contrast = 35
        self._booster = True
        self._display = 4
        self._entry = 2

    @property
    def ready(self):
        return self._ready

    @property
    def last_error(self):
        return self._last_error

    @property
    def bytes_written(self):
        return self._bytes_written

    @staticmethod
    def _integer(value, low, high, name):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(name + " is out of range")

    @staticmethod
    def _choice(value, choices, name):
        if value not in choices:
            raise ValueError("invalid " + name)

    @staticmethod
    def _boolean(value):
        if type(value) is not bool:
            raise ValueError("expected bool")

    def _start(self):
        if not self._ready:
            raise RuntimeError("LCD requires begin()")
        self._last_error = None

    def _transfer(self, control, value, wait_us=100):
        self._buffer[0] = control
        self._buffer[1] = value
        try:
            count = self._i2c.writeto(self.ADDRESS, self._buffer)
            sleep_us(wait_us)
            if count != 2:
                raise OSError(5, "incomplete LCD transfer")
        except BaseException as error:
            # Includes interruption during a transfer or its wait period.
            self._ready = False
            self._last_error = error
            raise

    def _command(self, value, wait_us=100):
        self._transfer(0x00, value, wait_us)

    def _function(self, extended=False, mode=None):
        if mode is None:
            mode = self._mode
        bits = 8 if mode == self.TWO_LINES else (4 if mode == self.DOUBLE_HEIGHT else 0)
        return 0x30 | bits | int(extended)

    @staticmethod
    def _power(contrast, booster):
        return 0x50 | (4 if booster else 0) | (contrast >> 4)

    def _sequence(self, commands, settle_after=None):
        # A partially completed multi-command operation must not remain usable.
        self._ready = False
        try:
            for index, command in enumerate(commands):
                self._command(command, 3000 if command in (1, 2) else 100)
                if index == settle_after:
                    sleep_ms(201)
        except BaseException as error:
            self._last_error = error
            raise
        self._ready = True

    def begin(self, *, supply=V3_3, contrast=35, mode=TWO_LINES,
              bias=BIAS_ONE_FIFTH, oscillator=4, follower_ratio=4):
        """Initialize; 3.3 V contrast is a starting value, not a measured optimum."""
        self._choice(supply, (self.V5, self.V3_3), "supply")
        self._choice(mode, (self.TWO_LINES, self.ONE_LINE, self.DOUBLE_HEIGHT), "mode")
        self._choice(bias, (self.BIAS_ONE_FIFTH, self.BIAS_ONE_FOURTH), "bias")
        self._integer(contrast, 0, 63, "contrast")
        self._integer(oscillator, 0, 7, "oscillator")
        self._integer(follower_ratio, 0, 7, "follower_ratio")
        self._ready = False
        self._last_error = None
        self._bytes_written = 0
        self._mode = mode
        self._supply = supply
        self._contrast = contrast
        self._booster = supply == self.V3_3
        self._display = 4
        self._entry = 2
        try:
            sleep_ms(100)
            self._sequence((
                self._function(), self._function(True),
                0x10 | (8 if bias == self.BIAS_ONE_FOURTH else 0) | oscillator,
                0x70 | (contrast & 15), self._power(contrast, self._booster),
                0x68 | follower_ratio, self._function(), 0x08, 0x01, 0x06, 0x0C,
            ), settle_after=5)
        except BaseException as error:
            self._last_error = error
            raise

    def write(self, data):
        """Send bytes/bytearray unchanged. Return count; raise on partial failure."""
        self._start()
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("write expects bytes or bytearray")
        self._bytes_written = 0
        for value in data:
            self._transfer(0x40, value)
            self._bytes_written += 1
        return self._bytes_written

    def write_byte(self, value):
        self._start()
        self._integer(value, 0, 255, "character code")
        self._bytes_written = 0
        self._transfer(0x40, value)
        self._bytes_written = 1
        return 1

    def text(self, value):
        """Printable ASCII only. Use write(bytes) for LCD kana/custom glyph codes."""
        self._start()
        if not isinstance(value, str):
            raise TypeError("text expects str")
        for char in value:
            if not 0x20 <= ord(char) <= 0x7E:
                raise ValueError("text accepts printable ASCII; use write for LCD codes")
        return self.write(value.encode())

    def clear(self):
        self._start()
        # The controller's clear instruction sets I/D=1; restore user choice.
        self._sequence((0x01, 0x04 | self._entry))

    def home(self):
        self._start()
        self._command(0x02, 3000)

    def set_cursor(self, column, row):
        self._start()
        self._integer(column, 0, 15, "column")
        self._integer(row, 0, 1 if self._mode == self.TWO_LINES else 0, "row")
        self._command(0x80 | (0x40 if row else 0) | column)

    def set_ddram_address(self, address):
        self._start()
        self._integer(address, 0, 0x7F, "DDRAM address")
        valid = address <= 0x27
        if self._mode == self.TWO_LINES:
            valid = valid or 0x40 <= address <= 0x67
        elif self._mode == self.ONE_LINE:
            valid = address <= 0x4F
        if not valid:
            raise ValueError("DDRAM address outside selected mode")
        self._command(0x80 | address)

    def set_cgram_address(self, address):
        self._start()
        self._integer(address, 0, 63, "CGRAM address")
        self._command(0x40 | address)

    def create_char(self, slot, bitmap):
        self._start()
        self._integer(slot, 0, 7, "slot")
        if self._mode == self.DOUBLE_HEIGHT:
            raise ValueError("create_char supports 5x8 mode only")
        if not isinstance(bitmap, (bytes, bytearray, tuple, list)) or len(bitmap) != 8:
            raise ValueError("bitmap must contain exactly 8 rows")
        for value in bitmap:
            self._integer(value, 0, 31, "bitmap row")
        self._ready = False
        try:
            self._command(0x06)
            self._command(0x40 | (slot << 3))
            for value in bitmap:
                self._transfer(0x40, value)
            self._command(0x80)
            self._command(0x04 | self._entry)
        except BaseException as error:
            self._last_error = error
            raise
        self._ready = True

    def _change_display(self, bit, enabled):
        self._start()
        self._boolean(enabled)
        next_value = self._display | bit if enabled else self._display & ~bit
        self._command(0x08 | next_value)
        self._display = next_value

    def set_display(self, enabled):
        self._change_display(4, enabled)

    def set_cursor_visible(self, enabled):
        self._change_display(2, enabled)

    def set_blink(self, enabled):
        self._change_display(1, enabled)

    def set_entry_mode(self, direction, shift_display=False):
        self._start()
        self._choice(direction, (self.LEFT, self.RIGHT), "direction")
        self._boolean(shift_display)
        next_value = (2 if direction == self.RIGHT else 0) | int(shift_display)
        self._command(0x04 | next_value)
        self._entry = next_value

    def _shift(self, direction, display):
        self._start()
        self._choice(direction, (self.LEFT, self.RIGHT), "direction")
        self._command(0x10 | (8 if display else 0) | (4 if direction == self.RIGHT else 0))

    def move_cursor(self, direction):
        self._shift(direction, False)

    def scroll_display(self, direction):
        self._shift(direction, True)

    def set_mode(self, mode):
        self._start()
        self._choice(mode, (self.TWO_LINES, self.ONE_LINE, self.DOUBLE_HEIGHT), "mode")
        self._sequence((self._function(mode=mode), 0x02))
        self._mode = mode

    def _extended(self, command, settle=False):
        self._sequence((self._function(True), command, self._function()),
                       settle_after=1 if settle else None)

    def set_contrast(self, contrast):
        self._start()
        self._integer(contrast, 0, 63, "contrast")
        self._sequence((self._function(True), 0x70 | (contrast & 15),
                        self._power(contrast, self._booster), self._function()))
        self._contrast = contrast

    def set_bias_and_oscillator(self, bias, oscillator):
        self._start()
        self._choice(bias, (self.BIAS_ONE_FIFTH, self.BIAS_ONE_FOURTH), "bias")
        self._integer(oscillator, 0, 7, "oscillator")
        self._extended(0x10 | (8 if bias == self.BIAS_ONE_FOURTH else 0) | oscillator)

    def set_follower(self, enabled, ratio):
        self._start()
        self._boolean(enabled)
        self._integer(ratio, 0, 7, "follower ratio")
        self._extended(0x60 | (8 if enabled else 0) | ratio, settle=enabled)

    def set_booster(self, enabled):
        self._start()
        self._boolean(enabled)
        if enabled and self._supply != self.V3_3:
            raise ValueError("booster requires 3.3V supply configuration")
        self._extended(self._power(self._contrast, enabled), settle=enabled)
        self._booster = enabled
