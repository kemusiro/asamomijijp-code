"""Job-level sphere/vehicle dispatch. Keep only one renderer resident on Pico."""
import gc
import sys

ALGORITHM_VERSION = "alternating-raytracer-v2"
OUTPUT_VERSION = "rgb888-v1"
CHECKSUM_VERSION = "crc32-image-v1"
_active = None
_active_name = None


def _renderer(job):
    global _active, _active_name
    if not isinstance(job, dict) or job.get("scene_type") not in ("sphere", "vehicle"):
        raise ValueError("scene_type must be sphere or vehicle")
    name = "vehicle_raytracer" if job["scene_type"] == "vehicle" else ("gallery_raytracer" if sys.implementation.name == "micropython" else "raytracer_core")
    if name != _active_name:
        old = _active_name
        _active = None
        _active_name = None
        if old is not None and old in sys.modules:
            del sys.modules[old]
        gc.collect()
        module = __import__(name)
        _active = module
        _active_name = name
        gc.collect()
    return _active


def validate_job(job):
    _renderer(job).validate_job(job)


def compute_tile_into(job, x0, y0, width, height, output):
    return _renderer(job).compute_tile_into(job, x0, y0, width, height, output)


def compute_tile(job, x0, y0, width, height):
    output = bytearray(width * height * 3)
    compute_tile_into(job, x0, y0, width, height, output)
    return output
