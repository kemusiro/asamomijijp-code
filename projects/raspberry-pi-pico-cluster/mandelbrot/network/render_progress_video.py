#!/usr/bin/env python3
"""Render an MP4 from a Mandelbrot or RGB tile-progress recording."""

from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path
import shutil
import subprocess

from progress_recording import (
    IMAGE_ENCODING,
    RGB_IMAGE_ENCODING,
    TILE_MIRRORING_REAL_AXIS,
    load_recording,
)


BACKGROUND_RGB = (6, 9, 16)
INTERIOR_RGB = (0, 0, 0)
PROGRESS_TRACK_RGB = (30, 36, 48)
PROGRESS_FILL_RGB = (34, 211, 238)
PROGRESS_HEIGHT = 8


def iteration_palette(max_iter):
    if type(max_iter) is not int or not 1 <= max_iter <= 255:
        raise ValueError("max_iter must be between 1 and 255")
    palette = []
    for value in range(256):
        if value >= max_iter:
            palette.append(INTERIOR_RGB)
            continue
        ratio = value / max_iter
        hue = (0.66 - 0.60 * ratio) % 1.0
        saturation = 0.88
        brightness = 0.20 + 0.80 * math.sqrt(ratio)
        red, green, blue = colorsys.hsv_to_rgb(hue, saturation, brightness)
        palette.append((round(red * 255), round(green * 255), round(blue * 255)))
    return palette


def colorize_image(image, max_iter):
    palette = iteration_palette(max_iter)
    output = bytearray(len(image) * 3)
    for index, value in enumerate(image):
        destination = index * 3
        output[destination : destination + 3] = bytes(palette[value])
    return output


def recording_image_to_rgb(recording, image):
    encoding = recording["image_encoding"]
    if encoding == IMAGE_ENCODING:
        return colorize_image(image, recording["job"]["max_iter"])
    if encoding == RGB_IMAGE_ENCODING:
        return bytearray(image)
    raise ValueError("unsupported image encoding")


def reveal_tile(canvas, final_rgb, width, height, tile, mirror=True):
    x0 = tile["x0"]
    y0 = tile["y0"]
    tile_width = tile["width"]
    tile_height = tile["height"]
    for local_y in range(tile_height):
        row = y0 + local_y
        mirror_row = height - 1 - row
        source = (row * width + x0) * 3
        source_end = source + tile_width * 3
        destination = source
        canvas[destination:source_end] = final_rgb[source:source_end]
        if mirror and mirror_row != row:
            mirror_destination = (mirror_row * width + x0) * 3
            mirror_end = mirror_destination + tile_width * 3
            canvas[mirror_destination:mirror_end] = final_rgb[
                mirror_destination:mirror_end
            ]


def draw_progress(canvas, width, height, completed, total):
    first_row = height
    for row in range(first_row, first_row + PROGRESS_HEIGHT):
        start = row * width * 3
        canvas[start : start + width * 3] = bytes(PROGRESS_TRACK_RGB) * width
    filled = round(width * completed / total) if total else 0
    for row in range(first_row, first_row + PROGRESS_HEIGHT):
        start = row * width * 3
        canvas[start : start + filled * 3] = bytes(PROGRESS_FILL_RGB) * filled


def ffmpeg_command(
    ffmpeg,
    width,
    height,
    fps,
    scale,
    output,
    worker_count,
    demo_name="Mandelbrot",
):
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "%dx%d" % (width, height),
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-vf",
        "scale=%d:%d:flags=neighbor" % (width * scale, height * scale),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-metadata",
        "title=%s progress with %d Pico 2 W workers"
        % (demo_name, worker_count),
        str(output),
    ]


def render_video(recording_path, output_path, fps=30, scale=2, speed=1.0, hold=1.0, ffmpeg=None):
    if type(fps) is not int or fps <= 0:
        raise ValueError("fps must be a positive integer")
    if type(scale) is not int or scale <= 0:
        raise ValueError("scale must be a positive integer")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or speed <= 0:
        raise ValueError("speed must be positive")
    if isinstance(hold, bool) or not isinstance(hold, (int, float)) or hold < 0:
        raise ValueError("hold must be zero or positive")

    recording, image = load_recording(recording_path)
    job = recording["job"]
    width = job["width"]
    height = job["height"]
    frame_height = height + PROGRESS_HEIGHT
    final_rgb = recording_image_to_rgb(recording, image)
    mirror_tiles = recording["tile_mirroring"] == TILE_MIRRORING_REAL_AXIS
    demo_name = (
        "Ray tracing"
        if recording["image_encoding"] == RGB_IMAGE_ENCODING
        else "Mandelbrot"
    )
    canvas = bytearray(BACKGROUND_RGB) * (width * frame_height)
    tiles = {tile["tile_id"]: tile for tile in recording["tiles"]}
    events = recording["events"]
    event_index = 0
    playback_seconds = recording["duration_ms"] / 1000.0 / speed
    frame_count = math.ceil((playback_seconds + hold) * fps) + 1

    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg was not found; install it or pass --ffmpeg")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ffmpeg_command(
        executable,
        width,
        frame_height,
        fps,
        scale,
        output,
        recording["worker_count"],
        demo_name=demo_name,
    )
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame_index in range(frame_count):
            elapsed_ms = min(frame_index / fps * speed * 1000.0, recording["duration_ms"])
            while event_index < len(events) and events[event_index]["accepted_ms"] <= elapsed_ms:
                reveal_tile(
                    canvas,
                    final_rgb,
                    width,
                    height,
                    tiles[events[event_index]["tile_id"]],
                    mirror=mirror_tiles,
                )
                event_index += 1
            draw_progress(canvas, width, height, event_index, len(events))
            process.stdin.write(canvas)
    except BrokenPipeError as exc:
        error = process.stderr.read().decode("utf-8", errors="replace")
        process.stderr.close()
        raise RuntimeError("ffmpeg stopped while encoding: " + error.strip()) from exc
    finally:
        if process.stdin is not None:
            process.stdin.close()
    error = process.stderr.read().decode("utf-8", errors="replace")
    process.stderr.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError("ffmpeg failed: " + error.strip())
    return {
        "recording": str(recording_path),
        "output": str(output),
        "workers": recording["worker_count"],
        "duration_ms": recording["duration_ms"],
        "video_seconds": frame_count / fps,
        "frames": frame_count,
        "fps": fps,
        "scale": scale,
        "speed": speed,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", help="progress recording JSON from manager.py")
    parser.add_argument("output", help="output MP4 path")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--hold", type=float, default=1.0)
    parser.add_argument("--ffmpeg")
    args = parser.parse_args()
    result = render_video(
        args.recording,
        args.output,
        fps=args.fps,
        scale=args.scale,
        speed=args.speed,
        hold=args.hold,
        ffmpeg=args.ffmpeg,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
