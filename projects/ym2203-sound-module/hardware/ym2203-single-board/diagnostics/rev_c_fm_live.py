# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Bounded live FM -> PCM -> I2S diagnostic for physical Rev C/Pico 2 Arm.

Two bounded DMA buffers, native conversion, and fail-closed deadline checks.
No replayed period or generated substitute waveform is used. Import is silent.
"""
import gc
import time
from machine import Pin
import micropython
from rev_c_bus_check import I2S_OUTPUT_GPIO, _check_platform, _diagnose, _emergency_stop
from rev_c_fm_capture import RevCFMBus
from rev_c_dac_check import _send, _write


INPUT_FRAMES = 625
OUTPUT_FRAMES = 540  # 55,555.555... -> 48,000 Hz, ratio 125:108
BLOCK_US = 11250
RATE = 48000
IBUF = 16384
PIO_SM = 0
DREQ_RX = 4
FDEBUG = 0x50200008
RXSTALL = 1
DMA_ERROR_SHIFT = 29
RING_BYTES = 4096
NOTE_BLOCKS = 49  # about 551 ms
GAP_BLOCKS = 89  # about 1 second
ROUNDS = 2
PITCHES = (("C4", 0x22, 0x69), ("D4", 0x22, 0xB5), ("E4", 0x23, 0x0A),
           ("F4", 0x23, 0x38), ("G4", 0x23, 0x9D))
MELODY = (0, 1, 2, 3, 4, 3, 2, 1, 0)


@micropython.viper
def convert(source: ptr32, destination: ptr16) -> int:
    # Each word contains 24 serial bits in bits 8..31: valid last13 in 19..31.
    # This function's caller guarantees >=625 uint32 input and 1080 uint16 output.
    position = 0
    flags = 0
    peak = 0
    for i in range(540):
        index = position // 108
        fraction = position % 108
        wa = (int(source[index]) >> 19) & 8191
        wb = (int(source[index + 1]) >> 19) & 8191
        ea = wa >> 10
        eb = wb >> 10
        value = 0
        if ea == 0 or eb == 0:
            flags |= 1
        else:
            a = ((wa & 1023) - 512) << (ea - 1)
            b = ((wb & 1023) - 512) << (eb - 1)
            # Fixed gain 32: the verified TL48 carrier reaches about 4064/32768.
            value = ((a * (108 - fraction) + b * fraction) * 32) // 108
            if value > 4096:
                flags |= 2
                value = 4096
            if value < -4096:
                flags |= 2
                value = -4096
        magnitude = value
        if magnitude < 0:
            magnitude = -magnitude
        if magnitude > peak:
            peak = magnitude
        destination[2 * i] = value & 65535
        destination[2 * i + 1] = 0
        position += 125
    return peak | (flags << 16)


def program(rp2):
    @rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT, autopush=True, push_thresh=24)
    def receive():
        wrap_target()
        wait(1, gpio, 18)
        wait(0, gpio, 18)
        set(x, 23)
        label("bits")
        wait(0, gpio, 17)
        wait(1, gpio, 17)
        in_(pins, 1)
        jmp(x_dec, "bits")
        wrap()
    return receive


class LiveBus(RevCFMBus):
    def pitch(self, note):
        if type(note) is not int or not 0 <= note < len(PITCHES):
            raise ValueError("Choose one of the five diagnostic pitches")
        name, high, low = PITCHES[note]
        # Only these two selected channel-1 pitch bytes extend the prior allow-list.
        for register, value in ((0xA4, high), (0xA0, low)):
            self.wait_ready()
            self._write_port(0, register)
            self.wait_ready()
            self._write_port(1, value)
            self.wait_ready()


class Stream:
    def __init__(self):
        self.sm = None
        self.dmas = []
        self.storage = []
        self.buffers = []
        self.mem32 = None
        self.sequence = 0
        self.started = 0
        self.running = False
        self.deadline_misses = 0
        self.max_convert_us = 0

    def open(self):
        import rp2
        from machine import mem32
        from uctypes import addressof
        self.mem32 = mem32
        # Hardware address rings keep every DMA write inside its own allocation,
        # even if Python/USB pauses so long that a stale channel is retriggered.
        for unused in range(2):
            storage = bytearray(2 * RING_BYTES)
            offset = (-addressof(storage)) & (RING_BYTES - 1)
            self.storage.append(storage)
            self.buffers.append(memoryview(storage)[offset:offset + RING_BYTES])
        self.sm = rp2.StateMachine(PIO_SM, program(rp2), freq=32000000, in_base=Pin(16))
        self.dmas.append(rp2.DMA())
        self.dmas.append(rp2.DMA())
        for i in range(2):
            ctrl = self.dmas[i].pack_ctrl(
                size=2, inc_read=False, inc_write=True, treq_sel=DREQ_RX,
                chain_to=self.dmas[1 - i].channel, ring_size=12, ring_sel=True,
                high_pri=True, bswap=False
            )
            self.dmas[i].config(read=self.sm, write=self.buffers[i], count=INPUT_FRAMES, ctrl=ctrl)

    def start(self):
        self.stop()
        self.sm.restart()
        while self.sm.rx_fifo():
            self.sm.get()
        self.mem32[FDEBUG] = RXSTALL
        for i in range(2):
            self.dmas[i].config(write=self.buffers[i], count=INPUT_FRAMES)
        self.sequence = 0
        self.started = time.ticks_us()
        self.running = True
        self.dmas[0].active(1)
        self.sm.active(1)

    def check(self):
        if not self.running:
            raise RuntimeError("FM stream is not running")
        elapsed = time.ticks_diff(time.ticks_us(), self.started)
        if elapsed >= (self.sequence + 2) * BLOCK_US - 500:
            self.deadline_misses += 1
            raise RuntimeError("FM stream deadline missed; audio stopped")
        if self.mem32[FDEBUG] & RXSTALL:
            raise RuntimeError("FM receive FIFO stalled; audio stopped")
        # A 0xE0000000 mask invokes allocating big-int arithmetic on MicroPython.
        # Both normal status words and these shifted error bits fit small ints.
        if self.dmas[0].ctrl >> DMA_ERROR_SHIFT or self.dmas[1].ctrl >> DMA_ERROR_SHIFT:
            raise RuntimeError("FM DMA bus error; audio stopped")

    def take(self):
        index = self.sequence & 1
        while self.dmas[index].active():
            self.check()
            time.sleep_us(50)
        self.check()
        if not self.dmas[1 - index].active():
            raise RuntimeError("FM DMA chain stopped")
        return self.buffers[index]

    def release(self):
        self.check()
        index = self.sequence & 1
        if self.dmas[index].active() or not self.dmas[1 - index].active():
            raise RuntimeError("FM buffer ownership lost")
        self.dmas[index].config(write=self.buffers[index], count=INPUT_FRAMES)
        self.sequence += 1

    def stop(self):
        self.running = False
        try:
            if self.sm is not None:
                self.sm.active(0)
        finally:
            for dma in self.dmas:
                dma.active(0)

    def close(self):
        try:
            self.stop()
        finally:
            for dma in self.dmas:
                dma.close()
            self.dmas = []


def step(stream, pcm, audio):
    source = stream.take()
    started = time.ticks_us()
    result = convert(source, pcm)
    elapsed = time.ticks_diff(time.ticks_us(), started)
    if elapsed > stream.max_convert_us:
        stream.max_convert_us = elapsed
    # Validate ownership before queuing any audio made from this buffer.
    stream.check()
    if result >> 16:
        raise RuntimeError("FM conversion invalid exponent or level exceeded: 0x%X" % result)
    stream.release()
    _write(audio, pcm)
    return result & 65535


def scale_sequence(bus, stream, pcm, audio, silence):
    bus.dac_allow.value(1)
    for repetition in range(ROUNDS):
        bus.pitch(0)
        bus.write_fm(0x28, 0x10)
        stream.start()
        for unused in range(4):
            step(stream, pcm, audio)
        bus.line_allow.value(1)
        for note in MELODY:
            bus.pitch(note)
            print("LIVE %d/%d / %s" % (repetition + 1, ROUNDS, PITCHES[note][0]))
            for unused in range(NOTE_BLOCKS):
                step(stream, pcm, audio)
        bus.write_fm(0x28, 0)
        # Drain the chip's release and the independent I2S output queue.
        for unused in range(20):
            step(stream, pcm, audio)
        bus.line_allow.value(0)
        for unused in range(GAP_BLOCKS):
            step(stream, pcm, audio)
        stream.stop()


def run(sequence=None, bus_factory=None, title=None, description=None, completion=None,
        connection_message=None):
    _check_platform()
    print(title or "YM2203 Rev C / live FM scale v1.1")
    print(connection_message or "Host I2C disconnected; both volumes low. This test WILL produce live FM.")
    bus = stream = audio = None
    reserve = None
    mute_line = disarm = None
    was_gc_enabled = gc.isenabled()
    try:
        reserve = bytearray(4096)  # released before recovery if memory runs low
        gc.enable()
        bus = LiveBus() if bus_factory is None else bus_factory()
        # Prebind the two C pin methods while memory is available. They can mute
        # the board before diagnostics/cleanup allocate anything on an OOM path.
        mute_line = bus.line_allow.value
        disarm = bus.arm.value
        _diagnose(bus)
        bus.prepare()
        pcm = bytearray(OUTPUT_FRAMES * 4)
        silence = bytearray(RATE // 100 * 4)
        stream = Stream()
        stream.open()
        from machine import I2S
        sd, sck, ws = I2S_OUTPUT_GPIO
        audio = I2S(0, sck=Pin(sck), ws=Pin(ws), sd=Pin(sd), mode=I2S.TX,
                    bits=16, format=I2S.STEREO, rate=RATE, ibuf=IBUF)
        _send(audio, silence, 100)
        gc.collect()
        # Same new receiver and resampler run while both output gates stay low.
        stream.start()
        for unused in range(4):
            if step(stream, pcm, audio) > 64:
                raise RuntimeError("Live receiver key-off is not near zero")
        bus.write_fm(0x28, 0x10)
        peak = 0
        for unused in range(12):
            peak = max(peak, step(stream, pcm, audio))
        if peak < 512:
            raise RuntimeError("Live receiver did not detect key-on signal")
        bus.write_fm(0x28, 0)
        for i in range(40):
            value = step(stream, pcm, audio)
            if i >= 30 and value > 64:
                raise RuntimeError("Live receiver did not return to silence")
        stream.stop()
        gc.collect()  # stream stopped, audio still muted
        print("PASS: new serial receiver and live conversion preflight; peak=%d free=%d" %
              (peak, gc.mem_free()))
        print(description or "C D E F G F E D C, twice. Sound starts in about 5 seconds.")
        _send(audio, silence, 5000)
        if sequence is None:
            scale_sequence(bus, stream, pcm, audio, silence)
        else:
            sequence(bus, stream, pcm, audio, silence)
        bus.dac_allow.value(0)
        print("PASS: live sequence sent; max conversion=%d us, deadline misses=%d" %
              (stream.max_convert_us, stream.deadline_misses))
    except BaseException:
        if mute_line is not None:
            mute_line(0)
        if disarm is not None:
            disarm(0)
        reserve = None
        gc.enable()
        gc.collect()
        print("FAIL or interrupted. Save the FULL log before retrying.")
        raise
    finally:
        if mute_line is not None:
            mute_line(0)
        if disarm is not None:
            disarm(0)
        reserve = None
        gc.enable()
        gc.collect()
        try:
            if bus is None:
                _emergency_stop()
            else:
                bus.close()
        finally:
            try:
                if stream is not None:
                    stream.close()
            finally:
                try:
                    if audio is not None:
                        audio.deinit()
                finally:
                    for gpio in I2S_OUTPUT_GPIO:
                        Pin(gpio, Pin.OUT, pull=None, value=0)
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped")
        if not was_gc_enabled:
            gc.disable()
    print(completion or "DONE: report both scales on L/R, pitch changes, gaps, and any clicks/dropouts.")


if __name__ == "__main__":
    run()
