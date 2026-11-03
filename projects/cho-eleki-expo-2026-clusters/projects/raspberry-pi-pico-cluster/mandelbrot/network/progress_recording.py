"""Read and write deterministic tile-progress recordings."""

from __future__ import annotations

import base64
import json
from pathlib import Path


FORMAT_VERSION = "tile-progress-v2"
LEGACY_FORMAT_VERSION = "mandelbrot-progress-v1"
IMAGE_ENCODING = "base64-u8-row-major"
RGB_IMAGE_ENCODING = "base64-rgb888-row-major"
TILE_MIRRORING_REAL_AXIS = "real-axis"
TILE_MIRRORING_NONE = "none"


def write_recording(
    path,
    job,
    tiles,
    image,
    events,
    summary,
    image_encoding=IMAGE_ENCODING,
    tile_mirroring=TILE_MIRRORING_REAL_AXIS,
):
    """Atomically write the completed image and accepted-tile timeline."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    recording = {
        "format": FORMAT_VERSION,
        "image_encoding": image_encoding,
        "tile_mirroring": tile_mirroring,
        "job": dict(job),
        "job_id": summary["job_id"],
        "tile_size": summary["tile_size"],
        "worker_count": summary["worker_count_started"],
        "duration_ms": summary["e2e_ms"],
        "tiles": [dict(tile) for tile in tiles],
        "events": [dict(event) for event in events],
        "image_base64": base64.b64encode(bytes(image)).decode("ascii"),
        "summary": dict(summary),
    }
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(recording, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def load_recording(path):
    """Load and validate a progress recording, returning it and image bytes."""
    source = Path(path)
    recording = json.loads(source.read_text(encoding="utf-8"))
    format_version = recording.get("format")
    if format_version not in (FORMAT_VERSION, LEGACY_FORMAT_VERSION):
        raise ValueError("unsupported recording format")
    image_encoding = recording.get("image_encoding")
    if image_encoding not in (IMAGE_ENCODING, RGB_IMAGE_ENCODING):
        raise ValueError("unsupported image encoding")
    if format_version == LEGACY_FORMAT_VERSION and image_encoding != IMAGE_ENCODING:
        raise ValueError("legacy recording must use u8 image encoding")

    tile_mirroring = recording.get("tile_mirroring")
    if tile_mirroring is None and format_version == LEGACY_FORMAT_VERSION:
        tile_mirroring = TILE_MIRRORING_REAL_AXIS
        recording["tile_mirroring"] = tile_mirroring
    if tile_mirroring not in (TILE_MIRRORING_REAL_AXIS, TILE_MIRRORING_NONE):
        raise ValueError("unsupported tile mirroring")

    job = recording.get("job")
    if not isinstance(job, dict):
        raise ValueError("recording job is missing")
    width = job.get("width")
    height = job.get("height")
    if type(width) is not int or width <= 0 or type(height) is not int or height <= 0:
        raise ValueError("recording image dimensions are invalid")

    encoded = recording.get("image_base64")
    if not isinstance(encoded, str):
        raise ValueError("recording image is missing")
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("recording image is not valid base64") from exc
    bytes_per_pixel = 3 if image_encoding == RGB_IMAGE_ENCODING else 1
    if len(image) != width * height * bytes_per_pixel:
        raise ValueError("recording image size does not match the job")

    tiles = recording.get("tiles")
    events = recording.get("events")
    if not isinstance(tiles, list) or not isinstance(events, list):
        raise ValueError("recording tiles or events are missing")
    tile_ids = {tile.get("tile_id") for tile in tiles if isinstance(tile, dict)}
    if len(tile_ids) != len(tiles) or None in tile_ids:
        raise ValueError("recording tile IDs are invalid")
    event_ids = []
    previous_ms = -1.0
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("recording event is invalid")
        tile_id = event.get("tile_id")
        accepted_ms = event.get("accepted_ms")
        node_id = event.get("node_id")
        if tile_id not in tile_ids:
            raise ValueError("recording event has an unknown tile ID")
        if isinstance(accepted_ms, bool) or not isinstance(accepted_ms, (int, float)):
            raise ValueError("recording event time is invalid")
        if accepted_ms < previous_ms:
            raise ValueError("recording event times are not monotonic")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("recording event node ID is invalid")
        previous_ms = accepted_ms
        event_ids.append(tile_id)
    if len(event_ids) != len(tiles) or len(set(event_ids)) != len(event_ids):
        raise ValueError("recording must contain one event for every tile")

    duration_ms = recording.get("duration_ms")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)):
        raise ValueError("recording duration is invalid")
    if duration_ms < previous_ms:
        raise ValueError("recording duration precedes the last event")
    return recording, image
