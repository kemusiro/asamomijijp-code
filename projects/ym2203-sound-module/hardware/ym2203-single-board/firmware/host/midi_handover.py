# SPDX-License-Identifier: MIT
"""USB-MIDI six-voice/I2C handover acceptance;run on the OTHER Pico.

First send/latch six MIDI voices using the browser,then run this HOST program.
This intentionally attaches without the normal constructor's automatic STOP.
"""
import time
from machine import Pin,I2C
from ym2203_revc import YM2203,MAGIC,ProtocolError

I2C_MS = 30000
WAIT_MIDI_MS = 90000
QUIET_MS = 4000


class Attached(YM2203):
    def __init__(self,i2c):
        self.i2c,self.address,self.clock = i2c,0x42,time
        if self._read(0,8)!=MAGIC:raise RuntimeError('Wrong Rev C identity')
        self.seq = self.status()[0]


def midi_state(chip):
    state = chip._read(0x14,3)
    if len(state)!=3 or state[0]>1 or state[1]>63 or state[2]>1:
        raise RuntimeError('Malformed MIDI ownership state:%r' % state)
    return state


def expect_midi(chip):
    state=chip.status();meta=midi_state(chip)
    if meta!=bytes((1,63,1)) or state[2]!=29 or state[3]!=0:
        raise RuntimeError('Expected six MIDI voices and gates on:state=%r meta=%r' % (state,meta))
    return state


def quiet(chip):
    started=time.ticks_ms()
    while True:
        state=chip.status();meta=midi_state(chip)
        if state[1:]!=bytes((0,1,0)) or meta!=bytes((0,0,1)):
            raise RuntimeError('Expected all-source quiet:state=%r meta=%r' % (state,meta))
        if time.ticks_diff(time.ticks_ms(),started)>=QUIET_MS:return
        time.sleep_ms(150)


def wait_for_six(chip):
    started=time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(),started)<WAIT_MIDI_MS:
        state=chip.status();meta=midi_state(chip)
        if state[2]&96 or not meta[2]:raise RuntimeError('USB offline or target fault')
        if meta==bytes((1,63,1)) and state[2]==29:
            time.sleep_ms(1200)
            expect_midi(chip)
            return
        time.sleep_ms(150)
    raise RuntimeError('Six-voice MIDI recovery timed out;no automatic replay')


def i2c_chord(chip):
    for channel in range(3):chip.pure_fm(channel)
    chip.ssg_bass()
    chip.write_registers(((0xA4,0x22),(0xA0,0x69),(0xA5,0x23),(0xA1,0x0A),
                         (0xA6,0x23),(0xA2,0x9D),(0x28,0x10),(0x28,0x11),
                         (0x28,0x12),(8,7),(9,7),(10,7)))
    chip.gates()
    started=time.ticks_ms();next_report=5000
    print('I2C PLAY /30 seconds of fixed six-voice chord')
    print('NOW: browser button2 sends FM+SSG scales for about15s;chord must stay unchanged')
    while time.ticks_diff(time.ticks_ms(),started)<I2C_MS:
        chip.keepalive()
        state=chip.status();meta=midi_state(chip)
        if state[1]!=0 or state[2]!=15 or state[3]!=0 or meta!=bytes((0,0,1)):
            raise RuntimeError('I2C ownership/gates changed:state=%r meta=%r' % (state,meta))
        elapsed=time.ticks_diff(time.ticks_ms(),started)
        if elapsed>=next_report:
            print('I2C HOLD elapsed_ms=%d /MIDI owner=0 mask=0' % elapsed)
            next_report+=5000
        time.sleep_ms(150)
    chip.stop()
    quiet(chip)
    print('PASS: I2C chord,stable ownership and4s quiet after STOP')


def main():
    chip=Attached(I2C(0,sda=Pin(0),scl=Pin(1),freq=10000,timeout=500000))
    try:
        print('YM2203 USB-MIDI six-voice/I2C handover HOST / OTHER Pico only')
        print('Browser must already have sent/latching all six MIDI voices')
        expect_midi(chip)
        time.sleep_ms(1200)
        expect_midi(chip)
        try:
            chip.write_registers(((0xA0,0),))
        except ProtocolError:
            state=expect_midi(chip)
            if state[0]!=chip.seq or state[1]!=3:
                raise RuntimeError('Expected acknowledged BUSY rejection')
        else:raise RuntimeError('I2C write was not rejected during MIDI ownership')
        print('PASS: MIDI six voices retain ownership;I2C WRITE rejected BUSY')
        chip.stop()
        quiet(chip)
        print('PASS: I2C STOP muted MIDI;4s read-only quiet,no spontaneous replay')
        i2c_chord(chip)
        print('WAIT FINAL MIDI / browser button3 sends six voices;within90s')
        wait_for_six(chip)
        print('PASS: explicit six-voice MIDI recovery after I2C release')
    finally:
        chip.stop()
    quiet(chip)
    state=chip.status();meta=midi_state(chip)
    print('FINAL STATE result=%d flags=%d queued=%d midi_owner=%d mask=%d usb=%d' %
          (state[1],state[2],state[3],meta[0],meta[1],meta[2]))
    print('HOST PASS: MIDI six voices,BUSY rejection,I2C STOP/hold/release and explicit MIDI recovery')
    print('DONE: report six solos/chord,unchanged I2C chord during MIDI send,L/R,distortion and final silence')


if __name__=='__main__':main()
