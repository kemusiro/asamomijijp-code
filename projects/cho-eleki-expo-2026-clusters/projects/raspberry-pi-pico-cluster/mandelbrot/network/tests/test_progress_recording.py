"""Tests for progress recording and offline video frame reconstruction."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import unittest

NETWORK_DIR = Path(__file__).resolve().parents[1]
MANDELBROT_DIR = NETWORK_DIR.parent
HOST_DIR = MANDELBROT_DIR / "host"
for directory in (str(NETWORK_DIR), str(HOST_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import progress_recording  # noqa: E402
import render_progress_video as video  # noqa: E402
import manager  # noqa: E402
import mock_worker  # noqa: E402
from mandelbrot_reference import SMALL_JOB  # noqa: E402


class ProgressRecordingTests(unittest.TestCase):
    @staticmethod
    def recording_data():
        tiles = [
            {"tile_id": 0, "x0": 0, "y0": 0, "width": 8, "height": 2},
            {"tile_id": 1, "x0": 0, "y0": 2, "width": 8, "height": 2},
        ]
        image = bytes(range(32)) + bytes(reversed(range(32)))
        events = [
            {"accepted_ms": 10.5, "tile_id": 0, "node_id": "pico-01"},
            {"accepted_ms": 20.5, "tile_id": 1, "node_id": "pico-02"},
        ]
        summary = {
            "job_id": "recording-test",
            "tile_size": 2,
            "worker_count_started": 2,
            "e2e_ms": 21.0,
        }
        return tiles, image, events, summary

    def test_recording_round_trip(self):
        tiles, image, events, summary = self.recording_data()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "trace.json"
            progress_recording.write_recording(
                path, SMALL_JOB, tiles, image, events, summary
            )
            recording, loaded_image = progress_recording.load_recording(path)

        self.assertEqual(loaded_image, image)
        self.assertEqual(recording["format"], progress_recording.FORMAT_VERSION)
        self.assertEqual(recording["worker_count"], 2)
        self.assertEqual(recording["events"], events)
        self.assertEqual(
            recording["tile_mirroring"],
            progress_recording.TILE_MIRRORING_REAL_AXIS,
        )

    def test_rgb_recording_round_trip(self):
        job = {"name": "rgb-test", "width": 2, "height": 1}
        tiles = [
            {"tile_id": 0, "x0": 0, "y0": 0, "width": 2, "height": 1}
        ]
        image = bytes((255, 0, 0, 0, 255, 0))
        events = [
            {"accepted_ms": 1.0, "tile_id": 0, "node_id": "pico-01"}
        ]
        summary = {
            "job_id": "rgb-recording-test",
            "tile_size": 2,
            "worker_count_started": 1,
            "e2e_ms": 2.0,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rgb-trace.json"
            progress_recording.write_recording(
                path,
                job,
                tiles,
                image,
                events,
                summary,
                image_encoding=progress_recording.RGB_IMAGE_ENCODING,
                tile_mirroring=progress_recording.TILE_MIRRORING_NONE,
            )
            recording, loaded_image = progress_recording.load_recording(path)

        self.assertEqual(loaded_image, image)
        self.assertEqual(
            recording["image_encoding"], progress_recording.RGB_IMAGE_ENCODING
        )
        self.assertEqual(
            recording["tile_mirroring"], progress_recording.TILE_MIRRORING_NONE
        )

    def test_legacy_recording_defaults_to_real_axis_mirroring(self):
        tiles, image, events, summary = self.recording_data()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-trace.json"
            progress_recording.write_recording(
                path, SMALL_JOB, tiles, image, events, summary
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            data["format"] = progress_recording.LEGACY_FORMAT_VERSION
            data.pop("tile_mirroring")
            path.write_text(json.dumps(data), encoding="utf-8")
            recording, _loaded_image = progress_recording.load_recording(path)

        self.assertEqual(
            recording["tile_mirroring"],
            progress_recording.TILE_MIRRORING_REAL_AXIS,
        )

    def test_non_monotonic_events_are_rejected(self):
        tiles, image, events, summary = self.recording_data()
        events[1]["accepted_ms"] = 5.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            progress_recording.write_recording(
                path, SMALL_JOB, tiles, image, events, summary
            )
            with self.assertRaisesRegex(ValueError, "not monotonic"):
                progress_recording.load_recording(path)

    def test_missing_tile_event_is_rejected(self):
        tiles, image, events, summary = self.recording_data()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            progress_recording.write_recording(
                path, SMALL_JOB, tiles, image, events[:1], summary
            )
            with self.assertRaisesRegex(ValueError, "one event for every tile"):
                progress_recording.load_recording(path)

    def test_manager_records_each_accepted_tile_after_completion(self):
        manager_socket, worker_socket = socket.socketpair()
        start_event = threading.Event()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "manager-trace.json"
                session = manager.ManagerSession(
                    SMALL_JOB,
                    tile_size=4,
                    job_id="manager-recording-test",
                    timeout=5,
                    request_window=1,
                    record_path=path,
                )
                with ThreadPoolExecutor(max_workers=1) as pool:
                    manager_future = pool.submit(
                        session.run,
                        manager_socket,
                        lambda _hello, _job_id: start_event.set(),
                    )
                    worker_result = mock_worker.run_worker_session(
                        worker_socket,
                        lambda _job_id: start_event.wait(1),
                        node_id="mock-pico-recording",
                        udp_port=40001,
                    )
                    manager_result = manager_future.result(timeout=5)
                recording, image = progress_recording.load_recording(path)
        finally:
            manager_socket.close()
            worker_socket.close()

        self.assertEqual(worker_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["recording_events"], 2)
        self.assertEqual(len(recording["events"]), 2)
        self.assertEqual(len(image), SMALL_JOB["width"] * SMALL_JOB["height"])
        self.assertTrue(
            all(event["node_id"] == "mock-pico-recording" for event in recording["events"])
        )


class VideoFrameTests(unittest.TestCase):
    def test_rgb_recording_uses_image_without_palette_conversion(self):
        recording = {
            "image_encoding": progress_recording.RGB_IMAGE_ENCODING,
            "job": {"width": 2, "height": 1},
        }
        image = bytes((255, 0, 0, 0, 255, 0))
        self.assertEqual(video.recording_image_to_rgb(recording, image), image)

    def test_reveal_tile_copies_upper_and_mirrored_rows(self):
        width = 4
        height = 4
        final_rgb = bytearray()
        for pixel in range(width * height):
            final_rgb.extend((pixel, pixel, pixel))
        canvas = bytearray(video.BACKGROUND_RGB) * (width * height)
        tile = {"tile_id": 0, "x0": 1, "y0": 0, "width": 2, "height": 1}

        video.reveal_tile(canvas, final_rgb, width, height, tile)

        for row in (0, 3):
            for column in (1, 2):
                start = (row * width + column) * 3
                self.assertEqual(canvas[start : start + 3], final_rgb[start : start + 3])
        untouched = (1 * width + 1) * 3
        self.assertEqual(
            canvas[untouched : untouched + 3], bytes(video.BACKGROUND_RGB)
        )

    def test_palette_marks_max_iteration_as_interior(self):
        palette = video.iteration_palette(64)
        self.assertEqual(len(palette), 256)
        self.assertNotEqual(palette[1], video.INTERIOR_RGB)
        self.assertEqual(palette[64], video.INTERIOR_RGB)
        self.assertEqual(palette[255], video.INTERIOR_RGB)

    def test_reveal_tile_can_disable_mirroring(self):
        width = 2
        height = 2
        final_rgb = bytearray(
            (255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255)
        )
        canvas = bytearray(video.BACKGROUND_RGB) * (width * height)
        tile = {"tile_id": 0, "x0": 0, "y0": 0, "width": 2, "height": 1}

        video.reveal_tile(canvas, final_rgb, width, height, tile, mirror=False)

        self.assertEqual(canvas[:6], final_rgb[:6])
        self.assertEqual(canvas[6:], bytes(video.BACKGROUND_RGB) * 2)

    def test_ffmpeg_command_has_expected_dimensions_and_metadata(self):
        command = video.ffmpeg_command(
            "ffmpeg", 512, 328, 30, 2, Path("out.mp4"), 6
        )
        self.assertIn("512x328", command)
        self.assertIn("scale=1024:656:flags=neighbor", command)
        self.assertIn("title=Mandelbrot progress with 6 Pico 2 W workers", command)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
    def test_render_video_encodes_mp4(self):
        tiles, image, events, summary = ProgressRecordingTests.recording_data()
        with tempfile.TemporaryDirectory() as directory:
            recording_path = Path(directory) / "trace.json"
            output_path = Path(directory) / "progress.mp4"
            progress_recording.write_recording(
                recording_path, SMALL_JOB, tiles, image, events, summary
            )
            result = video.render_video(
                recording_path,
                output_path,
                fps=10,
                scale=1,
                hold=0.1,
            )
            output_size = output_path.stat().st_size

        self.assertEqual(result["workers"], 2)
        self.assertGreater(output_size, 0)


if __name__ == "__main__":
    unittest.main()
