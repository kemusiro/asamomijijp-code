# SPDX-License-Identifier: MIT
"""Three-minute streaming acceptance run on the OTHER Pico,using alpha.2.

No target firmware change. Intentional melody rests; SSG accompaniment stays on.
The generator is replenished through the standard YM2203.stream() implementation.
"""
import time
from machine import Pin, I2C
from ym2203_revc import YM2203

CYCLES = 36
SLOT_MS = 500
PITCHES = ((0x22,0x69),(0x22,0xB5),(0x23,0x0A),(0x23,0x38),(0x23,0x9D))
SCORE = (0,2,None,4,None,2,1,None,0,None)
EXPECTED_EVENTS = 726
EXPECTED_SCORE_MS = 180000


def events():
    for reg in (8,9,10): yield 0,reg,7
    previous = None
    for cycle in range(CYCLES):
        for slot,note in enumerate(SCORE):
            delay = 0 if cycle == 0 and slot == 0 else SLOT_MS
            if note is None:
                yield delay,0x28,0
            else:
                high,low = PITCHES[note]
                yield delay,0xA4,high
                yield 0,0xA0,low
                if previous is None: yield 0,0x28,0x10
            previous = note
    # The final rest lasts a full slot; companions then turn off at180s.
    for reg in (8,9,10): yield SLOT_MS if reg == 8 else 0,reg,0


def counted_events(counts):
    for delay,reg,value in events():
        counts[0] += 1
        counts[1] += delay
        yield delay,reg,value


class ProgressPlayer(YM2203):
    def __init__(self,i2c,clock=None):
        self.play_started = None
        self.next_report = 30000
        super().__init__(i2c,clock=clock)

    def play(self):
        status = super().play()
        self.play_started = self.clock.ticks_ms()
        self.next_report = 30000
        return status

    def status(self):
        status = super().status()
        if self.play_started is not None:
            elapsed = self.clock.ticks_diff(self.clock.ticks_ms(),self.play_started)
            if self.next_report <= EXPECTED_SCORE_MS and elapsed >= self.next_report:
                print('STREAM %d/6 elapsed_ms=%d queued=%d seq=%d' %
                      (self.next_report//30000,elapsed,status[3],status[0]))
                self.next_report += 30000
        return status


def main():
    i2c = I2C(0,sda=Pin(0),scl=Pin(1),freq=10000,timeout=500000)
    chip = ProgressPlayer(i2c)
    counts = [0,0]
    elapsed = 0
    try:
        chip.pure_fm()
        chip.ssg_bass()
        print('YM2203 alpha.2 / three-minute streaming HOST / OTHER Pico only')
        print('FM C E REST G REST E D REST C REST + held SSG chord;36 cycles')
        print('Score180000ms /726 events / ring128; progress every30s;volumes low')
        started = time.ticks_ms()
        chip.stream(counted_events(counts))
        elapsed = time.ticks_diff(time.ticks_ms(),started)
        if counts != [EXPECTED_EVENTS,EXPECTED_SCORE_MS]:
            raise RuntimeError('Incomplete streaming source:events=%d score_ms=%d' %
                               (counts[0],counts[1]))
    finally:
        chip.stop()
    state = chip.status()
    if state[1] != 0 or state[2] != 1 or state[3] != 0:
        raise RuntimeError('Final state is not stopped/ready:%r' % state)
    print('STREAM COMPLETE events=%d score_ms=%d host_elapsed_ms=%d' %
          (counts[0],counts[1],elapsed))
    print('FINAL STATE seq=%d result=%d flags=%d queued=%d' %
          (state[0],state[1],state[2],state[3]))
    print('HOST PASS: three-minute replenished score,normal end and explicit STOP')
    print('DONE: report L/R,melody rests,held chord,unplanned gaps/distortion and final silence')


if __name__ == '__main__': main()
