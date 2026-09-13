"""Host-side tests for the independent reference and MicroPython core."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
sys.path.insert(0, str(ROOT / "pico"))

import benchmark  # noqa: E402
import mandelbrot_core as core  # noqa: E402
import mandelbrot_reference as reference  # noqa: E402


EXPECTED_SMALL_HEX = (
    "0103030406060302"
    "0303040640400503"
    "0305081540402603"
    "0408404040400603"
    "0408404040400603"
    "0305081540402603"
    "0303040640400503"
    "0103030406060302"
)


def render_with_core(job, tile_size, method="float"):
    image = bytearray(job["width"] * job["height"])
    checksum = 0
    for y0 in range(0, job["height"], tile_size):
        tile_height = min(tile_size, job["height"] - y0)
        for x0 in range(0, job["width"], tile_size):
            tile_width = min(tile_size, job["width"] - x0)
            tile = core.compute_tile(job, x0, y0, tile_width, tile_height, method)
            checksum = core.update_checksum_for_tile(
                checksum, tile, job["width"], x0, y0, tile_width, tile_height
            )
            for local_y in range(tile_height):
                source = local_y * tile_width
                destination = (y0 + local_y) * job["width"] + x0
                image[destination : destination + tile_width] = tile[source : source + tile_width]
    return image, checksum


class MandelbrotCoreTests(unittest.TestCase):
    def test_small_reference_is_pinned(self):
        image = reference.render_reference(reference.SMALL_JOB)
        self.assertEqual(image.hex(), EXPECTED_SMALL_HEX)
        self.assertEqual(reference.checksum_image(image), 0xCE7D8FA3)

    def test_float_core_matches_independent_reference(self):
        expected = reference.render_reference(reference.SMALL_JOB)
        actual, checksum = render_with_core(reference.SMALL_JOB, 3, "float")
        self.assertEqual(actual, expected)
        self.assertEqual(checksum, 0xCE7D8FA3)

    def test_exhibition_candidate_is_pinned(self):
        expected = reference.render_reference(reference.EXHIBITION_JOB)
        actual, checksum = render_with_core(reference.EXHIBITION_JOB, 32, "float")
        self.assertEqual(actual, expected)
        self.assertEqual(checksum, 0xE135D100)
        self.assertEqual(
            reference.known_pixels(actual, reference.EXHIBITION_JOB),
            {"0,0": 1, "256,160": 64, "384,160": 64, "511,319": 2},
        )

    def test_float32_reference_matches_pico_observation(self):
        image = reference.render_reference_float32(reference.EXHIBITION_JOB, use_symmetry=False)
        self.assertEqual(reference.checksum_image(image), 0x9807E883)
        self.assertEqual(
            reference.known_pixels(image, reference.EXHIBITION_JOB),
            {"0,0": 1, "256,160": 64, "384,160": 64, "511,319": 2},
        )

    def test_row_checksum_is_pinned(self):
        float32_image = reference.render_reference_float32(reference.EXHIBITION_JOB)
        self.assertEqual(
            reference.checksum_image_rows(float32_image, reference.EXHIBITION_JOB),
            0x1A26B685,
        )

    def test_float32_symmetry_rounding_difference_is_bounded(self):
        formula = reference.render_reference_float32(
            reference.EXHIBITION_JOB, use_symmetry=False
        )
        symmetric = reference.render_reference_float32(reference.EXHIBITION_JOB)
        deltas = [abs(a - b) for a, b in zip(formula, symmetric) if a != b]
        self.assertEqual(len(deltas), 15)
        self.assertEqual(max(deltas), 5)

    def test_checksum_and_pixels_do_not_depend_on_tile_size(self):
        job = dict(reference.SMALL_JOB)
        job.update({"width": 65, "height": 33})
        expected = reference.render_reference(job)
        expected_checksum = reference.checksum_image(expected)
        for tile_size in (16, 32, 64):
            with self.subTest(tile_size=tile_size):
                actual, checksum = render_with_core(job, tile_size, "float")
                self.assertEqual(actual, expected)
                self.assertEqual(checksum, expected_checksum)

    def test_fixed_q20_is_deterministic_and_close_to_float(self):
        float_image, _ = render_with_core(reference.SMALL_JOB, 4, "float")
        fixed_a, fixed_checksum_a = render_with_core(reference.SMALL_JOB, 3, "fixed_q20")
        fixed_b, fixed_checksum_b = render_with_core(reference.SMALL_JOB, 5, "fixed_q20")
        self.assertEqual(fixed_a, fixed_b)
        self.assertEqual(fixed_checksum_a, fixed_checksum_b)
        mismatches = sum(a != b for a, b in zip(float_image, fixed_a))
        self.assertLessEqual(mismatches, 2)

    def test_fixed_q20_exhibition_difference_is_pinned(self):
        float_image = reference.render_reference_float32(reference.EXHIBITION_JOB)
        fixed_image, _ = render_with_core(
            reference.EXHIBITION_JOB, 32, "fixed_q20"
        )
        deltas = [abs(a - b) for a, b in zip(float_image, fixed_image) if a != b]
        self.assertEqual(len(deltas), 189)
        self.assertEqual(max(deltas), 22)

    def test_tile_validation_and_u8_limit(self):
        job = dict(reference.SMALL_JOB)
        with self.assertRaises(ValueError):
            core.compute_tile(job, 7, 7, 2, 2)
        job["max_iter"] = 256
        with self.assertRaises(ValueError):
            core.compute_tile(job, 0, 0, 1, 1)

    def test_twenty_small_runs_are_reproducible(self):
        checksums = []
        for _ in range(20):
            result = benchmark.run_job(benchmark.SMALL_JOB, "float", 4)
            self.assertTrue(result["checksum_matches"])
            checksums.append(result["checksum32"])
        self.assertEqual(len(set(checksums)), 1)


if __name__ == "__main__":
    unittest.main()
