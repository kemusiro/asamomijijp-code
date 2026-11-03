#!/usr/bin/env python3
"""Pico USB serial deviceの列挙状態を一定時間監視する。"""

import argparse
import glob
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def discover_devices():
    """macOSまたはLinuxでPico候補のserial deviceを重複なく返す。"""
    mac_devices = sorted(glob.glob("/dev/cu.usbmodem*"))
    if mac_devices:
        return mac_devices
    return sorted(glob.glob("/dev/ttyACM*"))


def write_event(output_path, event):
    if output_path is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Pico USB serial device数と再列挙を監視する"
    )
    parser.add_argument("--expected", type=int, default=16, help="期待する台数")
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="監視秒数。0は1回だけ確認する",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="確認間隔（秒）"
    )
    parser.add_argument(
        "--output", type=Path, help="全snapshotを追記するJSON Lines file"
    )
    args = parser.parse_args()
    if args.expected < 0:
        parser.error("--expectedは0以上にしてください")
    if args.duration < 0:
        parser.error("--durationは0以上にしてください")
    if args.interval <= 0:
        parser.error("--intervalは0より大きくしてください")

    started = time.monotonic()
    deadline = started + args.duration
    baseline = None
    previous = None
    sample_count = 0
    failures = []

    while True:
        devices = discover_devices()
        sample_count += 1
        changed = baseline is not None and devices != baseline
        changed_since_previous = previous is not None and devices != previous
        count_ok = len(devices) == args.expected
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "expected": args.expected,
            "count": len(devices),
            "devices": devices,
            "changed_from_baseline": changed,
            "count_ok": count_ok,
        }
        write_event(args.output, event)

        if baseline is None:
            baseline = devices
            print("開始: %d/%d台" % (len(devices), args.expected))
            for device in devices:
                print("  " + device)
            if not count_ok:
                failures.append(
                    "%.3f秒: serial deviceが%d/%d台"
                    % (event["elapsed_seconds"], len(devices), args.expected)
                )
        elif changed_since_previous:
            failures.append(
                "%.3f秒: device集合が変化し%d/%d台"
                % (event["elapsed_seconds"], len(devices), args.expected)
            )
            print("変化検出: " + ", ".join(devices), file=sys.stderr)
        previous = devices

        if args.duration == 0 or time.monotonic() >= deadline:
            break
        time.sleep(min(args.interval, max(0, deadline - time.monotonic())))

    elapsed = time.monotonic() - started
    if failures:
        for failure in dict.fromkeys(failures):
            print("NG: " + failure, file=sys.stderr)
        print(
            "NG: %.1f秒、%d回の監視中にUSB列挙異常を検出" % (elapsed, sample_count),
            file=sys.stderr,
        )
        return 1
    print("OK: %.1f秒、%d回の監視で%d台を維持" % (elapsed, sample_count, args.expected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
