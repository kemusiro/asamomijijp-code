import time

counter = 0


def announce(value):
    print("counter:", value)


def setup():
    rgb_0.fill_color(0xff0000)
    time.sleep(1)
    announce(counter)


def loop():
    global counter
    if M5.Touch.getCount():
        counter += 1
        announce(counter)
        rgb_0.fill_color(0x0033ff)
    else:
        rgb_0.fill_color(0x000000)
    time.sleep_ms(100)


if __name__ == '__main__':
    setup()
    while True:
        loop()
