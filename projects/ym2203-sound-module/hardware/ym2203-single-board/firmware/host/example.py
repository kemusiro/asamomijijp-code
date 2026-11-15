# SPDX-License-Identifier: MIT
"""Run on the OTHER Pico:FM melody+SSG chord,streamed through protocol v1."""
from machine import Pin, I2C
from ym2203_revc import YM2203

PITCHES = ((0x22,0x69),(0x22,0xB5),(0x23,0x0A),(0x23,0x38),(0x23,0x9D))
SCORE = (0,2,None,4,None,2,1,None,0)


def events(repeats):
    for reg in (8,9,10): yield 0,reg,7
    previous = None
    for repetition in range(repeats):
        for index,note in enumerate(SCORE):
            delay = 0 if repetition == 0 and index == 0 else 150 if index == 0 else 500
            if note is None:
                yield delay,0x28,0
            else:
                high,low = PITCHES[note]
                yield delay,0xA4,high
                yield 0,0xA0,low
                if previous is None: yield 0,0x28,0x10
            previous = note
        yield 500,0x28,0
        previous = None
    for reg in (8,9,10): yield 0,reg,0


def main():
    i2c = I2C(0,sda=Pin(0),scl=Pin(1),freq=10000,timeout=500000)
    chip = YM2203(i2c)
    try:
        chip.pure_fm()
        chip.ssg_bass()
        print("Rev C firmware v0.1:FM melody+SSG chord,two repeats;start volumes low")
        chip.stream(events(2))
        print("Playback complete;all voices stopped")
    finally:
        chip.stop()


if __name__ == "__main__": main()
