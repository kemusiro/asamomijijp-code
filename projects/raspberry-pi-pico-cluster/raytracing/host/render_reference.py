#!/usr/bin/env python3
"""Render the fixed Pico ray-tracing scene on CPython for visual validation."""

from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import sys
import time
import zlib
import struct

PICO_DIR = Path(__file__).resolve().parents[1] / "pico"
if str(PICO_DIR) not in sys.path:
    sys.path.insert(0, str(PICO_DIR))

import raytracer_core  # noqa: E402


PREVIEW_JOB = {
    "name": "showcase-preview-v1",
    "width": 160,
    "height": 90,
    "samples": 1,
    "shadow_samples": 1,
    "max_bounces": 1,
}

EXHIBITION_JOB = {
    "name": "showcase-spheres-v1",
    "width": 320,
    "height": 180,
    "samples": 2,
    "shadow_samples": 2,
    "max_bounces": 2,
}

HIGH_QUALITY_JOB = {
    "name": "showcase-spheres-high-quality-v1",
    "width": 384,
    "height": 216,
    "samples": 4,
    "shadow_samples": 4,
    "max_bounces": 2,
}


def render(job, tile_size=8):
    raytracer_core.validate_job(job)
    image = bytearray(job["width"] * job["height"] * 3)
    started = time.perf_counter()
    tiles = 0
    for y0 in range(0, job["height"], tile_size):
        tile_height = min(tile_size, job["height"] - y0)
        for x0 in range(0, job["width"], tile_size):
            tile_width = min(tile_size, job["width"] - x0)
            payload = raytracer_core.compute_tile(
                job, x0, y0, tile_width, tile_height
            )
            for local_y in range(tile_height):
                source = local_y * tile_width * 3
                destination = ((y0 + local_y) * job["width"] + x0) * 3
                image[destination : destination + tile_width * 3] = payload[
                    source : source + tile_width * 3
                ]
            tiles += 1
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return image, {"elapsed_ms": elapsed_ms, "tiles": tiles}


def write_png(path, image, width, height):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    rows = bytearray()
    row_bytes = width * 3
    for row in range(height):
        rows.append(0)
        start = row * row_bytes
        rows.extend(image[start : start + row_bytes])
    payload = bytearray(b"\x89PNG\r\n\x1a\n")
    payload.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    payload.extend(chunk(b"IDAT", zlib.compress(rows, 9)))
    payload.extend(chunk(b"IEND", b""))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument(
        "--preset",
        choices=("preview", "exhibition", "high-quality"),
        default="preview",
    )
    parser.add_argument("--tile-size", type=int, default=8)
    args = parser.parse_args()
    jobs = {
        "preview": PREVIEW_JOB,
        "exhibition": EXHIBITION_JOB,
        "high-quality": HIGH_QUALITY_JOB,
    }
    job = jobs[args.preset]
    image, summary = render(job, args.tile_size)
    write_png(args.output, image, job["width"], job["height"])
    summary.update(
        {
            "output": args.output,
            "job": job,
            "crc32": "%08x" % (binascii.crc32(image) & 0xFFFFFFFF),
        }
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
