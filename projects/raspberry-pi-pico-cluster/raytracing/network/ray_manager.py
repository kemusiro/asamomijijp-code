#!/usr/bin/env python3
"""Raspberry Pi manager for the Pico cluster ray-tracing demo."""

from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import sys

RAYTRACING_DIR = Path(__file__).resolve().parents[1]
PICO_DIR = RAYTRACING_DIR / "pico"
HOST_DIR = RAYTRACING_DIR / "host"
MANDELBROT_NETWORK_DIR = RAYTRACING_DIR.parent / "mandelbrot" / "network"
for directory in (str(PICO_DIR), str(HOST_DIR), str(MANDELBROT_NETWORK_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import manager as cluster_manager  # noqa: E402
import network_protocol as protocol  # noqa: E402
import progress_recording  # noqa: E402
import raytracer_core as core  # noqa: E402
from render_reference import (  # noqa: E402
    EXHIBITION_JOB,
    HIGH_QUALITY_JOB,
    PREVIEW_JOB,
    write_png,
)


EXPECTED_CHECKSUM_PROFILES = {
    "showcase-preview-v1": {"cpython-float64": "f2557b8f"},
    "showcase-spheres-v1": {
        "cpython-float64": "7686fe75",
        "micropython-rp2350-float32": "4278ccd8",
    },
    "showcase-spheres-high-quality-v1": {"cpython-float64": "b76746f4"},
}

EXPECTED_PIXELS = {
    "showcase-spheres-v1": {
        "0,0": (135, 159, 201),
        "160,90": (175, 142, 53),
        "80,100": (138, 152, 179),
        "240,100": (107, 125, 158),
        "160,170": (214, 208, 196),
    }
}


def identify_checksum_profile(job_name, checksum):
    profiles = EXPECTED_CHECKSUM_PROFILES.get(job_name)
    if profiles is None:
        return None
    for profile, expected_checksum in profiles.items():
        if checksum == expected_checksum:
            return profile
    return None


def build_full_frame_tiles(job, tile_size):
    if type(tile_size) is not int or tile_size <= 0:
        raise ValueError("tile_size must be a positive integer")
    tiles = []
    tile_id = 0
    for y0 in range(0, job["height"], tile_size):
        tile_height = min(tile_size, job["height"] - y0)
        for x0 in range(0, job["width"], tile_size):
            tile_width = min(tile_size, job["width"] - x0)
            tiles.append(
                {
                    "tile_id": tile_id,
                    "x0": x0,
                    "y0": y0,
                    "width": tile_width,
                    "height": tile_height,
                }
            )
            tile_id += 1
    return tiles


class RayResultAssembler:
    def __init__(self, job, tiles, job_id, output_path):
        self.job = job
        self.job_id = job_id
        self.tiles = {tile["tile_id"]: tile for tile in tiles}
        self.completed = set()
        self.image = bytearray(job["width"] * job["height"] * 3)
        self.payload_bytes = 0
        self.compute_ms = 0
        self.min_free = None
        self.output_path = Path(output_path)

    def accept(self, message, payload):
        protocol.require_message_type(message, "tile_result")
        if message.get("job_id") != self.job_id:
            raise protocol.ProtocolError("tile_result has a different job_id")
        tile_id = message.get("tile_id")
        if tile_id not in self.tiles:
            raise protocol.ProtocolError("tile_result has an unknown tile_id")
        if tile_id in self.completed:
            raise protocol.ProtocolError("duplicate tile_result")
        tile = self.tiles[tile_id]
        for field in ("x0", "y0", "width", "height"):
            if message.get(field) != tile[field]:
                raise protocol.ProtocolError("tile_result has mismatched " + field)
        expected_length = tile["width"] * tile["height"] * 3
        if len(payload) != expected_length:
            raise protocol.ProtocolError("tile_result payload size mismatch")
        expected_crc = "%08x" % (binascii.crc32(payload) & 0xFFFFFFFF)
        if message.get("payload_crc32") != expected_crc:
            raise protocol.ProtocolError("tile_result payload CRC mismatch")

        image_width = self.job["width"]
        row_bytes = tile["width"] * 3
        for local_y in range(tile["height"]):
            source = local_y * row_bytes
            destination = (
                (tile["y0"] + local_y) * image_width + tile["x0"]
            ) * 3
            self.image[destination : destination + row_bytes] = payload[
                source : source + row_bytes
            ]
        self.completed.add(tile_id)
        self.payload_bytes += len(payload)
        compute_ms = message.get("compute_ms")
        if isinstance(compute_ms, int) and compute_ms >= 0:
            self.compute_ms += compute_ms
        mem_free = message.get("mem_free_min_sampled")
        if isinstance(mem_free, int) and mem_free >= 0:
            if self.min_free is None or mem_free < self.min_free:
                self.min_free = mem_free

    def _known_pixels(self):
        result = {}
        image_width = self.job["width"]
        expected = EXPECTED_PIXELS.get(self.job["name"], {})
        for coordinate in expected:
            x_text, y_text = coordinate.split(",")
            offset = (int(y_text) * image_width + int(x_text)) * 3
            result[coordinate] = tuple(self.image[offset : offset + 3])
        return result

    def finish(self):
        if len(self.completed) != len(self.tiles):
            raise protocol.ProtocolError("job has missing tile results")
        checksum = "%08x" % (binascii.crc32(self.image) & 0xFFFFFFFF)
        checksum_profiles = EXPECTED_CHECKSUM_PROFILES.get(self.job["name"])
        checksum_profile = identify_checksum_profile(self.job["name"], checksum)
        checksum_matches = checksum_profiles is None or checksum_profile is not None
        known_pixels = self._known_pixels()
        expected_pixels = EXPECTED_PIXELS.get(self.job["name"], {})
        known_pixels_match = known_pixels == expected_pixels
        if not checksum_matches:
            accepted = ", ".join(checksum_profiles.values())
            raise protocol.ProtocolError(
                "completed image checksum mismatch: got %s; accepted %s"
                % (checksum, accepted)
            )
        if not known_pixels_match:
            raise protocol.ProtocolError("known pixels mismatch")
        write_png(
            self.output_path,
            self.image,
            self.job["width"],
            self.job["height"],
        )
        return {
            "checksum32": checksum,
            "accepted_checksum32": (
                list(checksum_profiles.values()) if checksum_profiles else None
            ),
            "checksum_matches": checksum_matches,
            "checksum_profile": checksum_profile,
            "known_pixels": known_pixels,
            "known_pixels_match": known_pixels_match,
            "tiles_completed": len(self.completed),
            "payload_bytes_received": self.payload_bytes,
            "worker_compute_ms": self.compute_ms,
            "worker_mem_free_min_sampled": self.min_free,
            "output_path": str(self.output_path),
        }


class RayTracingWorkload:
    algorithm_version = core.ALGORITHM_VERSION
    output_version = core.OUTPUT_VERSION
    checksum_version = core.CHECKSUM_VERSION
    symmetry = "none"
    recording_image_encoding = progress_recording.RGB_IMAGE_ENCODING
    recording_tile_mirroring = progress_recording.TILE_MIRRORING_NONE

    def __init__(self, output_path):
        self.output_path = output_path

    @staticmethod
    def build_tiles(job, tile_size):
        return build_full_frame_tiles(job, tile_size)

    def create_assembler(self, job, tiles, job_id):
        return RayResultAssembler(job, tiles, job_id, self.output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--tile-size", type=int, default=16)
    parser.add_argument("--request-window", type=int, default=4)
    parser.add_argument("--worker-timeout", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--job-id", default="raytracing-showcase-1")
    parser.add_argument(
        "--preset",
        choices=("preview", "exhibition", "high-quality"),
        default="exhibition",
    )
    parser.add_argument("--output", default="raytracing-showcase.png")
    parser.add_argument(
        "--record-trace",
        help="write accepted-tile times and the completed RGB image to JSON",
    )
    args = parser.parse_args()
    jobs = {
        "preview": PREVIEW_JOB,
        "exhibition": EXHIBITION_JOB,
        "high-quality": HIGH_QUALITY_JOB,
    }
    job = jobs[args.preset]
    summary = cluster_manager.run_tcp_server(
        job,
        args.tile_size,
        args.host,
        args.port,
        args.timeout,
        args.job_id,
        request_window=args.request_window,
        worker_count=args.workers,
        worker_timeout=args.worker_timeout,
        record_path=args.record_trace,
        workload=RayTracingWorkload(args.output),
    )
    print(json.dumps({"type": "summary", "data": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
