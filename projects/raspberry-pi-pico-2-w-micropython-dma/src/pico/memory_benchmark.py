"""Measure slice assignment and memory-to-memory DMA on a Pico 2 W."""

import gc
import machine
import os
import rp2
import sys
import time


BUFFER_SIZES = (256, 1024, 4096, 16384, 65536)
SAMPLES = 31
COPIES_PER_SAMPLE = 20


def fill_source(buffer):
    for index in range(len(buffer)):
        buffer[index] = (index * 17 + 23) & 0xFF


def fill_reset(buffer):
    for index in range(len(buffer)):
        buffer[index] = 0xA5


def measure_dma(dma, ctrl, source, destination):
    transfer_count = len(source) // 4
    started = time.ticks_us()
    for _ in range(COPIES_PER_SAMPLE):
        dma.config(
            read=source,
            write=destination,
            count=transfer_count,
            ctrl=ctrl,
            trigger=True,
        )
        while dma.active():
            pass
    return time.ticks_diff(time.ticks_us(), started)


def measure_slice(source, destination):
    started = time.ticks_us()
    for _ in range(COPIES_PER_SAMPLE):
        destination[:] = source
    return time.ticks_diff(time.ticks_us(), started)


def run_method(method, dma, ctrl, source, destination, reset_data):
    destination[:] = reset_data
    gc.collect()
    if method == "dma":
        elapsed_us = measure_dma(dma, ctrl, source, destination)
    else:
        elapsed_us = measure_slice(source, destination)
    if destination != source:
        raise RuntimeError("copy verification failed: %s" % method)
    return elapsed_us


def main():
    print("META,implementation,%s" % (sys.implementation,))
    print("META,uname,%s" % (os.uname(),))
    print("META,cpu_hz,%d" % machine.freq())
    print("META,samples,%d" % SAMPLES)
    print("META,copies_per_sample,%d" % COPIES_PER_SAMPLE)

    dma = rp2.DMA()
    ctrl = dma.pack_ctrl(
        size=2,
        inc_read=True,
        inc_write=True,
        bswap=False,
    )
    print("META,dma_channel,%d" % dma.channel)

    try:
        for size in BUFFER_SIZES:
            source = bytearray(size)
            destination = bytearray(size)
            reset_data = bytearray(size)
            fill_source(source)
            fill_reset(reset_data)

            run_method("slice", dma, ctrl, source, destination, reset_data)
            run_method("dma", dma, ctrl, source, destination, reset_data)

            for sample in range(SAMPLES):
                methods = ("dma", "slice") if sample & 1 else ("slice", "dma")
                for method in methods:
                    elapsed_us = run_method(
                        method,
                        dma,
                        ctrl,
                        source,
                        destination,
                        reset_data,
                    )
                    print(
                        "RESULT,memory,%d,%s,%d,%d,%d"
                        % (size, method, sample, elapsed_us, COPIES_PER_SAMPLE)
                    )

            del source, destination, reset_data
            gc.collect()
            print("META,mem_free_after_%d,%d" % (size, gc.mem_free()))
    finally:
        dma.close()

    print("META,status,ok")


main()
