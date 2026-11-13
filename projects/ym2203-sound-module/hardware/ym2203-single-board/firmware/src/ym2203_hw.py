# SPDX-License-Identifier: MIT
"""Physical RP2350 Rev C adapter;boot stays muted until explicit host action."""
import gc
import time
from machine import Pin, I2S
from rev_c_bus_check import RevCBus, I2S_OUTPUT_GPIO, _check_platform, _emergency_stop
import rev_c_i2c_target_check as link
import rev_c_dac_check as dac
import rev_c_fm_live as verified
import ym2203_audio as audio_core
import ym2203_fw as fw
import ym2203_midi as midi_core
import ym2203_usb as usb_core


class Board(RevCBus):
    def __init__(self):
        super().__init__()
        self.latched = -1

    def cancel_write(self):
        self.latched = -1

    def write_register(self, reg, value):
        # Never wait100ms for BUSY while the audio deadline is11.25ms.
        # Retry this same transaction on the next audio opportunity instead.
        if self.status() & 128: return False
        if self.latched < 0:
            self._write_port(0,reg)
            self.latched = reg
            if self.status() & 128: return False
        elif self.latched != reg:
            raise RuntimeError("YM register address ownership lost")
        self._write_port(1,value)
        self.latched = -1
        return True

    def initialize(self):
        self.start()
        for reg,value in ((0x27,0),(0x28,0),(0x28,1),(0x28,2),(8,0),(9,0),(10,0),(7,63)):
            self.startup_write(reg,value)
        for reg,value in midi_core.default_registers():self.startup_write(reg,value)

    def startup_write(self,reg,value):
        started = time.ticks_ms()
        while not self.write_register(reg,value):
            if time.ticks_diff(time.ticks_ms(),started) >= 100:
                raise RuntimeError("YM startup BUSY timeout")
            time.sleep_ms(1)


class Target(link.Target):
    def __init__(self, engine):
        super().__init__()
        self.window = fw.Window(engine)

    def poll(self):
        # Same v1.1 TX-before-CLR_RD_REQ ordering,with bounded RX work.
        raw = link.mem32[link.IC_RAW_INTR_STAT]
        if raw & link.FIFO_ERRORS: raise RuntimeError("I2C FIFO error")
        if raw & link.TX_ABRT:
            source = link.mem32[link.IC_TX_ABRT_SOURCE]
            unused = link.mem32[link.IC_CLR_TX_ABRT]
            if source & 0x1FFFF != 0x2000: raise RuntimeError("I2C TX abort")
            self.flushes = (self.flushes+1) & 65535
        budget = 32
        while budget and link.mem32[link.IC_RXFLR]:
            word = link.mem32[link.IC_DATA_CMD]
            self.window.receive(word & 255,word & link.FIRST_BYTE)
            budget -= 1
        if link.mem32[link.IC_RXFLR]: return
        if raw & link.RD_REQ:
            burst = 4 if self.window.pointer == 0x10 else 1
            while burst:
                link.mem32[link.IC_DATA_CMD] = self.window.next_byte()
                burst -= 1
            unused = link.mem32[link.IC_CLR_RD_REQ]
        if raw & link.RX_DONE: unused = link.mem32[link.IC_CLR_RX_DONE]
        if raw & link.STOP_DET: unused = link.mem32[link.IC_CLR_STOP_DET]
        if raw & link.RESTART_DET: unused = link.mem32[link.IC_CLR_RESTART_DET]


def run():
    _check_platform()
    bus = stream = audio = target = reserve = None
    midi = transport = None
    mute_line = disarm = None
    try:
        reserve = bytearray(4096)
        gc.enable()
        bus = Board()
        mute_line,disarm = bus.line_allow.value,bus.arm.value
        bus.initialize()
        pcm = bytearray(verified.OUTPUT_FRAMES*4)
        silence = bytearray(1920)
        stream = audio_core.Stream()
        stream.open()
        sd,sck,ws = I2S_OUTPUT_GPIO
        audio = I2S(0,sck=Pin(sck),ws=Pin(ws),sd=Pin(sd),mode=I2S.TX,
                    bits=16,format=I2S.STEREO,rate=48000,ibuf=16384)
        dac._send(audio,silence,100)
        stream.start()
        for unused in range(4):
            if audio_core.step(stream,pcm,audio) > 64:
                raise RuntimeError("FM boot key-off is not silent")
        stream.stop()
        transport = usb_core.get_transport()
        engine = midi_core.Engine(bus) if transport is not None else fw.Engine(bus)
        if transport is not None:midi = midi_core.Controller(engine,transport)
        target = Target(engine)
        target.prepare()
        target._enable(1)
        gc.collect()
        print("YM2203 Rev C firmware",fw.VERSION,"READY I2C=0x42;outputs muted")
        if transport is not None:transport.start()
        stream.start()
        while True:
            stream.check()
            target.poll()
            idle = not link.mem32[link.IC_STATUS] & 0x40
            if idle:
                if target.window.bad_frame:
                    engine.result = fw.CRC_ERROR
                    engine.publish()
                    target.window.bad_frame = False
                if target.window.pending:
                    engine.accept(target.window.frame)
                    target.window.pending = False
                    target.window.mask = 0
            engine.poll(idle)
            if midi is not None:midi.poll()
            stream.check()
            audio_core.step(stream,pcm,audio)
    finally:
        # Prebound C methods work before any exception/GC/console allocation.
        if mute_line is not None: mute_line(0)
        if disarm is not None: disarm(0)
        if transport is not None:transport.stop()
        try:
            if bus is None: _emergency_stop()
            else: bus.close()
        finally:
            try:
                if stream is not None: stream.close()
            finally:
                try:
                    if target is not None: target.close()
                finally:
                    if audio is not None: audio.deinit()
                    reserve = None
                    gc.collect()
                    print("YM2203 SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0")
