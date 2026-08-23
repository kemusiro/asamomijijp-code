"""Capture GP18 with PIO and DMA, then compare with CPU FIFO reads."""

import binascii
from machine import Pin
import machine
import rp2
import time


CAPTURE_BYTES = 16 * 1024
PIO0_SM0_RX_DREQ = 4

try:
    SAMPLE_HZ = int(CAPTURE_SAMPLE_HZ)
except NameError:
    SAMPLE_HZ = 10_000_000

if SAMPLE_HZ not in (1_000_000, 10_000_000, 20_000_000, 50_000_000, 100_000_000):
    raise ValueError("unsupported sample rate")
if CAPTURE_BYTES & 3:
    raise ValueError("capture buffer must contain complete 32-bit words")


@rp2.asm_pio(
    in_shiftdir=rp2.PIO.SHIFT_RIGHT,
    autopush=True,
    push_thresh=32,
)
def sample_one_pin():
    in_(pins, 1)


input_pin = Pin(18, Pin.IN)
state_machine = rp2.StateMachine(
    0,
    sample_one_pin,
    freq=SAMPLE_HZ,
    in_base=input_pin,
)
capture = bytearray(CAPTURE_BYTES)
word_count = CAPTURE_BYTES // 4
dma = rp2.DMA()
ctrl = dma.pack_ctrl(
    size=2,
    inc_read=False,
    inc_write=True,
    treq_sel=PIO0_SM0_RX_DREQ,
    bswap=False,
)

print("META,sample_hz,%d" % SAMPLE_HZ)
print("META,capture_bytes,%d" % CAPTURE_BYTES)
print("META,capture_bits,%d" % (CAPTURE_BYTES * 8))
print("META,cpu_hz,%d" % machine.freq())
print("META,dma_channel,%d" % dma.channel)
print("READY")

try:
    dma.config(
        read=state_machine,
        write=capture,
        count=word_count,
        ctrl=ctrl,
        trigger=True,
    )
    started = time.ticks_us()
    state_machine.active(1)
    background_iterations = 0
    while dma.active():
        background_iterations += 1
    dma_elapsed_us = time.ticks_diff(time.ticks_us(), started)
    state_machine.active(0)

    state_machine.init(sample_one_pin, freq=SAMPLE_HZ, in_base=input_pin)
    checksum = 0
    started = time.ticks_us()
    state_machine.active(1)
    for _ in range(word_count):
        checksum ^= state_machine.get()
    cpu_elapsed_us = time.ticks_diff(time.ticks_us(), started)
    state_machine.active(0)

    ideal_us = CAPTURE_BYTES * 8 * 1_000_000 // SAMPLE_HZ
    print(
        "RESULT,ideal_us,%d,dma_us,%d,cpu_us,%d,background_iterations,%d,checksum,%08x"
        % (
            ideal_us,
            dma_elapsed_us,
            cpu_elapsed_us,
            background_iterations,
            checksum & 0xFFFFFFFF,
        )
    )
    print("DATA,%s" % binascii.hexlify(capture).decode())
finally:
    state_machine.active(0)
    input_pin.init(Pin.IN)
    dma.close()

print("STATUS,ok")
