# SPDX-License-Identifier: MIT
"""Unix MicroPython v1.29 heap probe; GPIO, clocks and I2C are models.

Run with firmware/src on MICROPYPATH. This does not run on the target Pico.
A minimal Unix build needs array and gc.mem_alloc enabled; time is mocked.
"""
import sys
sys.modules['time'] = sys
import gc
import ym2203_fw as fw

class Clock:
    def ticks_ms(self): return 0
    def ticks_diff(self,a,b): return a-b
    def ticks_add(self,a,b): return a+b
class Pin:
    def value(self,n): pass
class Board:
    def __init__(self): self.line_allow=Pin();self.dac_allow=Pin()
    def cancel_write(self): pass
    def write_register(self,r,v): return True

def measure():
    engine=fw.Engine(Board(),Clock())
    packet=bytearray(16)
    packet[0]=1;packet[2]=fw.PUSH;packet[3]=4;packet[6]=0xA0;packet[7]=1
    engine.active=engine.running=True
    def exercise():
        for unused in range(1000):
            packet[1]=(engine.seq+1)&255
            crc=fw.crc16(packet)
            packet[14]=crc&255;packet[15]=crc>>8
            engine.accept(packet)
            engine.poll()
    exercise()
    gc.collect();gc.disable()
    before=gc.mem_alloc()
    try:
        exercise()
        growth=gc.mem_alloc()-before
    finally: gc.enable()
    print(sys.version)
    print('ENGINE HEAP: CRC,accept,queue,register,status;1000 frames;bytes:',growth)
    assert growth<=64 and engine.executed==2000 and engine.queue.count==0
    print('PASS: bounded small-int heap probe;physical GPIO/audio and USB latency untested')
measure()
