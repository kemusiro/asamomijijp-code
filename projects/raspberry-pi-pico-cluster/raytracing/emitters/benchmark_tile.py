"""Measure one 16x16 exhibition tile on a Pico 2 W."""

import binascii
import gc
import os
import sys
import time

import raytracer_core


JOB = {
    "name": "showcase-spheres-v1",
    "width": 320,
    "height": 180,
    "samples": 2,
    "shadow_samples": 2,
    "max_bounces": 2,
}
X0 = 144
Y0 = 80
TILE_SIZE = 16
RUNS = 3


def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def main():
    result = bytearray(TILE_SIZE * TILE_SIZE * 3)
    timings = []
    print("META,implementation,%s" % (sys.implementation,))
    print("META,uname,%s" % (os.uname(),))
    for run in range(RUNS):
        gc.collect()
        started = time.ticks_ms()
        raytracer_core.compute_tile_into(
            JOB, X0, Y0, TILE_SIZE, TILE_SIZE, result
        )
        elapsed = time.ticks_diff(time.ticks_ms(), started)
        timings.append(elapsed)
        checksum = "%08x" % (binascii.crc32(result) & 0xFFFFFFFF)
        print("RAW,tile,%d,%d,%s" % (run + 1, elapsed, checksum))
    print(
        "SUMMARY,tile,%d,%d,%d"
        % (min(timings), median(timings), max(timings))
    )


if __name__ == "__main__":
    main()
