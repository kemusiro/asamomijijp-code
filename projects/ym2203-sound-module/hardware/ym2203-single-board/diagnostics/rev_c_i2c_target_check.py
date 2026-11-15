# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Silent RP2350 I2C0 target diagnostic; RAM only, no YM register commands."""
import gc
import time
from machine import Pin, I2C, mem32
from rev_c_bus_check import RevCBus, _check_platform, _emergency_stop


ADDRESS = 0x42  # temporary diagnostic address, not the sound module API
TRANSPORT_VERSION = "1.1"
SIGNATURE = b"RCI2C01!"
WAIT_MS = 300000
# RP2350 I2C0. Absolute constants avoid allocating base+offset in the poll loop.
IC_CON = 0x40090000
IC_SAR = 0x40090008
IC_DATA_CMD = 0x40090010
IC_INTR_MASK = 0x40090030
IC_RAW_INTR_STAT = 0x40090034
IC_RX_TL = 0x40090038
IC_TX_TL = 0x4009003C
IC_CLR_INTR = 0x40090040
IC_CLR_RD_REQ = 0x40090050
IC_CLR_TX_ABRT = 0x40090054
IC_CLR_RX_DONE = 0x40090058
IC_CLR_STOP_DET = 0x40090060
IC_ENABLE = 0x4009006C
IC_STATUS = 0x40090070
IC_RXFLR = 0x40090078
IC_TX_ABRT_SOURCE = 0x40090080
IC_SLV_DATA_NACK_ONLY = 0x40090084
IC_DMA_CR = 0x40090088
IC_ACK_GENERAL_CALL = 0x40090098
IC_ENABLE_STATUS = 0x4009009C
IC_CLR_RESTART_DET = 0x400900A8
IC_COMP_TYPE = 0x400900FC
CON_TARGET = 0x324  # SDK slave mode: fast, restart, TX empty control, RX full hold
FIRST_BYTE = 0x800
RD_REQ = 0x20
TX_ABRT = 0x40
RX_DONE = 0x80
STOP_DET = 0x200
RESTART_DET = 0x1000
FIFO_ERRORS = 0x0B  # RX underflow/overflow, TX overflow


class Window:
    def __init__(self):
        self.data = bytearray(256)
        self.data[:8] = SIGNATURE
        self.pointer = 0
        self.received = self.sent = self.ignored = 0
        self.finish_pending = self.finished = False

    def receive(self, word):
        value = word & 255
        self.received += 1
        if word & FIRST_BYTE:
            self.pointer = value
            return
        if 0x20 <= self.pointer < 0x40:
            self.data[self.pointer] = value
        elif self.pointer == 0x7F and value == 0xA5:
            self.finish_pending = True
        else:
            self.ignored += 1
        self.pointer = (self.pointer + 1) & 255

    def next_byte(self):
        value = self.data[self.pointer]
        self.pointer = (self.pointer + 1) & 255
        self.sent += 1
        return value


class Target:
    def __init__(self):
        self.window = Window()
        self.controller = None
        self.flushes = 0
        self.touched = False

    def _enable(self, enabled):
        mem32[IC_ENABLE] = enabled
        started = time.ticks_ms()
        while mem32[IC_ENABLE_STATUS] & 1 != enabled:
            if time.ticks_diff(time.ticks_ms(), started) >= 100:
                raise RuntimeError("I2C enable/disable timeout")
            time.sleep_us(10)

    def prepare(self):
        self.touched = True
        # Use the official port to enable the clock, release reset and select the
        # approved GP20/21 mux. No master transfers are issued by this object.
        self.controller = I2C(0, sda=Pin(20), scl=Pin(21), freq=100000)
        self._enable(0)
        if mem32[IC_COMP_TYPE] != 0x44570140:
            raise RuntimeError("Unexpected RP2350 I2C component ID")
        mem32[IC_INTR_MASK] = 0  # polling RAW status, no Python IRQ callback
        mem32[IC_DMA_CR] = 0
        mem32[IC_CON] = CON_TARGET
        mem32[IC_SAR] = ADDRESS
        mem32[IC_RX_TL] = 0
        mem32[IC_TX_TL] = 0
        mem32[IC_SLV_DATA_NACK_ONLY] = 0
        mem32[IC_ACK_GENERAL_CALL] = 0
        unused = mem32[IC_CLR_INTR]
        if mem32[IC_CON] != CON_TARGET or mem32[IC_SAR] != ADDRESS:
            raise RuntimeError("I2C target configuration readback failed")

    def poll(self):
        raw = mem32[IC_RAW_INTR_STAT]
        if raw & FIFO_ERRORS:
            raise RuntimeError("I2C FIFO error: 0x%X" % raw)
        if raw & TX_ABRT:
            source = mem32[IC_TX_ABRT_SOURCE]
            unused = mem32[IC_CLR_TX_ABRT]
            # Hardware may flush stale TX data at a new read; other aborts fail.
            if source & 0x1FFFF != 0x2000:
                raise RuntimeError("I2C TX abort: 0x%X" % source)
            self.flushes += 1
        # Drain pointer/data bytes before answering a repeated-start read.
        while mem32[IC_RXFLR]:
            self.window.receive(mem32[IC_DATA_CMD])
        if raw & RD_REQ:
            # RP2350 datasheet 12.2.10.1.2: prepare/enqueue the byte while
            # RD_REQ is still asserted, then acknowledge the request. Python
            # may be interrupted while preparing the reply; do not release the
            # request first and rely on an empty FIFO to keep stretching SCL.
            mem32[IC_DATA_CMD] = self.window.next_byte()
            unused = mem32[IC_CLR_RD_REQ]
        if raw & RX_DONE:
            unused = mem32[IC_CLR_RX_DONE]
        if raw & STOP_DET:
            unused = mem32[IC_CLR_STOP_DET]
        if raw & RESTART_DET:
            unused = mem32[IC_CLR_RESTART_DET]
        # Do not disable before the host's final byte ACK and STOP complete.
        if self.window.finish_pending and not mem32[IC_STATUS] & 0x40:
            self.window.finished = True

    def serve(self):
        self._enable(1)
        started = time.ticks_ms()
        while not self.window.finished:
            self.poll()
            if time.ticks_diff(time.ticks_ms(), started) >= WAIT_MS:
                raise RuntimeError("I2C diagnostic timed out; rerun target then host")

    def close(self):
        if not self.touched:
            return
        try:
            self._enable(0)
        finally:
            # RP2 hardware I2C has no portable deinit method; disconnect its mux.
            Pin(20, Pin.IN, pull=None)
            Pin(21, Pin.IN, pull=None)


def run():
    _check_platform()
    print("YM2203 Rev C / silent I2C target check v1.1")
    print("YM stays in reset; DAC/LINE stay muted. Use the OTHER Pico for host.")
    board = target = reserve = None
    try:
        reserve = bytearray(4096)
        board = RevCBus()
        target = Target()
        target.prepare()
        gc.collect()
        print("READY: address=0x42 SDA=GP20 SCL=GP21; start host within 5 minutes.")
        target.serve()  # no console output or explicit GC while serving
    except BaseException:
        reserve = None
        gc.collect()
        print("FAIL or interrupted. Save both target and host logs.")
        raise
    finally:
        reserve = None
        gc.collect()
        try:
            if target is not None:
                target.close()
        finally:
            if board is not None:
                board.close()
            else:
                _emergency_stop()
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 I2C=disabled")
    print("TARGET: received=%d sent=%d ignored=%d stale_flushes=%d" %
          (target.window.received, target.window.sent, target.window.ignored, target.flushes))
    print("DONE: host requested finish; confirm HOST PASS and no sound on both logs.")


if __name__ == "__main__":
    run()
