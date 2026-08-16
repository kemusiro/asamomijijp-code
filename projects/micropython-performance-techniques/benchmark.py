"""Compare MicroPython bytecode, native, Viper, and Thumb inline assembly."""

import gc
import machine
import micropython
import os
import sys
import time


SAMPLES = 31
INTEGER_N = 20_000
INTEGER_CALLS = 20
BUFFER_SIZE = 4_096
BUFFER_CALLS = 20  # Must be even so repeated XOR restores the input.
XOR_MASK = 0x5A


def sum_bytecode(n):
    total = 0
    while n:
        total += n
        n -= 1
    return total


@micropython.native
def sum_native(n):
    total = 0
    while n:
        total += n
        n -= 1
    return total


@micropython.viper
def sum_viper(n: int) -> int:
    total = 0
    while n:
        total += n
        n -= 1
    return total


@micropython.asm_thumb
def sum_asm(r0):
    mov(r1, 0)
    label(loop)
    add(r1, r1, r0)
    sub(r0, 1)
    bne(loop)
    mov(r0, r1)


def xor_bytecode(buf, n, mask):
    for index in range(n):
        buf[index] ^= mask


@micropython.native
def xor_native(buf, n, mask):
    for index in range(n):
        buf[index] ^= mask


@micropython.viper
def xor_viper(buf, n: int, mask: int):
    data = ptr8(buf)
    for index in range(n):
        data[index] = data[index] ^ mask


@micropython.asm_thumb
def xor_asm(r0, r1, r2):
    label(loop)
    ldrb(r3, [r0, 0])
    eor(r3, r2)
    strb(r3, [r0, 0])
    add(r0, 1)
    sub(r1, 1)
    bne(loop)


def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def elapsed_for_calls(function, args, calls):
    gc.collect()
    started = time.ticks_us()
    result = None
    for _ in range(calls):
        result = function(*args)
    elapsed = time.ticks_diff(time.ticks_us(), started)
    return elapsed, result


def print_metadata():
    print("META,implementation,%s" % (sys.implementation,))
    print("META,uname,%s" % (os.uname(),))
    print("META,cpu_hz,%d" % machine.freq())
    print("META,timer,time.ticks_us")
    print("META,samples,%d" % SAMPLES)
    print("META,integer_n,%d" % INTEGER_N)
    print("META,integer_calls_per_sample,%d" % INTEGER_CALLS)
    print("META,buffer_size_bytes,%d" % BUFFER_SIZE)
    print("META,buffer_calls_per_sample,%d" % BUFFER_CALLS)
    print("META,xor_mask,0x%02x" % XOR_MASK)


def verify_integer(variants):
    expected = INTEGER_N * (INTEGER_N + 1) // 2
    for name, function in variants:
        actual = function(INTEGER_N)
        if actual != expected:
            raise RuntimeError("%s returned %r, expected %r" % (name, actual, expected))
    print("VERIFY,integer,%d" % expected)


def make_buffer():
    return bytearray((index * 17 + 23) & 0xFF for index in range(BUFFER_SIZE))


def verify_buffer(variants):
    original = make_buffer()
    expected = bytearray(value ^ XOR_MASK for value in original)
    for name, function in variants:
        candidate = bytearray(original)
        function(candidate, BUFFER_SIZE, XOR_MASK)
        if candidate != expected:
            raise RuntimeError("%s produced an incorrect buffer" % name)
        function(candidate, BUFFER_SIZE, XOR_MASK)
        if candidate != original:
            raise RuntimeError("%s did not restore the buffer" % name)
    print("VERIFY,buffer,ok")


def benchmark_integer(variants):
    timings = {name: [] for name, _ in variants}
    for _, function in variants:
        function(INTEGER_N)

    for sample in range(SAMPLES):
        offset = sample % len(variants)
        for step in range(len(variants)):
            name, function = variants[(offset + step) % len(variants)]
            elapsed, result = elapsed_for_calls(function, (INTEGER_N,), INTEGER_CALLS)
            timings[name].append(elapsed)
            print("RAW,integer,%s,%d,%d" % (name, sample + 1, elapsed))
            if result != INTEGER_N * (INTEGER_N + 1) // 2:
                raise RuntimeError("%s failed after measurement" % name)
    return timings


def benchmark_buffer(variants):
    buffers = {name: make_buffer() for name, _ in variants}
    originals = {name: bytes(buffers[name]) for name, _ in variants}
    timings = {name: [] for name, _ in variants}

    for name, function in variants:
        function(buffers[name], BUFFER_SIZE, XOR_MASK)
        function(buffers[name], BUFFER_SIZE, XOR_MASK)

    for sample in range(SAMPLES):
        offset = sample % len(variants)
        for step in range(len(variants)):
            name, function = variants[(offset + step) % len(variants)]
            elapsed, _ = elapsed_for_calls(
                function,
                (buffers[name], BUFFER_SIZE, XOR_MASK),
                BUFFER_CALLS,
            )
            timings[name].append(elapsed)
            print("RAW,buffer,%s,%d,%d" % (name, sample + 1, elapsed))
            if buffers[name] != originals[name]:
                raise RuntimeError("%s buffer changed after measurement" % name)
    return timings


def print_summary(workload, variants, timings):
    baseline = median(timings["bytecode"])
    for name, _ in variants:
        values = timings[name]
        middle = median(values)
        speedup = baseline / middle
        print(
            "SUMMARY,%s,%s,%d,%d,%d,%.3f"
            % (workload, name, min(values), middle, max(values), speedup)
        )


def main():
    integer_variants = (
        ("bytecode", sum_bytecode),
        ("native", sum_native),
        ("viper", sum_viper),
        ("asm_thumb", sum_asm),
    )
    buffer_variants = (
        ("bytecode", xor_bytecode),
        ("native", xor_native),
        ("viper", xor_viper),
        ("asm_thumb", xor_asm),
    )

    print_metadata()
    verify_integer(integer_variants)
    verify_buffer(buffer_variants)
    integer_timings = benchmark_integer(integer_variants)
    buffer_timings = benchmark_buffer(buffer_variants)
    print("SUMMARY,workload,emitter,min_us,median_us,max_us,speedup_vs_bytecode")
    print_summary("integer", integer_variants, integer_timings)
    print_summary("buffer", buffer_variants, buffer_timings)


main()
