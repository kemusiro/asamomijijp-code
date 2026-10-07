import time

enabled = True


def setup():
    pass


def loop():
    total = 0
    if enabled:
        for i in range(3):
            total += i
            if i == 1:
                print("depth three stays Python", i)
    while total < 5:
        total += 1
    time.sleep(1)
