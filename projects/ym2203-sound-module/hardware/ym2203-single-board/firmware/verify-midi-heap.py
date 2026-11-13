# SPDX-License-Identifier: MIT
"""Unix MicroPython1.29 MIDI hot-path heap probe;USB/GPIO/time are models.

Use firmware/src on MICROPYPATH. Imports the unmodified MIDI/USB sources.
No audio runs while GC is disabled for allocation measurement.
"""
import sys
sys.modules['time']=sys
class Machine:
    USBDevice=object
    mem32={}
sys.modules['machine']=Machine
import gc
import ym2203_midi as midi
import ym2203_usb as usb

class Clock:
    us=0
    def ticks_ms(self):return self.us//1000
    def ticks_diff(self,a,b):return a-b
    def ticks_add(self,a,b):return a+b
class Pin:
    def value(self,n):pass
class Board:
    def __init__(self):self.line_allow=Pin();self.dac_allow=Pin()
    def cancel_write(self):pass
    def write_register(self,r,v):return True
class Device:
    def submit_xfer(self,ep,buffer):return True
class Registers:
    def __init__(self,clock):self.clock=clock
    def __getitem__(self,address):return (self.clock.us//1000)&2047

def measure():
    clock=Clock();engine=midi.Engine(Board(),clock)
    transport=usb.Transport(Device(),2,3,clock,Registers(clock))
    control=midi.Controller(engine,transport,clock)
    transport.opened=True;transport.start()
    def tick():
        clock.us+=11250
        engine.poll()
        control.poll()
    def exercise():
        for cycle in range(100):
            transport.buffer[0]=9;transport.buffer[1]=0x90|(cycle%6)
            transport.buffer[2]=60;transport.buffer[3]=100
            transport.xfer_cb(3,0,4)
            for unused in range(40):tick()
            transport.buffer[0]=8;transport.buffer[1]=0x80|(cycle%6)
            transport.xfer_cb(3,0,4)
            for unused in range(30):tick()
    exercise()
    gc.collect();gc.disable();before=gc.mem_alloc()
    try:
        exercise()
        growth=gc.mem_alloc()-before
    finally:gc.enable()
    print(sys.version)
    print('MIDI HEAP:100 note pairs across all6 voices,7000 USB/core/planner ticks;bytes:',growth)
    assert growth<=64 and not control.owned and engine.gates==0
    print('PASS: actual MIDI/USB Python hot paths bounded;physical callbacks/GPIO/USB interrupt latency unmeasured')
measure()
