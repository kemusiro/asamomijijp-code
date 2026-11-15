# SPDX-License-Identifier: MIT
"""Final alpha.2 STOP/lease/rebind acceptance run on the OTHER Pico.

Release HOST GP0/GP1 only between completed transfers. No target reset, cable
change or bus-stuck/mid-frame fault injection. Uses the installed host driver.
"""
import time
from machine import Pin, I2C
from ym2203_revc import YM2203, MAGIC

PITCHES = ((0x22,0x69),(0x22,0xB5),(0x23,0x0A),(0x23,0x38),(0x23,0x9D))
SCORE = (0,1,2,3,4,3,2,1,0)
QUIET_MS = 4000
RELEASE_MS = 1800


def make_i2c():
    return I2C(0,sda=Pin(0),scl=Pin(1),freq=10000,timeout=500000)


def events():
    for reg in (8,9,10): yield 0,reg,7
    for index,note in enumerate(SCORE):
        high,low = PITCHES[note]
        yield 0 if index == 0 else 500,0xA4,high
        yield 0,0xA0,low
        if index == 0: yield 0,0x28,0x10
    yield 500,0x28,0
    for reg in (8,9,10): yield 0,reg,0


def stopped(chip,expired=False,seq=None):
    state = chip.status()
    expected_result = 5 if expired else 0
    expected_flags = 33 if expired else 1
    if (state[1] != expected_result or state[2] != expected_flags or
            state[3] != 0 or (seq is not None and state[0] != seq)):
        raise RuntimeError('Stopped/lease state mismatch:expected result=%d flags=%d seq=%r actual=%r' %
                           (expected_result,expected_flags,seq,state))
    return state


def quiet(chip,expired=False):
    first = stopped(chip,expired)
    started = time.ticks_ms()
    # Reads only: no KEEP,STOP,PLAY or score writes in this interval.
    while time.ticks_diff(time.ticks_ms(),started) < QUIET_MS:
        time.sleep_ms(150)
        stopped(chip,expired,seq=first[0])
    return first


def start_partial(chip):
    chip.stop()
    chip.enqueue(events())
    chip.seal()
    chip.play()
    started = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(),started) < 1200:
        chip.keepalive()
        time.sleep_ms(150)
    state = chip.status()
    # Active + DAC/LINE on,normal result,and events still pending.
    if state[1] != 0 or state[2] & ~16 != 143 or state[3] == 0:
        raise RuntimeError('Expected active,partially played score:%r' % state)
    return state


def main():
    chip = YM2203(make_i2c())
    released = False
    try:
        chip.pure_fm()
        chip.ssg_bass()
        print('YM2203 alpha.2 / final STOP-reconnect HOST / OTHER Pico only')
        print('FM C D E F G F E D C + held SSG chord;start volumes low')
        print('1/4 PARTIAL PLAY then STOP;expect all voices off and4s quiet')
        start_partial(chip)
        chip.stop()
        state = quiet(chip)
        print('1/4 PASS STOP / result=%d flags=%d queued=%d /4s read-only quiet' %
              (state[1],state[2],state[3]))
        print('2/4 EXPLICIT REPLAY / upload same score,all9 notes from C')
        chip.stream(events())
        stopped(chip)
        print('2/4 PASS complete score and normal end')
        print('3/4 PARTIAL PLAY then HOST pins released;auto-mute in about1s')
        start_partial(chip)
        chip.keepalive()
        before = chip.status()
        print('HOST RELEASE / no I2C for1800ms;no KEEP,STOP or reads')
        # Set before touching either mux so cleanup also handles interruption
        # between the two pin changes or during the deliberate communication gap.
        released = True
        Pin(0,Pin.IN,pull=None)
        Pin(1,Pin.IN,pull=None)
        time.sleep_ms(RELEASE_MS)
        chip.i2c = make_i2c()
        released = False
        # Retain the SAME client and sequence. Its constructor would send STOP
        # and hide the expiry we need to inspect here.
        if chip._read(0,8) != MAGIC:
            raise RuntimeError('Reattached target identity mismatch')
        state = stopped(chip,expired=True,seq=before[0])
        print('REBIND / seq=%d result=%d flags=%d queued=%d / expect4s quiet' %
              (state[0],state[1],state[2],state[3]))
        quiet(chip,expired=True)
        print('3/4 PASS lease cleanup,same target sequence,read-only reattachment stayed muted')
        chip.stop()
        stopped(chip)
        print('4/4 RECOVERY / explicit STOP clears lease,upload+PLAY all9 notes from C')
        chip.stream(events())
        stopped(chip)
        print('4/4 PASS full recovery score and normal end')
    finally:
        if released:
            chip.i2c = make_i2c()
        chip.stop()
    state = stopped(chip)
    print('FINAL STATE seq=%d result=%d flags=%d queued=%d' %
          (state[0],state[1],state[2],state[3]))
    print('HOST PASS: STOP,4s quiet,replay,HOST release,lease mute,quiet rebind and explicit recovery')
    print('DONE: report both full scales,partial stops,auto-mute,L/R,distortion and final silence')


if __name__ == '__main__':main()
