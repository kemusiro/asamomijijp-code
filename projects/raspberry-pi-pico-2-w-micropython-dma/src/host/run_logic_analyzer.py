"""Drive an AD2 pattern into GP18 and collect PIO+DMA captures."""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import subprocess
import time
from ctypes import byref, c_double, c_int, c_ubyte
from pathlib import Path

from dwf_utils import check, last_error, load_dwf
from signal_analysis import PATTERN_BYTES, analyse_logic_capture, make_vcd


DIO_PIN = 2
DIGITAL_OUT_TYPE_CUSTOM = 1
DIGITAL_OUT_IDLE_LOW = 1
CAPTURES = (
    (1_000_000, 10_000_000),
    (5_000_000, 50_000_000),
    (10_000_000, 100_000_000),
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_pico_result(line: str):
    fields = line.split(",")
    if fields[0] != "RESULT" or len(fields) != 11:
        raise ValueError(f"unexpected Pico result: {line}")
    values = dict(zip(fields[1::2], fields[2::2]))
    return {
        "ideal_us_truncated": int(values["ideal_us"]),
        "dma_us": int(values["dma_us"]),
        "cpu_us": int(values["cpu_us"]),
        "background_iterations": int(values["background_iterations"]),
        "checksum": values["checksum"],
    }


def run_pico(args, sample_hz: int):
    expression = (
        "CAPTURE_SAMPLE_HZ=%d; exec(open('/remote/src/pico/logic_analyzer.py').read())"
        % sample_hz
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
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        raise RuntimeError(f"mpremote failed:\n{output}")
    lines = output.splitlines()
    data_lines = tuple(line for line in lines if line.startswith("DATA,"))
    result_lines = tuple(line for line in lines if line.startswith("RESULT,"))
    if len(data_lines) != 1 or len(result_lines) != 1 or "STATUS,ok" not in lines:
        raise RuntimeError(f"unexpected Pico output:\n{output}")
    return bytes.fromhex(data_lines[0][5:]), parse_pico_result(result_lines[0])


def configure_pattern(dwf, handle, internal_clock_hz, pattern_hz):
    divider = int(round(internal_clock_hz / pattern_hz))
    if internal_clock_hz / divider != pattern_hz:
        raise ValueError("pattern rate cannot be represented exactly")
    pattern_data = (c_ubyte * len(PATTERN_BYTES))(*PATTERN_BYTES)
    check(dwf, dwf.FDwfDigitalOutReset(handle), "DigitalOutReset")
    check(
        dwf,
        dwf.FDwfDigitalOutEnableSet(handle, c_int(DIO_PIN), c_int(1)),
        "EnableSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalOutTypeSet(
            handle, c_int(DIO_PIN), c_int(DIGITAL_OUT_TYPE_CUSTOM)
        ),
        "TypeSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalOutIdleSet(
            handle, c_int(DIO_PIN), c_int(DIGITAL_OUT_IDLE_LOW)
        ),
        "IdleSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalOutDividerSet(handle, c_int(DIO_PIN), c_int(divider)),
        "DividerSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalOutDataSet(
            handle,
            c_int(DIO_PIN),
            byref(pattern_data),
            c_int(len(PATTERN_BYTES) * 8),
        ),
        "DataSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalOutConfigure(handle, c_int(1)),
        "DigitalOutConfigure",
    )
    time.sleep(0.05)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mpremote", default=os.environ.get("MPREMOTE", "mpremote"))
    parser.add_argument("--port", default="auto")
    parser.add_argument("--dwf")
    parser.add_argument(
        "--capture-date", default=datetime.date.today().isoformat()
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root() / "results" / "raw" / "logic-analyzer",
    )
    parser.add_argument("--vcd-dir", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    default_raw = project_root() / "results" / "raw" / "logic-analyzer"
    vcd_dir = args.vcd_dir
    if vcd_dir is None:
        vcd_dir = (
            project_root() / "results" / "vcd"
            if args.output_dir.resolve() == default_raw.resolve()
            else args.output_dir / "vcd"
        )
    vcd_dir.mkdir(parents=True, exist_ok=True)

    dwf = load_dwf(args.dwf)
    handle = c_int()
    check(dwf, dwf.FDwfDeviceOpen(c_int(-1), byref(handle)), "DeviceOpen")
    if handle.value == 0:
        raise RuntimeError(f"device handle is zero: {last_error(dwf)}")
    internal_clock = c_double()
    check(
        dwf,
        dwf.FDwfDigitalOutInternalClockInfo(handle, byref(internal_clock)),
        "InternalClockInfo",
    )

    rows = []
    try:
        for pattern_hz, sample_hz in CAPTURES:
            configure_pattern(dwf, handle, internal_clock.value, pattern_hz)
            capture, timing = run_pico(args, sample_hz)
            analysis = analyse_logic_capture(capture, pattern_hz, sample_hz)
            analysis.update(timing)
            analysis["capture_date"] = args.capture_date

            stem = f"capture_{pattern_hz}Hz_{sample_hz}Sps"
            (args.output_dir / f"{stem}.bin").write_bytes(capture)
            (vcd_dir / f"{stem}.vcd").write_text(
                make_vcd(capture, sample_hz, args.capture_date),
                encoding="utf-8",
            )
            rows.append(
                (
                    pattern_hz,
                    sample_hz,
                    len(capture),
                    timing["ideal_us_truncated"],
                    timing["dma_us"],
                    timing["cpu_us"],
                    timing["background_iterations"],
                    timing["checksum"],
                    args.capture_date,
                )
            )
            print(
                "RESULT,pattern_hz=%d,sample_hz=%d,dma_us=%d,cpu_us=%d,"
                "recovered_bits=%d,bit_errors=%d"
                % (
                    pattern_hz,
                    sample_hz,
                    timing["dma_us"],
                    timing["cpu_us"],
                    analysis["recovered_bits"],
                    analysis["bit_errors"],
                )
            )
    finally:
        dwf.FDwfDigitalOutReset(handle)
        dwf.FDwfDeviceClose(handle)

    with (args.output_dir / "timings.csv").open(
        "w", newline="", encoding="utf-8"
    ) as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            (
                "pattern_hz",
                "sample_hz",
                "capture_bytes",
                "ideal_us_truncated",
                "dma_us",
                "cpu_us",
                "background_iterations",
                "checksum",
                "capture_date",
            )
        )
        writer.writerows(rows)
    print("STATUS,ok")


if __name__ == "__main__":
    main()
