"""Verify a saved raytrace_native.py result log with CPython."""

import sys
from pathlib import Path


VARIANTS = ("bytecode", "native")
EXPECTED_SAMPLES = 11
EXPECTED_HITS = 1481
EXPECTED_PIXEL_SUM = 323731


def median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def parse(path):
    metadata = {}
    verification = {}
    raw = {name: {} for name in VARIANTS}
    summary = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split(",")
        if fields[0] == "META":
            metadata[fields[1]] = ",".join(fields[2:])
        elif fields[0] == "VERIFY":
            verification[fields[1]] = int(fields[2])
        elif fields[0] == "RAW":
            _, workload, variant, sample, elapsed = fields
            if workload != "raytrace" or variant not in raw:
                raise ValueError(f"unexpected raw row: {line}")
            sample_number = int(sample)
            if sample_number in raw[variant]:
                raise ValueError(f"duplicate sample: {variant} {sample_number}")
            raw[variant][sample_number] = int(elapsed)
        elif fields[0] == "SUMMARY":
            _, workload, variant, minimum, middle, maximum, speedup = fields
            if workload != "raytrace" or variant not in raw:
                raise ValueError(f"unexpected summary row: {line}")
            summary[variant] = (
                int(minimum),
                int(middle),
                int(maximum),
                float(speedup),
            )

    return metadata, verification, raw, summary


def verify(path):
    metadata, verification, raw, summary = parse(path)
    if int(metadata.get("width", 0)) != 64 or int(metadata.get("height", 0)) != 48:
        raise ValueError("unexpected frame dimensions")
    if int(metadata.get("samples", 0)) != EXPECTED_SAMPLES:
        raise ValueError("unexpected sample count metadata")
    if verification.get("hits") != EXPECTED_HITS:
        raise ValueError("unexpected hit count")
    if verification.get("pixel_sum") != EXPECTED_PIXEL_SUM:
        raise ValueError("unexpected pixel sum")

    expected_numbers = set(range(1, EXPECTED_SAMPLES + 1))
    for variant in VARIANTS:
        if set(raw[variant]) != expected_numbers:
            raise ValueError(f"missing samples for {variant}")

    computed = {}
    for variant in VARIANTS:
        values = list(raw[variant].values())
        computed[variant] = (min(values), median(values), max(values))
    baseline = computed["bytecode"][1]
    for variant in VARIANTS:
        expected = summary.get(variant)
        if expected is None:
            raise ValueError(f"missing summary for {variant}")
        speedup = baseline / computed[variant][1]
        actual = (*computed[variant], round(speedup, 3))
        if actual != expected:
            raise ValueError(f"summary mismatch for {variant}: {actual} != {expected}")


def verify_pgm(path):
    data = path.read_bytes()
    header, width_height, maximum, pixels = data.split(b"\n", 3)
    if header != b"P5" or width_height != b"64 48" or maximum != b"255":
        raise ValueError("unexpected PGM header")
    if len(pixels) != 64 * 48:
        raise ValueError("unexpected PGM pixel count")
    if sum(pixels) != EXPECTED_PIXEL_SUM:
        raise ValueError("unexpected PGM pixel sum")


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: verify_raytrace_results.py RESULT.log [IMAGE.pgm]")
    path = Path(sys.argv[1])
    verify(path)
    print(f"verified: {path}")
    if len(sys.argv) == 3:
        image_path = Path(sys.argv[2])
        verify_pgm(image_path)
        print(f"verified: {image_path}")


if __name__ == "__main__":
    main()
