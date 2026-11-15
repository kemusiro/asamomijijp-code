# SPDX-License-Identifier: MIT
# Silent GPIO-model allocation probe for MicroPython Unix (no audio/PIO).
# Prepare the method fixtures with prepare_bus_heap_probe.py first.
# This is a host verification tool: do not upload it to the physical Pico.
import sys

PINS = [None]*29
REGS = bytearray(256)
ADDRESS = 0
class Pin:
    IN, OUT = 0, 1
    def __init__(self,number,mode=None,pull=None,*,value=None):
        self.number, self.mode, self.level = number, self.IN, 0
        PINS[number] = self
        if mode is not None:
            self.init(mode,pull,value=value)
    def init(self,mode,pull=None,*,value=None):
        self.mode = mode
        if value is not None:
            self.level = value
    def value(self,value=None):
        global ADDRESS
        if value is not None:
            old = self.level
            self.level = value
            if self.number == 14 and old == 0 and value == 1 and not PINS[13].level:
                data = bit = 0
                while bit < 8:
                    data |= PINS[bit].level << bit
                    bit += 1
                if PINS[8].level:
                    REGS[ADDRESS] = data
                else:
                    ADDRESS = data
        elif self.number < 8:
            return (REGS[ADDRESS] >> self.number) & 1 if PINS[8].level else 0
        else:
            return self.level
I2S = I2C = SoftI2C = object
mem32 = {}

class Machine:
    Pin = Pin
    I2S = I2C = SoftI2C = object
    mem32 = {}
sys.modules["machine"] = Machine

import gc, sys
class Clock:
    us = 0
    @staticmethod
    def sleep_us(amount):
        Clock.us += amount
    @staticmethod
    def sleep_ms(amount):
        Clock.us += amount * 1000
    @staticmethod
    def ticks_us():
        return Clock.us
    @staticmethod
    def ticks_ms():
        return Clock.us // 1000
    @staticmethod
    def ticks_diff(a,b):
        return a-b
sys.modules["time"] = Clock
from _probe_target import PitchBus
print(sys.version)
bus = PitchBus()
bus.start()
COUNT = 128
def exercise(voice):
    for i in range(COUNT):
        bus.pitch_step(voice,i % 5,0)
        bus.pitch_step(voice,i % 5,1)
bad = 0
for voice in range(6):
    exercise(voice)  # warm import/attribute caches before measurement
    gc.collect()
    gc.disable()  # probe only, no PIO/audio is running; production keeps GC on
    before = gc.mem_alloc()
    try:
        exercise(voice)
        allocated = gc.mem_alloc()-before
    finally:
        gc.enable()
    print('BUS HEAP voice pairs bytes:',voice,COUNT,allocated)
    if allocated > 64:
        bad += 1
    gc.collect()
bus.close()
if bad:
    raise AssertionError('pitch GPIO path allocates per iteration')
print('PASS: all six actual pitch register paths use bounded heap; pairs per voice:',COUNT)
print('NOTE: this measures Python heap allocation, not physical GPIO timing, automatic GC latency or USB interrupt latency')
