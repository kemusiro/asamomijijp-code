# SPDX-License-Identifier: MIT
"""Shared CPython/MicroPython model;not a physical timing or audio emulator."""
import ym2203_fw as fw
import ym2203_revc as host

class Clock:
    PERIOD = 1 << 30
    def __init__(self): self.us = 0; self.next_tick = 11250; self.service = None
    def ticks_ms(self): return (self.us//1000) % self.PERIOD
    def ticks_us(self): return self.us % self.PERIOD
    def ticks_add(self,t,n): return (t+n) % self.PERIOD
    def ticks_diff(self,a,b): return ((a-b+self.PERIOD//2) % self.PERIOD)-self.PERIOD//2
    def advance(self,us,idle=True):
        end = self.us+us
        while self.next_tick <= end:
            self.us = self.next_tick; self.next_tick += 11250
            if self.service: self.service(idle)
        if self.us < end: self.us = end  # service work must not rewind time
    def sleep_ms(self,ms): self.advance(ms*1000)


class Pin:
    def __init__(self): self.level = 0
    def value(self,n): self.level = n


class Board:
    def __init__(self,clock):
        self.clock = clock; self.line_allow = Pin(); self.dac_allow = Pin()
        self.calls = []; self.regs = bytearray(256); self.blocked = False; self.cancels = 0
    def write_register(self,r,v):
        if self.blocked: return False
        self.calls.append((self.clock.us,r,v)); self.regs[r] = v
        return True
    def cancel_write(self): self.cancels += 1


class Wire:
    def __init__(self):
        self.clock = Clock(); self.board = Board(self.clock)
        self.engine = fw.Engine(self.board,self.clock); self.window = fw.Window(self.engine)
        self.transfers = []; self.trace_transfers = True; self.fail = None
        self.clock.service = self.service
    def service(self,idle):
        if idle and self.window.bad_frame:
            self.engine.result = fw.CRC_ERROR; self.engine.publish(); self.window.bad_frame = False
        if idle and self.window.pending:
            self.engine.accept(self.window.frame); self.window.pending = False; self.window.mask = 0
        before = len(self.board.calls); self.engine.poll(idle)
        assert len(self.board.calls)-before <= 1
    def writeto(self,address,data):
        assert address == 0x42
        if self.trace_transfers: self.transfers.append(bytes(data))
        if self.fail and self.fail(data): raise OSError('injected I2C failure')
        for i,value in enumerate(data): self.window.receive(value,i == 0)
        self.clock.advance(len(data)*900,False)
        return len(data)
    def readfrom(self,address,count):
        assert address == 0x42
        data = bytes(self.window.next_byte() for unused in range(count))
        self.clock.advance(count*900,False)
        return data
    def client(self): return host.YM2203(self,clock=self.clock)

