"""Pico 2 W measurement runner for the Mandelbrot tile core.

Copy this file and mandelbrot_core.py to one confirmed Pico 2 W, then invoke
the public functions from mpremote. The default direct execution performs only
the small self-check; it does not start the long exhibition benchmark.
"""

import gc
try:
    import binascii
except ImportError:
    import ubinascii as binascii
try:
    import json
except ImportError:
    import ujson as json
import sys
try:
    import time
except ImportError:
    import utime as time

import mandelbrot_core as core


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

EXPECTED_FLOAT_CHECKSUMS = {
    "small-v1": "9bcd4fd2",
    "exhibition-candidate-v1": "1a26b685",
}

KNOWN_PIXEL_COORDINATES = ((0, 0), (256, 160), (384, 160), (511, 319))


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.perf_counter() * 1000)


def _ticks_diff(later, earlier):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(later, earlier)
    return later - earlier


def _mem_free():
    if hasattr(gc, "mem_free"):
        return gc.mem_free()
    return -1


def _mem_alloc():
    if hasattr(gc, "mem_alloc"):
        return gc.mem_alloc()
    return -1


def _collect_timed():
    started = _ticks_ms()
    gc.collect()
    return _ticks_diff(_ticks_ms(), started)


def platform_info():
    implementation = getattr(sys, "implementation", None)
    return {
        "implementation": str(implementation),
        "version": sys.version,
        "platform": sys.platform,
        "algorithm_version": core.ALGORITHM_VERSION,
        "output_version": core.OUTPUT_VERSION,
        "checksum_version": core.CHECKSUM_VERSION,
    }


def _record_known_pixels(result, tile, job, x0, y0, tile_width, tile_height):
    for known_x, known_y in KNOWN_PIXEL_COORDINATES:
        if x0 <= known_x < x0 + tile_width and y0 <= known_y < y0 + tile_height:
            local_x = known_x - x0
            local_y = known_y - y0
            result[str(known_x) + "," + str(known_y)] = tile[local_y * tile_width + local_x]


def _is_real_axis_symmetric(job):
    return job["ymin"] == -job["ymax"]


def _record_known_pixels_symmetric(result, tile, job, x0, y0, tile_width, tile_height):
    for known_x, known_y in KNOWN_PIXEL_COORDINATES:
        if not (x0 <= known_x < x0 + tile_width):
            continue
        for local_y in range(tile_height):
            row = y0 + local_y
            if known_y == row or known_y == job["height"] - 1 - row:
                result[str(known_x) + "," + str(known_y)] = tile[
                    local_y * tile_width + known_x - x0
                ]


def run_job(
    job,
    method="float",
    tile_size=32,
    q_bits=core.DEFAULT_Q_BITS,
    gc_interval_tiles=1,
    use_symmetry=True,
):
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")

    gc_ms = _collect_timed()
    explicit_gc_count = 1
    free_before = _mem_free()
    alloc_before = _mem_alloc()
    min_free = free_before
    row_checksums = [0] * job["height"]
    known = {}
    tile_count = 0
    compute_ms = 0
    tile = bytearray(min(tile_size, job["width"]) * min(tile_size, job["height"]))
    tile_view = memoryview(tile)
    symmetry_used = bool(
        use_symmetry and method == "float" and _is_real_axis_symmetric(job)
    )
    y_stop = (job["height"] + 1) // 2 if symmetry_used else job["height"]
    computed_pixel_count = 0
    started = _ticks_ms()

    for y0 in range(0, y_stop, tile_size):
        tile_height = min(tile_size, y_stop - y0)
        for x0 in range(0, job["width"], tile_size):
            tile_width = min(tile_size, job["width"] - x0)
            tile_started = _ticks_ms()
            core.compute_tile_into(job, x0, y0, tile_width, tile_height, tile, method, q_bits)
            compute_ms += _ticks_diff(_ticks_ms(), tile_started)
            for local_y in range(tile_height):
                start = local_y * tile_width
                row = y0 + local_y
                row_checksum = binascii.crc32(
                    tile_view[start : start + tile_width], row_checksums[row]
                ) & 0xFFFFFFFF
                row_checksums[row] = row_checksum
                if symmetry_used:
                    row_checksums[job["height"] - 1 - row] = row_checksum
            if symmetry_used:
                _record_known_pixels_symmetric(
                    known, tile, job, x0, y0, tile_width, tile_height
                )
            else:
                _record_known_pixels(known, tile, job, x0, y0, tile_width, tile_height)
            tile_count += 1
            computed_pixel_count += tile_width * tile_height
            current_free = _mem_free()
            if current_free >= 0 and (min_free < 0 or current_free < min_free):
                min_free = current_free
            if gc_interval_tiles > 0 and tile_count % gc_interval_tiles == 0:
                gc_ms += _collect_timed()
                explicit_gc_count += 1

    elapsed_ms = _ticks_diff(_ticks_ms(), started)
    checksum = 0
    for row, row_checksum in enumerate(row_checksums):
        checksum = core.checksum_update(checksum, row, row_checksum)
    del tile_view
    del tile
    gc_ms += _collect_timed()
    explicit_gc_count += 1
    free_after = _mem_free()
    alloc_after = _mem_alloc()
    expected = EXPECTED_FLOAT_CHECKSUMS.get(job["name"]) if method == "float" else None

    return {
        "job": job["name"],
        "method": method,
        "q_bits": q_bits if method != "float" else None,
        "tile_size": tile_size,
        "tile_count": tile_count,
        "computed_pixel_count": computed_pixel_count,
        "logical_pixel_count": job["width"] * job["height"],
        "symmetry_used": symmetry_used,
        "tile_result_bytes_max": min(tile_size, job["width"]) * min(tile_size, job["height"]),
        "elapsed_ms": elapsed_ms,
        "compute_ms": compute_ms,
        "checksum32": "%08x" % checksum,
        "expected_checksum32": expected,
        "checksum_matches": expected is None or ("%08x" % checksum) == expected,
        "known_pixels": known,
        "mem_free_before": free_before,
        "mem_free_min_sampled": min_free,
        "mem_free_after_gc": free_after,
        "mem_alloc_before": alloc_before,
        "mem_alloc_after_gc": alloc_after,
        "explicit_gc_count": explicit_gc_count,
        "explicit_gc_ms": gc_ms,
        "gc_interval_tiles": gc_interval_tiles,
    }


def _emit(record):
    print(json.dumps(record))


def self_check():
    _emit({"type": "platform", "data": platform_info()})
    result = run_job(SMALL_JOB, "float", 4)
    _emit({"type": "small_self_check", "data": result})
    if not result["checksum_matches"]:
        raise RuntimeError("small reference checksum mismatch")
    return result


def run_suite(runs=1, include_fixed=False):
    _emit({"type": "platform", "data": platform_info()})
    methods = ("float", "fixed_q20") if include_fixed else ("float",)
    for method in methods:
        for tile_size in (16, 32, 64):
            for run_number in range(1, runs + 1):
                result = run_job(EXHIBITION_JOB, method, tile_size)
                result["run"] = run_number
                _emit({"type": "benchmark", "data": result})
                if method == "float" and not result["checksum_matches"]:
                    raise RuntimeError("exhibition reference checksum mismatch")


def run_reliability(runs=20, method="float", tile_size=64):
    if runs <= 0:
        raise ValueError("runs must be positive")
    expected = None
    failures = 0
    elapsed_values = []
    compute_values = []
    min_free_values = []
    _emit({"type": "platform", "data": platform_info()})
    for run_number in range(1, runs + 1):
        result = run_job(EXHIBITION_JOB, method, tile_size)
        result["run"] = run_number
        if expected is None:
            expected = result["checksum32"]
        consistent = result["checksum32"] == expected and result["checksum_matches"]
        result["consistent_with_run_1"] = consistent
        if not consistent:
            failures += 1
        elapsed_values.append(result["elapsed_ms"])
        compute_values.append(result["compute_ms"])
        min_free_values.append(result["mem_free_min_sampled"])
        _emit({"type": "reliability", "data": result})
    summary = {
        "runs": runs,
        "failures": failures,
        "method": method,
        "tile_size": tile_size,
        "checksum32": expected,
        "elapsed_ms_min": min(elapsed_values),
        "elapsed_ms_max": max(elapsed_values),
        "elapsed_ms_mean": sum(elapsed_values) // runs,
        "compute_ms_min": min(compute_values),
        "compute_ms_max": max(compute_values),
        "compute_ms_mean": sum(compute_values) // runs,
        "mem_free_min_sampled": min(min_free_values),
    }
    _emit({"type": "reliability_summary", "data": summary})
    if failures:
        raise RuntimeError("reliability run detected a mismatch")
    return summary


if __name__ == "__main__":
    self_check()
