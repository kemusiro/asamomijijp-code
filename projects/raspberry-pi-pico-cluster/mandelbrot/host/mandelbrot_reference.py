#!/usr/bin/env python3
"""Independent CPython reference calculator for the Pico Mandelbrot core."""

from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import struct
import sys
import time

PICO_DIR = Path(__file__).resolve().parents[1] / "pico"
sys.path.insert(0, str(PICO_DIR))

from mandelbrot_core import checksum_update  # noqa: E402


SMALL_JOB = {
    "name": "small-v1",
    "xmin": -2.0,
    "xmax": 1.0,
    "ymin": -1.0,
    "ymax": 1.0,
    "width": 8,
    "height": 8,
    "max_iter": 64,
}

EXHIBITION_JOB = {
    "name": "exhibition-candidate-v1",
    "xmin": -2.0,
    "xmax": 1.0,
    "ymin": -1.0,
    "ymax": 1.0,
    "width": 512,
    "height": 320,
    "max_iter": 64,
}

KNOWN_PIXEL_COORDINATES = ((0, 0), (256, 160), (384, 160), (511, 319))
_FLOAT32 = struct.Struct("<f")


def float32(value: float) -> float:
    return _FLOAT32.unpack(_FLOAT32.pack(value))[0]


def reference_iteration(cr: float, ci: float, max_iter: int) -> int:
    """Straightforward reference using Python float and complex arithmetic."""
    z = 0j
    c = complex(cr, ci)
    for count in range(1, max_iter + 1):
        z = z * z + c
        if z.real * z.real + z.imag * z.imag > 4.0:
            return count
    return max_iter


def reference_iteration_float32(cr: float, ci: float, max_iter: int) -> int:
    cr = float32(cr)
    ci = float32(ci)
    x = float32(cr - float32(0.25))
    ci2 = float32(ci * ci)
    q = float32(float32(x * x) + ci2)
    if float32(q * float32(q + x)) <= float32(float32(0.25) * ci2):
        return max_iter
    x = float32(cr + float32(1.0))
    if float32(float32(x * x) + ci2) <= float32(0.0625):
        return max_iter

    zr = float32(0.0)
    zi = float32(0.0)
    four = float32(4.0)
    two = float32(2.0)
    count = 0
    while count < max_iter:
        zr2 = float32(zr * zr)
        zi2 = float32(zi * zi)
        if float32(zr2 + zi2) > four:
            break
        zi = float32(float32(float32(two * zr) * zi) + ci)
        zr = float32(float32(zr2 - zi2) + cr)
        count += 1
    return count


def render_reference(job: dict) -> bytearray:
    width = job["width"]
    height = job["height"]
    dx = (job["xmax"] - job["xmin"]) / width
    dy = (job["ymax"] - job["ymin"]) / height
    output = bytearray(width * height)
    offset = 0
    for py in range(height):
        ci = job["ymin"] + (py + 0.5) * dy
        for px in range(width):
            cr = job["xmin"] + (px + 0.5) * dx
            output[offset] = reference_iteration(cr, ci, job["max_iter"])
            offset += 1
    return output


def render_reference_float32(job: dict, use_symmetry: bool = True) -> bytearray:
    """Render with float32 operations and optional real-axis symmetry.

    The exhibition job is mathematically symmetric about the real axis.  The
    optimized Pico runner computes the upper half and mirrors it, avoiding
    tiny asymmetries introduced by independently rounded float32 coordinates.
    """
    width = job["width"]
    height = job["height"]
    xmin = float32(job["xmin"])
    ymin = float32(job["ymin"])
    dx = float32(float32(float32(job["xmax"]) - xmin) / width)
    dy = float32(float32(float32(job["ymax"]) - ymin) / height)
    output = bytearray(width * height)
    offset = 0
    half = float32(0.5)
    symmetric = use_symmetry and job["ymin"] == -job["ymax"]
    rows_to_compute = (height + 1) // 2 if symmetric else height
    for py in range(rows_to_compute):
        ci = float32(ymin + float32(float32(py + half) * dy))
        for px in range(width):
            cr = float32(xmin + float32(float32(px + half) * dx))
            output[offset] = reference_iteration_float32(cr, ci, job["max_iter"])
            offset += 1
        mirror_y = height - 1 - py
        if mirror_y != py and symmetric:
            source = py * width
            destination = mirror_y * width
            output[destination : destination + width] = output[source : source + width]
    return output


def checksum_image(image: bytes) -> int:
    checksum = 0
    for index, value in enumerate(image):
        checksum = checksum_update(checksum, index, value)
    return checksum


def checksum_image_rows(image: bytes, job: dict) -> int:
    width = job["width"]
    row_checksums = []
    view = memoryview(image)
    for y in range(job["height"]):
        start = y * width
        row_checksums.append(binascii.crc32(view[start : start + width]) & 0xFFFFFFFF)
    checksum = 0
    for y, row_checksum in enumerate(row_checksums):
        checksum = checksum_update(checksum, y, row_checksum)
    return checksum


def known_pixels(image: bytes, job: dict) -> dict[str, int]:
    result = {}
    for x, y in KNOWN_PIXEL_COORDINATES:
        if x < job["width"] and y < job["height"]:
            result[f"{x},{y}"] = image[y * job["width"] + x]
    return result


def summarize(job: dict, precision: str = "float32", use_symmetry: bool = True) -> dict:
    started = time.perf_counter()
    if precision == "float32":
        image = render_reference_float32(job, use_symmetry)
    else:
        image = render_reference(job)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "job": job,
        "precision": precision,
        "symmetry_used": (
            precision == "float32" and use_symmetry and job["ymin"] == -job["ymax"]
        ),
        "checksum32": f"{checksum_image_rows(image, job):08x}",
        "checksum_version": "row-crc32-mix-v1",
        "known_pixels": known_pixels(image, job),
        "image_hex": image.hex() if job["width"] * job["height"] <= 256 else None,
        "elapsed_ms": elapsed_ms,
        "python": sys.version,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", choices=("small", "exhibition"), default="small")
    parser.add_argument("--precision", choices=("float32", "float64"), default="float32")
    parser.add_argument("--no-symmetry", action="store_true")
    args = parser.parse_args()
    job = SMALL_JOB if args.job == "small" else EXHIBITION_JOB
    print(
        json.dumps(
            summarize(job, args.precision, not args.no_symmetry),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
