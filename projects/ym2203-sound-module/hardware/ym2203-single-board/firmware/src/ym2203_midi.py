# SPDX-License-Identifier: MIT
"""Six monophonic MIDI channels;bounded planner shares the one-register budget."""
from ym2203_pitch import FM_HIGH,FM_LOW,SSG_PERIODS
import time
import ym2203_fw as fw

OFF = 255


def pitch_tables():
    return FM_HIGH,FM_LOW,SSG_PERIODS


def default_registers():
    # Initialized with all keys/SSG levels off,before starting audio capture.
    for channel in range(3):
        for slot in (0,4,8,12):
            for base,value in ((0x30,1),(0x40,0 if slot==0 else 127),(0x50,31),
                               (0x60,0),(0x70,0),(0x80,15),(0x90,0)):
                yield base+slot+channel,value
        yield 0xB0+channel,7
    yield 7,0x38


class Engine(fw.Engine):
    def __init__(self,board,clock=None):
        super().__init__(board,clock)
        self.midi = None

    def begin_stop(self,expired=False,failed=False):
        super().begin_stop(expired,failed)
        self.external_busy = False
        if self.midi is not None:self.midi.cancel()


class Controller:
    def __init__(self,engine,transport,clock=None):
        self.engine,self.transport = engine,transport
        self.clock = time if clock is None else clock
        self.high,self.low,self.period = pitch_tables()
        self.notes = bytearray((OFF,)*6)
        self.steps = bytearray((4,)*6)
        self.owned = False
        self.prime = self.cursor = self.silencing = 0
        self.release_at = self.io_since = self.io_voice = -1
        self.rejected = self.invalid = self.applied = 0
        engine.midi = self

    def cancel(self):
        self.owned = False
        self.engine.external_busy = False
        self.engine.midi_mask = 0
        self.prime = self.silencing = 0
        self.release_at = self.io_since = self.io_voice = -1
        i = 0
        while i<6:
            self.notes[i],self.steps[i] = OFF,4
            i += 1
        self.transport.discard()

    def panic(self):
        if self.owned:self.engine.begin_stop()
        else:self.transport.discard()

    def note(self,voice,note,on):
        if not on and (not self.owned or (note!=OFF and note!=self.notes[voice])):return
        if self.owned and self.io_voice==voice:
            self.engine.board.cancel_write()
            self.io_voice = -1  # retain BUSY deadline across replacement events
        if on:
            if (voice<3 and self.high[note]==OFF) or (voice>=3 and not self.period[note]):
                if self.owned:
                    self.notes[voice],self.steps[voice] = OFF,0
                    self.engine.midi_mask &= ~(1<<voice)
                return
            if not self.owned:
                e = self.engine
                if e.active or e.job or e.io_kind or e.queue.count or e.expired or e.failed:
                    self.rejected = (self.rejected+1)&65535
                    return
                self.owned = e.external_busy = True
                e.set_gates(0)
                # First silence all six voices,then allow12 audio blocks to
                # drain old buffered sound. Key-ons wait until priming ends.
                self.prime = fw.PRIME_BLOCKS
                self.silencing = 63
                i = 0
                while i<6:
                    self.notes[i],self.steps[i] = OFF,0
                    i += 1
            self.notes[voice],self.steps[voice] = note,0
            self.engine.midi_mask |= 1<<voice
            self.release_at = -1
        elif self.owned and (note==OFF or note==self.notes[voice]):
            self.notes[voice],self.steps[voice] = OFF,0
            self.engine.midi_mask &= ~(1<<voice)

    def message(self,buffer,index):
        cable,cin = buffer[index]>>4,buffer[index]&15
        if cable:return
        # Three-way tuple unpacking allocates in MicroPython;keep hot RX scalar.
        status = buffer[index+1]
        a = buffer[index+2]
        b = buffer[index+3]
        if cin==15 and status==255:
            self.panic()
            return
        if cin not in (8,9,11):return  # clock,SysEx,program/bend unsupported
        if status>>4!=cin or a>127 or b>127:
            self.invalid = (self.invalid+1)&65535
            self.panic()
            return
        voice = status&15
        if voice>=6:return
        if cin==11:
            if a==120:self.panic()  # device-wide immediate output mute
            elif a==123:self.note(voice,OFF,False)
        else:self.note(voice,a,cin==9 and b!=0)

    def poll(self):
        t,e = self.transport,self.engine
        t.service()
        e.midi_online = t.online
        if t.fault:
            t.fault = False
            self.panic()
        if t.online and t.count:
            index = t.offset
            t.offset += 4
            if t.offset==t.count:t.count = t.offset = 0
            self.message(t.buffer,index)
        if self.owned:
            if not self.silencing and self.prime:self.prime -= 1
            if not e.wrote:self.write_step()
            if self.owned and not self.prime and not self.silencing:
                if e.midi_mask:e.set_gates(3)
                else:
                    pending = False
                    i = 0
                    while i<6:
                        if self.steps[i]<4:pending = True
                        i += 1
                    if not pending:
                        now = self.clock.ticks_ms()
                        if self.release_at<0:self.release_at = now
                        elif self.clock.ticks_diff(now,self.release_at)>=135:
                            e.set_gates(0)
                            self.cancel()
        e.publish()
        t.arm()

    def write_step(self):
        e = self.engine
        voice = self.cursor
        searched = 0
        while searched<6:
            step = self.steps[voice]
            if step<4 and (not (self.prime or self.silencing) or step!=3 or self.notes[voice]==OFF):break
            voice = (voice+1)%6
            searched += 1
        if searched==6:return
        note = self.notes[voice]
        if voice<3:
            if step==0:reg,value = 0x28,voice
            elif step==1:reg,value = 0xA4+voice,self.high[note]
            elif step==2:reg,value = 0xA0+voice,self.low[note]
            else:reg,value = 0x28,0xF0|voice
        else:
            channel = voice-3
            if step==0:reg,value = 8+channel,0
            elif step==1:reg,value = 2*channel,self.period[note]&255
            elif step==2:reg,value = 2*channel+1,self.period[note]>>8
            else:reg,value = 8+channel,7
        if not e.board.write_register(reg,value):
            now = self.clock.ticks_ms()
            if self.io_since<0:self.io_since = now
            self.io_voice = voice
            if self.clock.ticks_diff(now,self.io_since)>=fw.IO_MS:e.fault(fw.IO_ERROR)
            return
        self.io_since = self.io_voice = -1
        if step==0:self.silencing &= ~(1<<voice)
        self.steps[voice] = 4 if note==OFF else step+1
        self.cursor = (voice+1)%6
        self.applied = (self.applied+1)&65535
