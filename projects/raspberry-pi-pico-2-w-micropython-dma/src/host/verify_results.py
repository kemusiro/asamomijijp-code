"""Verify raw measurements, generated files, article values, and publication safety."""

from __future__ import annotations

from pathlib import Path

from analyze_results import build_outputs, check_outputs, project_root


EXPECTED_MEMORY = {
    256: (8.30, 22.35, 23.30, 24.45, 0.356, 10.478),
    1024: (12.45, 22.00, 23.25, 24.60, 0.535, 42.003),
    4096: (29.35, 25.55, 26.55, 27.70, 1.105, 147.128),
    16384: (95.85, 46.80, 47.80, 48.65, 2.005, 326.883),
    65536: (362.10, 129.55, 130.55, 131.20, 2.774, 478.744),
}
EXPECTED_PIO = {
    100_000: (1_310_720.0, 1_310_346, 1_310_395, 285_258),
    1_000_000: (131_072.0, 131_054, 131_101, 28_518),
    10_000_000: (13_107.2, 13_139, 13_172, 2_843),
}
EXPECTED_ACTIVITY = {
    100_000: (10_000_000, 39, 140_589, 40, 9.30),
    1_000_000: (10_000_000, 354, 14_056, 35, 9.30),
    10_000_000: (20_000_000, 1755, 1_402, 15, 9.35),
}
EXPECTED_LOGIC = {
    1_000_000: (10_000_000, 13_107.2, 13_138, 71_558, 5.447, 2_098),
    5_000_000: (50_000_000, 2_621.44, 2_651, 71_171, 26.847, 403),
    10_000_000: (100_000_000, 1_310.72, 1_340, 71_208, 53.140, 190),
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "/private/" + "tmp/",
    "usbmodem" + "313",
    "ken" + "ichi",
)


def assert_close(actual, expected, digits=3):
    if round(actual, digits) != round(expected, digits):
        raise AssertionError(f"{actual!r} != {expected!r} at {digits} digits")


def verify_article_values(values):
    memory = {record["size_bytes"]: record for record in values["memory_run_2"]}
    if set(memory) != set(EXPECTED_MEMORY):
        raise AssertionError("unexpected memory buffer sizes")
    for size, expected in EXPECTED_MEMORY.items():
        record = memory[size]
        actual = (
            record["slice"]["median"],
            record["dma"]["minimum"],
            record["dma"]["median"],
            record["dma"]["maximum"],
            record["slice_over_dma"],
            record["dma_mib_s"],
        )
        for observed, wanted in zip(actual, expected):
            assert_close(observed, wanted)

    pio = {record["frequency_hz"]: record for record in values["pio_run_2"]}
    if set(pio) != set(EXPECTED_PIO):
        raise AssertionError("unexpected PIO frequencies")
    for frequency, expected in EXPECTED_PIO.items():
        record = pio[frequency]
        actual = (
            record["ideal_us"],
            record["cpu"]["median"],
            record["dma"]["median"],
            record["dma"]["background_median"],
        )
        for observed, wanted in zip(actual, expected):
            assert_close(observed, wanted)

    activity = {record["output_hz"]: record for record in values["cpu_activity"]}
    if set(activity) != set(EXPECTED_ACTIVITY):
        raise AssertionError("unexpected CPU activity frequencies")
    for frequency, expected in EXPECTED_ACTIVITY.items():
        record = activity[frequency]
        actual = (
            record["sample_hz"],
            record["captured_bits"],
            record["activity_toggles"],
            record["dio1_transition_count"],
            record["dio1_transition_interval_median_us"],
        )
        for observed, wanted in zip(actual, expected):
            assert_close(observed, wanted)
        if record["mismatch_count"] != 0:
            raise AssertionError("GP16 pattern mismatch during CPU activity capture")

    logic = {record["pattern_hz"]: record for record in values["logic_analyzer"]}
    if set(logic) != set(EXPECTED_LOGIC):
        raise AssertionError("unexpected logic-analyzer frequencies")
    for frequency, expected in EXPECTED_LOGIC.items():
        record = logic[frequency]
        actual = (
            record["sample_hz"],
            record["ideal_us"],
            record["dma_us"],
            record["cpu_us"],
            record["cpu_over_dma"],
            record["background_iterations"],
        )
        for observed, wanted in zip(actual, expected):
            assert_close(observed, wanted)
        if record["recovered_bits"] != 13_100 or record["bit_errors"] != 0:
            raise AssertionError("logic-analyzer pattern recovery failed")
        if (
            record["normalized_bit_samples_min"],
            record["normalized_bit_samples_median"],
            record["normalized_bit_samples_max"],
        ) != (9.0, 10.0, 11.0):
            raise AssertionError("unexpected samples-per-bit range")

    waveforms = values["pio_waveforms"]
    if len(waveforms) != 5 or any(row["mismatch_count"] for row in waveforms):
        raise AssertionError("PIO waveform validation failed")
    continuity = [row for row in waveforms if row["purpose"] in ("continuity", "combined")]
    if {row["output_hz"] for row in continuity} != {100_000, 1_000_000, 10_000_000}:
        raise AssertionError("missing PIO continuity frequency")
    if any(row["captured_bits"] != 354 for row in continuity):
        raise AssertionError("PIO continuity capture is shorter than 354 bits")


def verify_cross_run_stability(root: Path):
    from analyze_results import build_memory_summary, build_pio_summary

    memory, _ = build_memory_summary(root / "results" / "raw" / "benchmarks")
    pio, _ = build_pio_summary(root / "results" / "raw" / "benchmarks")

    for method, maximum in (("slice", 1.190), ("dma", 0.378)):
        differences = []
        for size in EXPECTED_MEMORY:
            medians = [
                record[method]["median"]
                for record in memory
                if record["size_bytes"] == size
            ]
            differences.append(abs((medians[1] - medians[0]) / medians[0] * 100))
        if round(max(differences), 3) > maximum:
            raise AssertionError(f"memory cross-run variation exceeds {maximum}%")

    for method in ("cpu", "dma"):
        for frequency in EXPECTED_PIO:
            medians = [
                record[method]["median"]
                for record in pio
                if record["frequency_hz"] == frequency
            ]
            difference = abs((medians[1] - medians[0]) / medians[0] * 100)
            if round(difference, 3) > 0.001:
                raise AssertionError("PIO cross-run variation exceeds 0.001%")


def verify_cleanup_and_connectivity(root: Path):
    connectivity = (
        root / "results" / "raw" / "logic-analyzer" / "connectivity.log"
    ).read_text(encoding="utf-8")
    if connectivity != "RESULT,low_before,0,high,101,low_after,0\nSTATUS,ok\n":
        raise AssertionError("connectivity check did not pass")

    cleanup = root / "results" / "raw" / "benchmarks" / "cleanup-test.log"
    if not cleanup.exists():
        raise AssertionError("missing cleanup-test.log")
    required = {
        "VERIFY,active_before_exception,1",
        "VERIFY,exception_caught,1",
        "VERIFY,state_machine_active_after_cleanup,0",
        "VERIFY,gp16_after_cleanup,0",
        "STATUS,ok",
    }
    lines = set(cleanup.read_text(encoding="utf-8").splitlines())
    if not required <= lines:
        raise AssertionError("cleanup test did not pass")
    first = next(line for line in lines if line.startswith("VERIFY,first_dma_channel,"))
    replacement = next(
        line for line in lines if line.startswith("VERIFY,replacement_dma_channel,")
    )
    if first.rsplit(",", 1)[1] != replacement.rsplit(",", 1)[1]:
        raise AssertionError("DMA channel was not reused after cleanup")


def verify_source_and_privacy(root: Path):
    checked_suffixes = {".py", ".md", ".csv", ".json", ".vcd", ".log"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in checked_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            compile(text, str(path), "exec")
        for marker in FORBIDDEN_TEXT:
            if marker in text:
                raise AssertionError(f"private host marker {marker!r} in {path}")

    source = root / "src" / "pico"
    expected_fragments = {
        "memory_benchmark.py": ("size=2", "inc_read=True", "inc_write=True"),
        "pio_tx_benchmark.py": ("size=0", "treq_sel=PIO0_SM0_TX_DREQ"),
        "logic_analyzer.py": ("size=2", "treq_sel=PIO0_SM0_RX_DREQ"),
    }
    for name, fragments in expected_fragments.items():
        text = (source / name).read_text(encoding="utf-8")
        if not all(fragment in text for fragment in fragments):
            raise AssertionError(f"missing DMA configuration in {name}")


def main():
    root = project_root()
    outputs, article_values = build_outputs(root)
    check_outputs(root, outputs)
    verify_article_values(article_values)
    verify_cross_run_stability(root)
    verify_cleanup_and_connectivity(root)
    verify_source_and_privacy(root)
    print("verified: raw logs and sample counts")
    print("verified: generated summaries, VCD files, and SHA256SUMS")
    print("verified: article values and cross-run stability")
    print("verified: cleanup, connectivity, and publication-safety checks")


if __name__ == "__main__":
    main()
