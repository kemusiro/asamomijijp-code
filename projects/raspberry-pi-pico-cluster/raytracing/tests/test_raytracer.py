"""Host tests for the MicroPython-compatible ray tracer."""

from __future__ import annotations

import binascii
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest

RAYTRACING_DIR = Path(__file__).resolve().parents[1]
PICO_DIR = RAYTRACING_DIR / "pico"
HOST_DIR = RAYTRACING_DIR / "host"
NETWORK_DIR = RAYTRACING_DIR / "network"
MANDELBROT_NETWORK_DIR = RAYTRACING_DIR.parent / "mandelbrot" / "network"
for directory in (
    str(PICO_DIR),
    str(HOST_DIR),
    str(NETWORK_DIR),
    str(MANDELBROT_NETWORK_DIR),
):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import raytracer_core as core  # noqa: E402
import render_reference  # noqa: E402
import network_protocol as protocol  # noqa: E402
import progress_recording  # noqa: E402
import ray_manager  # noqa: E402


class RayTracerCoreTests(unittest.TestCase):
    def test_rejects_unsupported_quality(self):
        job = dict(render_reference.PREVIEW_JOB)
        job["samples"] = 3
        with self.assertRaisesRegex(ValueError, "samples must be 1, 2, or 4"):
            core.validate_job(job)

    def test_tile_size_and_repeatability(self):
        job = dict(render_reference.PREVIEW_JOB)
        first = core.compute_tile(job, 24, 24, 8, 8)
        second = core.compute_tile(job, 24, 24, 8, 8)
        self.assertEqual(len(first), 8 * 8 * 3)
        self.assertEqual(first, second)
        self.assertGreater(len(set(first)), 8)

    def test_tile_bounds_are_checked(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            core.compute_tile(render_reference.PREVIEW_JOB, 159, 89, 2, 2)

    def test_preview_reference_is_deterministic(self):
        image, summary = render_reference.render(
            render_reference.PREVIEW_JOB, tile_size=16
        )
        self.assertEqual(len(image), 160 * 90 * 3)
        self.assertEqual(summary["tiles"], 60)
        self.assertEqual(
            "%08x" % (binascii.crc32(image) & 0xFFFFFFFF),
            "f2557b8f",
        )

    def test_png_writer_outputs_png(self):
        image = bytes((255, 0, 0, 0, 255, 0))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tiny.png"
            render_reference.write_png(path, image, 2, 1)
            encoded = path.read_bytes()
        self.assertTrue(encoded.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", encoded)
        self.assertIn(b"IDAT", encoded)


class RayTracingNetworkTests(unittest.TestCase):
    def test_exhibition_accepts_cpython_and_rp2350_checksums(self):
        self.assertEqual(
            ray_manager.identify_checksum_profile(
                "showcase-spheres-v1", "7686fe75"
            ),
            "cpython-float64",
        )
        self.assertEqual(
            ray_manager.identify_checksum_profile(
                "showcase-spheres-v1", "4278ccd8"
            ),
            "micropython-rp2350-float32",
        )
        self.assertIsNone(
            ray_manager.identify_checksum_profile(
                "showcase-spheres-v1", "00000000"
            )
        )

    def test_full_frame_tile_grid_covers_exhibition_image(self):
        tiles = ray_manager.build_full_frame_tiles(
            render_reference.EXHIBITION_JOB, 8
        )
        self.assertEqual(len(tiles), 920)
        self.assertEqual(
            sum(tile["width"] * tile["height"] for tile in tiles),
            320 * 180,
        )
        self.assertEqual(tiles[-1]["height"], 4)

    def test_protocol_accepts_raytracing_versions(self):
        protocol.validate_hello(
            {
                "type": "hello",
                "protocol_version": protocol.PROTOCOL_VERSION,
                "algorithm_version": core.ALGORITHM_VERSION,
                "output_version": core.OUTPUT_VERSION,
                "checksum_version": core.CHECKSUM_VERSION,
                "node_id": "ray-mock-1",
                "udp_port": 40000,
            },
            algorithm_version=core.ALGORITHM_VERSION,
            output_version=core.OUTPUT_VERSION,
            checksum_version=core.CHECKSUM_VERSION,
        )

    def test_reference_tiles_assemble_to_verified_png(self):
        job = render_reference.PREVIEW_JOB
        image, _summary = render_reference.render(job, tile_size=16)
        tiles = ray_manager.build_full_frame_tiles(job, 16)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "assembled.png"
            assembler = ray_manager.RayResultAssembler(
                job, tiles, "ray-assembly-test", output
            )
            for tile in tiles:
                payload = bytearray()
                for local_y in range(tile["height"]):
                    start = (
                        (tile["y0"] + local_y) * job["width"] + tile["x0"]
                    ) * 3
                    payload.extend(image[start : start + tile["width"] * 3])
                assembler.accept(
                    {
                        "type": "tile_result",
                        "job_id": "ray-assembly-test",
                        "tile_id": tile["tile_id"],
                        "x0": tile["x0"],
                        "y0": tile["y0"],
                        "width": tile["width"],
                        "height": tile["height"],
                        "payload_crc32": "%08x"
                        % (binascii.crc32(payload) & 0xFFFFFFFF),
                        "compute_ms": 1,
                        "mem_free_min_sampled": 1000,
                    },
                    payload,
                )
            result = assembler.finish()
            output_bytes = output.read_bytes()
        self.assertEqual(result["checksum32"], "f2557b8f")
        self.assertEqual(result["tiles_completed"], len(tiles))
        self.assertTrue(output_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_generic_manager_runs_raytracing_worker_session(self):
        manager_socket, worker_socket = socket.socketpair()
        start_event = threading.Event()

        def run_worker():
            protocol.send_frame(
                worker_socket,
                {
                    "type": "hello",
                    "protocol_version": protocol.PROTOCOL_VERSION,
                    "algorithm_version": core.ALGORITHM_VERSION,
                    "output_version": core.OUTPUT_VERSION,
                    "checksum_version": core.CHECKSUM_VERSION,
                    "node_id": "ray-mock-1",
                    "udp_port": 40000,
                },
            )
            job_message, payload = protocol.recv_frame(worker_socket)
            self.assertFalse(payload)
            protocol.send_frame(
                worker_socket,
                {"type": "ready", "job_id": job_message["job_id"]},
            )
            self.assertTrue(start_event.wait(1))
            completed = 0
            while True:
                message, payload = protocol.recv_frame(worker_socket)
                self.assertFalse(payload)
                if message["type"] == "complete":
                    return completed, message["checksum32"]
                tile_payload = core.compute_tile(
                    job_message["job"],
                    message["x0"],
                    message["y0"],
                    message["width"],
                    message["height"],
                )
                protocol.send_frame(
                    worker_socket,
                    {
                        "type": "tile_result",
                        "job_id": job_message["job_id"],
                        "tile_id": message["tile_id"],
                        "x0": message["x0"],
                        "y0": message["y0"],
                        "width": message["width"],
                        "height": message["height"],
                        "payload_crc32": "%08x"
                        % (binascii.crc32(tile_payload) & 0xFFFFFFFF),
                        "compute_ms": 1,
                        "mem_free_min_sampled": 1000,
                    },
                    tile_payload,
                )
                completed += 1

        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "network.png"
                recording_path = Path(directory) / "network-trace.json"
                session = ray_manager.cluster_manager.ManagerSession(
                    render_reference.PREVIEW_JOB,
                    tile_size=16,
                    job_id="ray-network-test",
                    timeout=5,
                    request_window=4,
                    record_path=recording_path,
                    workload=ray_manager.RayTracingWorkload(output),
                )
                with ThreadPoolExecutor(max_workers=2) as pool:
                    manager_future = pool.submit(
                        session.run,
                        manager_socket,
                        lambda _hello, _job_id: start_event.set(),
                    )
                    worker_future = pool.submit(run_worker)
                    manager_result = manager_future.result(timeout=5)
                    worker_result = worker_future.result(timeout=5)
                output_exists = output.exists()
                recording, recorded_image = progress_recording.load_recording(
                    recording_path
                )
        finally:
            manager_socket.close()
            worker_socket.close()

        self.assertEqual(manager_result["checksum32"], "f2557b8f")
        self.assertEqual(worker_result, (60, "f2557b8f"))
        self.assertTrue(output_exists)
        self.assertEqual(
            recording["image_encoding"], progress_recording.RGB_IMAGE_ENCODING
        )
        self.assertEqual(
            recording["tile_mirroring"], progress_recording.TILE_MIRRORING_NONE
        )
        self.assertEqual(len(recorded_image), 160 * 90 * 3)


if __name__ == "__main__":
    unittest.main()
