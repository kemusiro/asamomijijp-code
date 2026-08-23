"""Capture GP16 and optional GP17 activity with an Analog Discovery 2."""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import select
import subprocess
import time
from ctypes import byref, c_byte, c_double, c_int, c_ubyte, c_uint
from pathlib import Path

from dwf_utils import check, last_error, load_dwf
from signal_analysis import analyse_pio_samples


BUFFER_SAMPLES = 4096
SAMPLES_AFTER_TRIGGER = 3500
DIO_BIT = 0
TRIGSRC_DETECTOR_DIGITAL_IN = 3
STATE_DONE = 2

OUTPUT_CAPTURES = (
    (100_000, 10_000_000, "precision"),
    (100_000, 1_000_000, "continuity"),
    (1_000_000, 100_000_000, "precision"),
    (1_000_000, 10_000_000, "continuity"),
    (10_000_000, 100_000_000, "combined"),
)
ACTIVITY_CAPTURES = (
    (100_000, 10_000_000, "cpu_signal"),
    (1_000_000, 10_000_000, "cpu_signal"),
    (10_000_000, 20_000_000, "cpu_signal"),
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def start_pico(args, frequency_hz: int):
    pico_script = (
        "pio_cpu_activity_capture.py"
        if args.mode == "activity"
        else "pio_output_capture.py"
    )
    expression = (
        "CAPTURE_FREQUENCY_HZ=%d; exec(open('/remote/src/pico/%s').read())"
        % (frequency_hz, pico_script)
    )
    command = (
        args.mpremote,
        "connect",
        args.port,
        "mount",
        str(project_root()),
        "exec",
        expression,
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_lines = []
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        readable, _, _ = select.select((process.stdout,), (), (), 0.1)
        if not readable:
            if process.poll() is not None:
                break
            continue
        line = process.stdout.readline()
        if not line:
            continue
        output_lines.append(line.rstrip())
        if line.startswith("READY,"):
            return process, output_lines
    process.terminate()
    remaining, _ = process.communicate(timeout=2)
    if remaining:
        output_lines.extend(remaining.splitlines())
    raise RuntimeError(f"Pico did not become ready: {output_lines}")


def finish_pico(process, output_lines):
    remaining, _ = process.communicate(timeout=10)
    if remaining:
        output_lines.extend(remaining.splitlines())
    if process.returncode != 0:
        raise RuntimeError(f"mpremote failed: {output_lines}")
    selected = [
        line for line in output_lines if line.startswith(("READY,", "DONE,"))
    ]
    if not any(line.startswith("DONE,") for line in selected):
        raise RuntimeError(f"Pico output did not finish: {output_lines}")
    return selected


def configure_capture(dwf, handle, internal_clock_hz: float, sample_hz: int):
    divider = int(round(internal_clock_hz / sample_hz))
    if internal_clock_hz / divider != sample_hz:
        raise ValueError("sample rate cannot be represented exactly")
    check(dwf, dwf.FDwfDigitalInReset(handle), "DigitalInReset")
    check(dwf, dwf.FDwfDigitalInDividerSet(handle, c_uint(divider)), "DividerSet")
    check(dwf, dwf.FDwfDigitalInSampleFormatSet(handle, c_int(8)), "SampleFormatSet")
    check(
        dwf,
        dwf.FDwfDigitalInBufferSizeSet(handle, c_int(BUFFER_SAMPLES)),
        "BufferSizeSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalInTriggerSourceSet(
            handle, c_ubyte(TRIGSRC_DETECTOR_DIGITAL_IN)
        ),
        "TriggerSourceSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalInTriggerPositionSet(handle, c_uint(SAMPLES_AFTER_TRIGGER)),
        "TriggerPositionSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalInTriggerAutoTimeoutSet(handle, c_double(0)),
        "AutoTimeoutSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalInTriggerSet(
            handle, c_uint(0), c_uint(0), c_uint(1 << DIO_BIT), c_uint(0)
        ),
        "TriggerSet",
    )


def capture_one(dwf, handle, internal_clock_hz, args, output_hz, sample_hz, purpose):
    configure_capture(dwf, handle, internal_clock_hz, sample_hz)
    process, pico_output = start_pico(args, output_hz)
    try:
        check(
            dwf,
            dwf.FDwfDigitalInConfigure(handle, c_int(0), c_int(1)),
            "DigitalInConfigure",
        )
        pico_output = finish_pico(process, pico_output)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=2)

    state = c_byte()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        check(
            dwf,
            dwf.FDwfDigitalInStatus(handle, c_int(1), byref(state)),
            "DigitalInStatus",
        )
        if state.value == STATE_DONE:
            break
        time.sleep(0.001)
    else:
        raise RuntimeError(f"logic capture timed out, state={state.value}")

    data = (c_ubyte * BUFFER_SAMPLES)()
    check(
        dwf,
        dwf.FDwfDigitalInStatusData(handle, data, c_int(BUFFER_SAMPLES)),
        "DigitalInStatusData",
    )
    samples = tuple(data)
    result = analyse_pio_samples(samples, output_hz, sample_hz)
    result["purpose"] = purpose
    result["pico_output"] = pico_output
    return samples, result


def save_csv(path: Path, samples, sample_hz: int):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("sample", "time_us", "dio0", "dio1"))
        for index, sample in enumerate(samples):
            writer.writerow(
                (
                    index,
                    "%.9f" % (index / sample_hz * 1_000_000),
                    sample & 1,
                    (sample >> 1) & 1,
                )
            )


def parse_done_line(lines):
    line = next(line for line in lines if line.startswith("DONE,"))
    fields = dict(field.split("=", 1) for field in line.split(",")[1:])
    return int(fields["dma_elapsed_us"]), int(fields.get("activity_toggles", 0))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("output", "activity"), default="output")
    parser.add_argument("--mpremote", default=os.environ.get("MPREMOTE", "mpremote"))
    parser.add_argument("--port", default="auto")
    parser.add_argument("--dwf")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--capture-date", default=datetime.date.today().isoformat())
    return parser.parse_args()


def main():
    args = parse_args()
    if args.output_dir is None:
        leaf = "cpu-activity" if args.mode == "activity" else "pio-waveforms"
        args.output_dir = project_root() / "results" / "raw" / leaf
    args.output_dir.mkdir(parents=True, exist_ok=True)
    captures = ACTIVITY_CAPTURES if args.mode == "activity" else OUTPUT_CAPTURES

    dwf = load_dwf(args.dwf)
    handle = c_int()
    check(dwf, dwf.FDwfDeviceOpen(c_int(-1), byref(handle)), "DeviceOpen")
    if handle.value == 0:
        raise RuntimeError(f"device handle is zero: {last_error(dwf)}")
    clock_hz = c_double()
    check(
        dwf,
        dwf.FDwfDigitalInInternalClockInfo(handle, byref(clock_hz)),
        "ClockInfo",
    )
    metadata_rows = []
    try:
        for output_hz, sample_hz, purpose in captures:
            samples, result = capture_one(
                dwf,
                handle,
                clock_hz.value,
                args,
                output_hz,
                sample_hz,
                purpose,
            )
            stem = f"{output_hz}Hz_{sample_hz}Sps_{purpose}"
            save_csv(args.output_dir / f"{stem}.csv", samples, sample_hz)
            dma_elapsed_us, activity_toggles = parse_done_line(result["pico_output"])
            metadata_rows.append(
                (
                    output_hz,
                    sample_hz,
                    purpose,
                    dma_elapsed_us,
                    activity_toggles if args.mode == "activity" else "",
                    args.capture_date,
                )
            )
            print(
                "RESULT,output_hz=%d,sample_hz=%d,purpose=%s,bits=%d,"
                "mismatches=%d,median_us=%.9f,dio1_edges=%d"
                % (
                    output_hz,
                    sample_hz,
                    purpose,
                    result["captured_bits"],
                    result["mismatch_count"],
                    result["bit_width_median_us"],
                    result["dio1_transition_count"],
                )
            )
    finally:
        dwf.FDwfDeviceClose(handle)

    with (args.output_dir / "capture-metadata.csv").open(
        "w", newline="", encoding="utf-8"
    ) as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            (
                "output_hz",
                "sample_hz",
                "purpose",
                "dma_elapsed_us",
                "activity_toggles",
                "capture_date",
            )
        )
        writer.writerows(metadata_rows)
    print("STATUS,ok")


if __name__ == "__main__":
    main()
