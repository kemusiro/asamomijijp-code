# Conversion input, not a standalone device program. Initialization comes from the template.
import time


def setup():
    rgb_0.fill_color(0xff0000)
    time.sleep(2)


def loop():
    rgb_0.fill_color(0x33ff33)
    time.sleep(1)
    rgb_0.fill_color(0x000000)
    time.sleep(1)
