"""Compare CPU and DMA feeding of a PIO TX FIFO on GP16."""

import gc
from machine import Pin
import machine
import os
import rp2
import sys
import time


PIO_FREQUENCIES = (100_000, 1_000_000, 10_000_000)
SAMPLES = 31
PATTERN_REPETITIONS = 4096
PIO0_SM0_TX_DREQ = 0


@rp2.asm_pio(
    out_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=8,
)
def output_serial_bits():
    out(pins, 1)


pattern_values = (0xF0, 0xAA, 0x00, 0xFF)
pattern = bytearray(4 * PATTERN_REPETITIONS)
for index in range(len(pattern)):
    pattern[index] = pattern_values[index & 3]
output_pin = Pin(16)
state_machine = rp2.StateMachine(0)
dma = rp2.DMA()
ctrl = dma.pack_ctrl(
    size=0,
    inc_read=True,
    inc_write=False,
    treq_sel=PIO0_SM0_TX_DREQ,
    bswap=False,
)


def prepare_state_machine(frequency):
    state_machine.active(0)
    output_pin.init(Pin.OUT, value=0)
    state_machine.init(output_serial_bits, freq=frequency, out_base=output_pin)
    state_machine.active(1)


def finish_output(frequency):
    while state_machine.tx_fifo():
        pass
    tail_us = (8_000_000 + frequency - 1) // frequency + 10
    time.sleep_us(tail_us)
    state_machine.active(0)
    output_pin.init(Pin.OUT, value=0)


def measure_cpu_feed(frequency):
    prepare_state_machine(frequency)
    gc.collect()
    started = time.ticks_us()
    state_machine.put(pattern)
    elapsed_us = time.ticks_diff(time.ticks_us(), started)
    finish_output(frequency)
    return elapsed_us, 0


def measure_dma_feed(frequency):
    prepare_state_machine(frequency)
    gc.collect()
    started = time.ticks_us()
    dma.config(
        read=pattern,
        write=state_machine,
        count=len(pattern),
        ctrl=ctrl,
        trigger=True,
    )
    background_iterations = 0
    while dma.active():
        background_iterations += 1
    elapsed_us = time.ticks_diff(time.ticks_us(), started)
    finish_output(frequency)
    return elapsed_us, background_iterations


def main():
    print("META,implementation,%s" % (sys.implementation,))
    print("META,uname,%s" % (os.uname(),))
    print("META,cpu_hz,%d" % machine.freq())
    print("META,samples,%d" % SAMPLES)
    print("META,pattern_bytes,%d" % len(pattern))
    print("META,dma_channel,%d" % dma.channel)

    try:
        for frequency in PIO_FREQUENCIES:
            measure_cpu_feed(frequency)
            measure_dma_feed(frequency)

            ideal_us = len(pattern) * 8 * 1_000_000 // frequency
            for sample in range(SAMPLES):
                methods = ("dma", "cpu") if sample & 1 else ("cpu", "dma")
                for method in methods:
                    if method == "dma":
                        elapsed_us, background_iterations = measure_dma_feed(frequency)
                    else:
                        elapsed_us, background_iterations = measure_cpu_feed(frequency)
                    print(
                        "RESULT,pio,%d,%s,%d,%d,%d,%d"
                        % (
                            frequency,
                            method,
                            sample,
                            elapsed_us,
                            background_iterations,
                            ideal_us,
                        )
                    )
    finally:
        state_machine.active(0)
        output_pin.init(Pin.OUT, value=0)
        dma.close()

    print("META,status,ok")


main()
