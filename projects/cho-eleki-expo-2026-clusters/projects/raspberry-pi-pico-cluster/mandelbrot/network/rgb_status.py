"""RGB status LED control for the Pico 2 W exhibition worker."""

PWM_FREQUENCY_HZ = 2000

PIN_GREEN = 8
PIN_BLUE = 9
PIN_RED = 10

_DIM = 8192
_ACTIVE = 32768


class RgbStatusLed:
    """Drive the carrier-board common-cathode RGB LED with PWM."""

    def __init__(self, machine_module=None, sleep_ms=None):
        if machine_module is None:
            import machine as machine_module
        if sleep_ms is None:
            import time

            sleep_ms = time.sleep_ms

        self._machine = machine_module
        self._sleep_ms = sleep_ms
        self._pins = {
            "green": machine_module.Pin(PIN_GREEN, machine_module.Pin.OUT),
            "blue": machine_module.Pin(PIN_BLUE, machine_module.Pin.OUT),
            "red": machine_module.Pin(PIN_RED, machine_module.Pin.OUT),
        }
        self._pwm = {}
        for color, pin in self._pins.items():
            pwm = machine_module.PWM(pin)
            pwm.freq(PWM_FREQUENCY_HZ)
            self._pwm[color] = pwm
        self.off()

    def set_rgb(self, red, green, blue):
        for value in (red, green, blue):
            if type(value) is not int or not 0 <= value <= 65535:
                raise ValueError("RGB duty must be an integer from 0 to 65535")
        self._pwm["red"].duty_u16(red)
        self._pwm["green"].duty_u16(green)
        self._pwm["blue"].duty_u16(blue)

    def off(self):
        self.set_rgb(0, 0, 0)

    def waiting(self):
        self.set_rgb(0, _DIM, 0)

    def job_received(self):
        self.set_rgb(_ACTIVE, _ACTIVE, _ACTIVE)

    def computing(self):
        self.set_rgb(0, _ACTIVE // 2, _ACTIVE)

    def sending(self):
        self.set_rgb(_ACTIVE, _ACTIVE, _ACTIVE)

    def tile_waiting(self):
        self.set_rgb(0, 0, _DIM)

    def success(self):
        self.set_rgb(0, _ACTIVE, 0)

    def communication_error(self):
        for _index in range(2):
            self.set_rgb(_ACTIVE, _ACTIVE, 0)
            self._sleep_ms(120)
            self.off()
            self._sleep_ms(100)
        self.waiting()

    def error(self):
        self.set_rgb(_ACTIVE, 0, 0)
        self._sleep_ms(250)
        self.waiting()

    def deinit(self):
        self.off()
        for pwm in self._pwm.values():
            pwm.deinit()
        for pin in self._pins.values():
            pin.init(self._machine.Pin.OUT, value=0)
