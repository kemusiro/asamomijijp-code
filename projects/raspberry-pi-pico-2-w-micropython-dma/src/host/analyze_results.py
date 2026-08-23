"""Aggregate all committed Pico 2 W DMA measurements using only stdlib."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from signal_analysis import analyse_logic_capture, analyse_pio_samples, make_vcd


MEMORY_SIZES = (256, 1024, 4096, 16384, 65536)
PIO_FREQUENCIES = (100_000, 1_000_000, 10_000_000)
SAMPLES = 31
CAPTURE_NAME = re.compile(
    r"^(?P<output>[0-9]+)Hz_(?P<sample>[0-9]+)Sps_(?P<purpose>[a-z_]+)[.]csv$"
)
LOGIC_NAME = re.compile(
    r"^capture_(?P<pattern>[0-9]+)Hz_(?P<sample>[0-9]+)Sps[.]bin$"
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def csv_text(header, rows) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def parse_benchmark(path: Path, experiment: str):
    metadata = {}
    groups = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split(",")
        if fields[0] == "META":
            metadata[fields[1]] = ",".join(fields[2:])
        elif fields[:2] == ["RESULT", experiment]:
            if experiment == "memory":
                _, _, size, method, sample, elapsed, operations = fields
                groups[(int(size), method)].append(
                    (int(sample), int(elapsed), int(operations))
                )
            else:
                _, _, frequency, method, sample, elapsed, background, ideal = fields
                groups[(int(frequency), method)].append(
                    (int(sample), int(elapsed), int(background), int(ideal))
                )
    if metadata.get("status") != "ok":
        raise ValueError(f"missing successful status in {path}")
    if int(metadata.get("samples", 0)) != SAMPLES:
        raise ValueError(f"unexpected sample count in {path}")
    expected_numbers = list(range(SAMPLES))
    for key, rows in groups.items():
        if [row[0] for row in rows] != expected_numbers:
            raise ValueError(f"invalid sample sequence for {key} in {path}")
    return metadata, groups


def build_memory_summary(raw_dir: Path):
    rows = []
    records = []
    for run, path in enumerate(sorted(raw_dir.glob("memory-run-*.csv")), 1):
        metadata, groups = parse_benchmark(path, "memory")
        if set(groups) != {
            (size, method) for size in MEMORY_SIZES for method in ("slice", "dma")
        }:
            raise ValueError(f"unexpected result groups in {path}")
        copies = int(metadata["copies_per_sample"])
        for size in MEMORY_SIZES:
            values = {}
            for method in ("slice", "dma"):
                totals = [row[1] for row in groups[(size, method)]]
                operations = {row[2] for row in groups[(size, method)]}
                if operations != {copies}:
                    raise ValueError(f"inconsistent operation count in {path}")
                values[method] = {
                    "minimum": min(totals) / copies,
                    "median": statistics.median(totals) / copies,
                    "maximum": max(totals) / copies,
                }
            speedup = values["slice"]["median"] / values["dma"]["median"]
            throughput = size * 1_000_000 / values["dma"]["median"] / 1_048_576
            record = {
                "run": run,
                "size_bytes": size,
                "samples": SAMPLES,
                "copies_per_sample": copies,
                "slice": values["slice"],
                "dma": values["dma"],
                "slice_over_dma": speedup,
                "dma_mib_s": throughput,
            }
            records.append(record)
            rows.append(
                (
                    run,
                    size,
                    SAMPLES,
                    copies,
                    f"{values['slice']['minimum']:.3f}",
                    f"{values['slice']['median']:.3f}",
                    f"{values['slice']['maximum']:.3f}",
                    f"{values['dma']['minimum']:.3f}",
                    f"{values['dma']['median']:.3f}",
                    f"{values['dma']['maximum']:.3f}",
                    f"{speedup:.3f}",
                    f"{throughput:.3f}",
                )
            )
    if len({record["run"] for record in records}) != 2:
        raise ValueError("two independent memory benchmark runs are required")
    return records, csv_text(
        (
            "run",
            "size_bytes",
            "samples",
            "copies_per_sample",
            "slice_min_us",
            "slice_median_us",
            "slice_max_us",
            "dma_min_us",
            "dma_median_us",
            "dma_max_us",
            "slice_over_dma",
            "dma_mib_s",
        ),
        rows,
    )


def build_pio_summary(raw_dir: Path):
    rows = []
    records = []
    for run, path in enumerate(sorted(raw_dir.glob("pio-run-*.csv")), 1):
        metadata, groups = parse_benchmark(path, "pio")
        if set(groups) != {
            (frequency, method)
            for frequency in PIO_FREQUENCIES
            for method in ("cpu", "dma")
        }:
            raise ValueError(f"unexpected result groups in {path}")
        pattern_bytes = int(metadata["pattern_bytes"])
        for frequency in PIO_FREQUENCIES:
            values = {}
            for method in ("cpu", "dma"):
                method_rows = groups[(frequency, method)]
                elapsed = [row[1] for row in method_rows]
                values[method] = {
                    "minimum": min(elapsed),
                    "median": int(statistics.median(elapsed)),
                    "maximum": max(elapsed),
                    "background_median": int(statistics.median(row[2] for row in method_rows)),
                }
            ideal_us = pattern_bytes * 8 * 1_000_000 / frequency
            record = {
                "run": run,
                "frequency_hz": frequency,
                "samples": SAMPLES,
                "pattern_bytes": pattern_bytes,
                "ideal_us": ideal_us,
                "cpu": values["cpu"],
                "dma": values["dma"],
            }
            records.append(record)
            rows.append(
                (
                    run,
                    frequency,
                    SAMPLES,
                    pattern_bytes,
                    f"{ideal_us:.3f}",
                    values["cpu"]["minimum"],
                    values["cpu"]["median"],
                    values["cpu"]["maximum"],
                    values["dma"]["minimum"],
                    values["dma"]["median"],
                    values["dma"]["maximum"],
                    values["dma"]["background_median"],
                )
            )
    if len({record["run"] for record in records}) != 2:
        raise ValueError("two independent PIO benchmark runs are required")
    return records, csv_text(
        (
            "run",
            "frequency_hz",
            "samples",
            "pattern_bytes",
            "ideal_us",
            "cpu_min_us",
            "cpu_median_us",
            "cpu_max_us",
            "dma_min_us",
            "dma_median_us",
            "dma_max_us",
            "dma_background_median",
        ),
        rows,
    )


def read_dio_csv(path: Path):
    packed = []
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        expected_columns = ["sample", "time_us", "dio0"]
        if reader.fieldnames not in (expected_columns, expected_columns + ["dio1"]):
            raise ValueError(f"unexpected waveform columns in {path}")
        for expected_index, row in enumerate(reader):
            if int(row["sample"]) != expected_index:
                raise ValueError(f"invalid waveform sample index in {path}")
            dio1 = int(row["dio1"]) if "dio1" in row else 0
            packed.append(int(row["dio0"]) | (dio1 << 1))
    if len(packed) != 4096:
        raise ValueError(f"expected 4096 samples in {path}")
    return packed


def read_waveform_metadata(path: Path):
    metadata = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            key = (int(row["output_hz"]), int(row["sample_hz"]), row["purpose"])
            if key in metadata:
                raise ValueError(f"duplicate waveform metadata: {key}")
            metadata[key] = {
                "dma_elapsed_us": int(row["dma_elapsed_us"]),
                "activity_toggles": (
                    int(row["activity_toggles"])
                    if row["activity_toggles"]
                    else None
                ),
                "capture_date": row["capture_date"],
            }
    return metadata


def build_waveform_summary(raw_dir: Path):
    rows = []
    records = []
    metadata = read_waveform_metadata(raw_dir / "capture-metadata.csv")
    for path in sorted(raw_dir.glob("*Hz_*Sps_*.csv")):
        match = CAPTURE_NAME.match(path.name)
        if not match:
            raise ValueError(f"unexpected capture filename: {path.name}")
        output_hz = int(match.group("output"))
        sample_hz = int(match.group("sample"))
        purpose = match.group("purpose")
        result = analyse_pio_samples(read_dio_csv(path), output_hz, sample_hz)
        capture_metadata = metadata.pop((output_hz, sample_hz, purpose), None)
        if capture_metadata is None:
            raise ValueError(f"missing capture metadata for {path.name}")
        result.update(capture_metadata)
        result["file"] = path.name
        result["purpose"] = purpose
        records.append(result)
        rows.append(
            (
                path.name,
                output_hz,
                sample_hz,
                purpose,
                result["captured_bits"],
                result["mismatch_count"],
                f"{result['bit_width_min_us']:.9f}",
                f"{result['bit_width_median_us']:.9f}",
                f"{result['bit_width_max_us']:.9f}",
                result["dio1_transition_count"],
                "" if result["dio1_transition_interval_median_us"] is None else f"{result['dio1_transition_interval_median_us']:.9f}",
                result["dma_elapsed_us"],
                "" if result["activity_toggles"] is None else result["activity_toggles"],
                result["capture_date"],
            )
        )
    if metadata:
        raise ValueError(f"capture metadata without CSV: {sorted(metadata)}")
    return records, csv_text(
        (
            "file",
            "output_hz",
            "sample_hz",
            "purpose",
            "captured_bits",
            "mismatch_count",
            "bit_width_min_us",
            "bit_width_median_us",
            "bit_width_max_us",
            "dio1_transition_count",
            "dio1_transition_interval_median_us",
            "dma_elapsed_us",
            "activity_toggles",
            "capture_date",
        ),
        rows,
    )


def read_logic_timings(path: Path):
    result = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            key = (int(row["pattern_hz"]), int(row["sample_hz"]))
            if key in result:
                raise ValueError(f"duplicate logic-analyzer timing: {key}")
            result[key] = {
                "capture_bytes": int(row["capture_bytes"]),
                "ideal_us_truncated": int(row["ideal_us_truncated"]),
                "dma_us": int(row["dma_us"]),
                "cpu_us": int(row["cpu_us"]),
                "background_iterations": int(row["background_iterations"]),
                "checksum": row["checksum"],
                "capture_date": row["capture_date"],
            }
    return result


def build_logic_summary(raw_dir: Path):
    timings = read_logic_timings(raw_dir / "timings.csv")
    rows = []
    records = []
    vcd_outputs = {}
    for path in sorted(raw_dir.glob("capture_*Sps.bin")):
        match = LOGIC_NAME.match(path.name)
        if not match:
            raise ValueError(f"unexpected logic capture filename: {path.name}")
        pattern_hz = int(match.group("pattern"))
        sample_hz = int(match.group("sample"))
        key = (pattern_hz, sample_hz)
        timing = timings.pop(key, None)
        if timing is None:
            raise ValueError(f"missing timing row for {path.name}")
        capture = path.read_bytes()
        if len(capture) != timing["capture_bytes"]:
            raise ValueError(f"capture size mismatch for {path.name}")
        analysis = analyse_logic_capture(capture, pattern_hz, sample_hz)
        analysis.update(timing)
        analysis["file"] = path.name
        analysis["ideal_us"] = len(capture) * 8 * 1_000_000 / sample_hz
        analysis["cpu_over_dma"] = timing["cpu_us"] / timing["dma_us"]
        records.append(analysis)
        rows.append(
            (
                path.name,
                pattern_hz,
                sample_hz,
                len(capture),
                f"{analysis['ideal_us']:.3f}",
                timing["dma_us"],
                timing["cpu_us"],
                f"{analysis['cpu_over_dma']:.3f}",
                timing["background_iterations"],
                timing["checksum"],
                analysis["recovered_bits"],
                analysis["bit_errors"],
                f"{analysis['normalized_bit_samples_min']:.3f}",
                f"{analysis['normalized_bit_samples_median']:.3f}",
                f"{analysis['normalized_bit_samples_max']:.3f}",
            )
        )
        stem = path.stem
        vcd_outputs[f"vcd/{stem}.vcd"] = make_vcd(
            capture, sample_hz, timing["capture_date"]
        )
    if timings:
        raise ValueError(f"timing rows without captures: {sorted(timings)}")
    return records, csv_text(
        (
            "file",
            "pattern_hz",
            "sample_hz",
            "capture_bytes",
            "ideal_us",
            "dma_us",
            "cpu_us",
            "cpu_over_dma",
            "background_iterations",
            "checksum",
            "recovered_bits",
            "bit_errors",
            "bit_samples_min",
            "bit_samples_median",
            "bit_samples_max",
        ),
        rows,
    ), vcd_outputs


def rounded_record(record):
    if isinstance(record, float):
        return round(record, 9)
    if isinstance(record, dict):
        return {key: rounded_record(value) for key, value in record.items()}
    if isinstance(record, list):
        return [rounded_record(value) for value in record]
    return record


def build_outputs(root: Path | None = None):
    root = root or project_root()
    raw = root / "results" / "raw"
    memory, memory_csv = build_memory_summary(raw / "benchmarks")
    pio, pio_csv = build_pio_summary(raw / "benchmarks")
    pio_waveforms, pio_waveform_csv = build_waveform_summary(raw / "pio-waveforms")
    cpu_activity, cpu_activity_csv = build_waveform_summary(raw / "cpu-activity")
    logic, logic_csv, vcd_outputs = build_logic_summary(raw / "logic-analyzer")

    run2_memory = [record for record in memory if record["run"] == 2]
    run2_pio = [record for record in pio if record["run"] == 2]
    article_values = rounded_record(
        {
            "measurement_date": "2026-08-23",
            "memory_run_2": run2_memory,
            "pio_run_2": run2_pio,
            "pio_waveforms": pio_waveforms,
            "cpu_activity": cpu_activity,
            "logic_analyzer": logic,
        }
    )
    outputs = {
        "summary/memory.csv": memory_csv,
        "summary/pio.csv": pio_csv,
        "summary/pio-waveforms.csv": pio_waveform_csv,
        "summary/cpu-activity.csv": cpu_activity_csv,
        "summary/logic-analyzer.csv": logic_csv,
        "summary/article-values.json": json.dumps(
            article_values, indent=2, ensure_ascii=False
        )
        + "\n",
    }
    outputs.update(vcd_outputs)
    return outputs, article_values


def manifest_text(results_dir: Path) -> str:
    rows = []
    for group in ("raw", "summary", "vcd"):
        for path in sorted((results_dir / group).rglob("*")):
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                rows.append(f"{digest}  {path.relative_to(results_dir).as_posix()}")
    return "\n".join(rows) + "\n"


def write_outputs(root: Path, outputs):
    results = root / "results"
    for relative, content in outputs.items():
        path = results / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (results / "SHA256SUMS").write_text(manifest_text(results), encoding="utf-8")


def check_outputs(root: Path, outputs):
    results = root / "results"
    for relative, expected in outputs.items():
        path = results / relative
        if not path.exists():
            raise ValueError(f"missing generated result: {relative}")
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise ValueError(f"generated result is stale: {relative}")
    expected_manifest = manifest_text(results)
    manifest_path = results / "SHA256SUMS"
    if manifest_path.read_text(encoding="utf-8") != expected_manifest:
        raise ValueError("results/SHA256SUMS is stale")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = project_root()
    outputs, article_values = build_outputs(root)
    if args.write:
        write_outputs(root, outputs)
        print("generated results/summary, results/vcd, and results/SHA256SUMS")
    else:
        check_outputs(root, outputs)
        print("verified generated summaries and VCD files")
    print(json.dumps(article_values, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
