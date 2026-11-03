#!/usr/bin/env python3
"""Check the local Pico exhibition services and their current display state."""

import argparse
import json
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen


def service_state(name):
    completed = subprocess.run(
        ["systemctl", "is-active", name],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    failures = []
    for service in ("pico-raytracing-display", "pico-raytracing-runner"):
        state = service_state(service)
        print("%-26s %s" % (service, state))
        if state != "active":
            failures.append(service + " is " + state)
    try:
        with urlopen(args.url.rstrip("/") + "/api/state", timeout=3) as response:
            state = json.load(response)
    except (OSError, URLError, json.JSONDecodeError) as exc:
        failures.append("display API: " + str(exc))
        state = {}
    mode = state.get("mode", "unknown")
    print("%-26s %s" % ("display mode", mode))
    print(
        "%-26s %s/%s"
        % (
            "workers ready",
            len(state.get("ready_node_ids", [])),
            state.get("expected_workers", 16),
        )
    )
    print(
        "%-26s %s/%s"
        % (
            "tiles",
            state.get("completed_tiles", 0),
            state.get("total_tiles", 240),
        )
    )
    if mode in ("waiting_for_manual_recovery", "display_error"):
        failures.append("display mode is " + mode)
    if failures:
        for failure in failures:
            print("NG:", failure, file=sys.stderr)
        return 1
    print("OK: 来場者向け表示は応答しています")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
