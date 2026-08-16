"""Verify the raw output produced by benchmark.py."""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path


EXPECTED_WORKLOADS = {"integer", "buffer"}
EXPECTED_EMITTERS = {"bytecode", "native", "viper", "asm_thumb"}
EXPECTED_SAMPLES = 31


def parse_log(path: Path):
    raw = defaultdict(list)
    summaries = {}
    verified = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VERIFY,"):
            verified.add(line.split(",", 2)[1])
        elif line.startswith("RAW,"):
            _, workload, emitter, sample, elapsed = line.split(",")
            raw[(workload, emitter)].append((int(sample), int(elapsed)))
        elif line.startswith("SUMMARY,") and not line.startswith("SUMMARY,workload,"):
            _, workload, emitter, minimum, median, maximum, speedup = line.split(",")
            summaries[(workload, emitter)] = (
                int(minimum),
                int(median),
                int(maximum),
                float(speedup),
            )

    return raw, summaries, verified


def verify(raw, summaries, verified):
    if verified != EXPECTED_WORKLOADS:
        raise AssertionError("missing correctness checks: %r" % (EXPECTED_WORKLOADS - verified))

    expected_keys = {
        (workload, emitter)
        for workload in EXPECTED_WORKLOADS
        for emitter in EXPECTED_EMITTERS
    }
    if set(raw) != expected_keys:
        raise AssertionError("unexpected raw-data keys: %r" % (set(raw) ^ expected_keys))
    if set(summaries) != expected_keys:
        raise AssertionError("unexpected summary keys: %r" % (set(summaries) ^ expected_keys))

    for key in sorted(expected_keys):
        samples = raw[key]
        if [sample for sample, _ in samples] != list(range(1, EXPECTED_SAMPLES + 1)):
            raise AssertionError("invalid sample sequence for %r" % (key,))
        values = [elapsed for _, elapsed in samples]
        expected = (min(values), int(statistics.median(values)), max(values))
        if summaries[key][:3] != expected:
            raise AssertionError(
                "summary mismatch for %r: recorded=%r calculated=%r"
                % (key, summaries[key][:3], expected)
            )

    for workload in EXPECTED_WORKLOADS:
        baseline = summaries[(workload, "bytecode")][1]
        for emitter in EXPECTED_EMITTERS:
            key = (workload, emitter)
            calculated = baseline / summaries[key][1]
            if abs(calculated - summaries[key][3]) > 0.0005:
                raise AssertionError("speedup mismatch for %r" % (key,))


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: python3 verify_results.py RESULTS.log")
    path = Path(argv[1])
    raw, summaries, verified = parse_log(path)
    verify(raw, summaries, verified)
    print("verified: %s" % path)


if __name__ == "__main__":
    main(sys.argv)
