# SPDX-License-Identifier: MIT
"""Validated PIO/DMA receiver with rolling deadlines and full-range FM scaling."""
import time
import micropython
import rev_c_fm_live as verified


@micropython.viper
def convert(source: ptr32, destination: ptr16) -> int:
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
            # The complete YM floating-point range fits in +/-4096 at 1/8.
            # Preserve the commissioned PCM output cap without clipping normal
            # TL0 patches. Diagnostic gain32 was for deliberately quiet TLs.
            value = (a * (108 - fraction) + b * fraction) // 864
            if value > 4096:
                flags |= 2
                value = 4096
            if value < -4096:
                flags |= 2
                value = -4096
        magnitude = value
        if magnitude < 0: magnitude = -magnitude
        if magnitude > peak: peak = magnitude
        destination[2*i] = value & 65535
        destination[2*i+1] = 0
        position += 125
    return peak | (flags << 16)


class Stream(verified.Stream):
    def start(self):
        verified.Stream.start(self)
        self.deadline = time.ticks_add(self.started,2*verified.BLOCK_US-500)

    def check(self):
        if not self.running: raise RuntimeError("FM stream is not running")
        if time.ticks_diff(time.ticks_us(),self.deadline) >= 0:
            self.deadline_misses += 1
            raise RuntimeError("FM stream deadline missed;audio stopped")
        if self.mem32[verified.FDEBUG] & verified.RXSTALL:
            raise RuntimeError("FM receive FIFO stalled;audio stopped")
        if self.dmas[0].ctrl >> 29 or self.dmas[1].ctrl >> 29:
            raise RuntimeError("FM DMA bus error;audio stopped")

    def release(self):
        self.check()
        index = self.sequence & 1
        if self.dmas[index].active() or not self.dmas[1-index].active():
            raise RuntimeError("FM buffer ownership lost")
        self.dmas[index].config(write=self.buffers[index],count=verified.INPUT_FRAMES)
        # An even modulus preserves the ping-pong index indefinitely. No
        # sequence*microseconds products or growing big ints in the hot loop.
        self.sequence = (self.sequence+1) & 65535
        # Re-anchor after a verified DMA handoff. The YM oscillator and
        # MCU timer can drift; adding nominal periods forever would eventually
        # cause a false deadline failure. DMA ownership/stall checks still guard
        # an overdue handoff before re-anchoring.
        self.deadline = time.ticks_add(time.ticks_us(),2*verified.BLOCK_US-500)


def step(stream, pcm, audio):
    source = stream.take()
    started = time.ticks_us()
    result = convert(source,pcm)
    elapsed = time.ticks_diff(time.ticks_us(),started)
    if elapsed > stream.max_convert_us: stream.max_convert_us = elapsed
    stream.check()
    if result >> 16: raise RuntimeError("Invalid FM conversion;audio stopped")
    stream.release()
    verified._write(audio,pcm)
    return result & 65535
