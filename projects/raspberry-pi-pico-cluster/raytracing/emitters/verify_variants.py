#!/usr/bin/env python3
"""Verify CPython-compatible variants produce the same tile bytes."""

from __future__ import annotations

import binascii
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VARIANTS = (
    "raytracer_core_original.py",
    "raytracer_core_viper.py",
    "raytracer_core_inline_asm.py",
)
JOB = {
    "width": 320,
    "height": 180,
    "samples": 2,
    "shadow_samples": 2,
    "max_bounces": 2,
}


def load(path: Path):
    name = "verify_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    reference = None
    for filename in VARIANTS:
        module = load(ROOT / filename)
        result = bytes(module.compute_tile(JOB, 144, 80, 16, 16))
        checksum = "%08x" % (binascii.crc32(result) & 0xFFFFFFFF)
        print("%s: %d bytes, CRC32 %s" % (filename, len(result), checksum))
        if reference is None:
            reference = result
        elif result != reference:
            raise RuntimeError(filename + " differs from original")
    print("compatible variants match")


if __name__ == "__main__":
    main()
