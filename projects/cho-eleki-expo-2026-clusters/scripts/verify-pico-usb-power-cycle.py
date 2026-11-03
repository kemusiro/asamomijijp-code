#!/usr/bin/env python3
"""USB hubの電源再投入でPico serial deviceが全台復旧することを確認する。"""

import argparse
import glob
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def discover_devices():
    mac_devices = sorted(glob.glob("/dev/cu.usbmodem*"))
    if mac_devices:
        return mac_devices
    return sorted(glob.glob("/dev/ttyACM*"))


def write_event(output_path, started, phase, devices):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "phase": phase,
        "count": len(devices),
        "devices": devices,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def main():
    parser = argparse.ArgumentParser(
        description="Pico USB hubのOFF、ON、全台安定復帰を監視する"
    )
    parser.add_argument("--expected", type=int, default=16, help="期待する台数")
    parser.add_argument(
        "--timeout", type=float, default=600, help="電源再投入試験全体の期限（秒）"
    )
    parser.add_argument(
        "--off-min-seconds",
        type=float,
        default=5,
        help="0台を維持する最短時間（秒）",
    )
    parser.add_argument(
        "--stable-seconds",
        type=float,
        default=30,
        help="復帰後に全台を維持する時間（秒）",
    )
    parser.add_argument(
        "--interval", type=float, default=0.25, help="確認間隔（秒）"
    )
    parser.add_argument(
        "--output", type=Path, help="snapshotを追記するJSON Lines file"
    )
    args = parser.parse_args()
    if args.expected <= 0:
        parser.error("--expectedは1以上にしてください")
    for name in ("timeout", "off_min_seconds", "stable_seconds", "interval"):
        if getattr(args, name) <= 0:
            parser.error("時間指定は0より大きくしてください")

    started = time.monotonic()
    deadline = started + args.timeout
    baseline = discover_devices()
    write_event(args.output, started, "baseline", baseline)
    if len(baseline) != args.expected:
        print(
            "NG: 開始時のserial deviceが%d/%d台" % (len(baseline), args.expected),
            file=sys.stderr,
        )
        return 1

    print("開始: %d台。USBハブの電源OFFを待機" % args.expected, flush=True)
    phase = "wait_for_off"
    previous = baseline
    zero_since = None
    stable_since = None
    off_confirmed_at = None
    recovered_at = None

    while time.monotonic() < deadline:
        now = time.monotonic()
        devices = discover_devices()
        if devices != previous:
            event = write_event(args.output, started, phase, devices)
            print(
                "%s: %d台 (%.3f秒)"
                % (phase, len(devices), event["elapsed_seconds"]),
                flush=True,
            )
            previous = devices

        if phase == "wait_for_off":
            if not devices:
                zero_since = zero_since or now
                if now - zero_since >= args.off_min_seconds:
                    off_confirmed_at = now
                    phase = "wait_for_recovery"
                    write_event(args.output, started, "off_confirmed", devices)
                    print(
                        "OFF確認: 0台を%.1f秒維持。再給電を待機"
                        % args.off_min_seconds,
                        flush=True,
                    )
            else:
                zero_since = None
        elif phase == "wait_for_recovery":
            if devices == baseline:
                recovered_at = now
                stable_since = now
                phase = "verify_stable"
                write_event(args.output, started, "recovered", devices)
                print("復帰確認: %d台。安定監視を開始" % args.expected, flush=True)
        elif phase == "verify_stable":
            if devices != baseline:
                print("NG: 復帰後にdevice集合が変化", file=sys.stderr)
                return 1
            if now - stable_since >= args.stable_seconds:
                write_event(args.output, started, "passed", devices)
                print(
                    "OK: OFF %.1f秒以上、復帰%.1f秒、復帰後%d台を%.1f秒維持"
                    % (
                        args.off_min_seconds,
                        recovered_at - off_confirmed_at,
                        args.expected,
                        args.stable_seconds,
                    )
                )
                return 0

        time.sleep(args.interval)

    print("NG: 電源再投入試験が%.1f秒で期限切れ" % args.timeout, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
