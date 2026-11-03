#!/usr/bin/env python3
"""Inject one ray-worker stall and verify same-cycle recovery."""

import argparse
import json
from pathlib import Path
import select
import shlex
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--target-port", required=True)
    parser.add_argument("--target-node-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--job-prefix", required=True)
    parser.add_argument("--cycle-seconds", type=float, default=40)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    return args


def main():
    args = parse_args()
    try:
        from mpremote.transport_serial import SerialTransport
    except ImportError as exc:
        raise RuntimeError("mpremote is required") from exc

    remote_output = args.remote_root.rstrip("/") + "/" + args.job_prefix
    runner = args.remote_root.rstrip("/") + "/scripts/run-pico-raytracing-exhibition.py"
    remote_command = " ".join(
        shlex.quote(item)
        for item in (
            "python3",
            "-u",
            runner,
            "--cycles",
            "1",
            "--cycle-seconds",
            str(args.cycle_seconds),
            "--minimum-display-seconds",
            "2",
            "--output-dir",
            remote_output,
            "--job-prefix",
            args.job_prefix,
        )
    )
    board = SerialTransport(args.target_port)
    process = None
    try:
        board.enter_raw_repl(soft_reset=False)
        board.exec("import machine; machine.WDT(timeout=8000).feed()")
        identity = board.exec(
            "import network_config; print(network_config.NODE_ID)"
        ).decode().strip()
        if identity != args.target_node_id:
            raise RuntimeError("unexpected node: " + identity)
        board.exec("import machine; machine.WDT(timeout=8000).feed()")
        process = subprocess.Popen(
            ["ssh", "-o", "BatchMode=yes", args.ssh_host, remote_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if not select.select([process.stdout], [], [], 10)[0]:
            raise RuntimeError("ray manager did not become ready")
        first_line = process.stdout.readline().strip()
        if not first_line.startswith("READY "):
            raise RuntimeError("ray manager startup failed: " + first_line)
        source = (
            "import pico_worker, ray_worker\n"
            "w,c,n,t=pico_worker._create_watchdog()\n"
            "ray_worker.run_once(stall_after_tiles=0, stall_seconds=30, "
            "watchdog=w, reset_cause=c, reset_cause_name=n, "
            "watchdog_timeout_ms=t)\n"
        )
        board.exec_raw_no_follow(source)
    except Exception:
        if process is not None and process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)
        raise
    finally:
        try:
            board.close()
        except Exception:
            pass

    if process is None:
        raise RuntimeError("ray manager did not start")
    output, error = process.communicate(timeout=120)
    log_path = args.output_dir / (args.job_prefix + "-fault.log")
    log_path.write_text(first_line + "\n" + output + error, encoding="utf-8")
    if process.returncode:
        raise RuntimeError("ray fault cycle failed: " + error.strip())
    result_records = [
        json.loads(line.split(" ", 1)[1])
        for line in output.splitlines()
        if line.startswith("RESULT_DISPLAY ")
    ]
    if len(result_records) != 1:
        raise RuntimeError("fault cycle result is missing")
    record = result_records[0]
    timeouts = record.get("worker_timeouts", [])
    if (
        len(timeouts) != 1
        or timeouts[0].get("node_id") != args.target_node_id
        or timeouts[0].get("requeued_tiles") != 4
    ):
        raise RuntimeError("unexpected worker timeout: " + json.dumps(timeouts))
    if record.get("recovery_attempts") != 1:
        raise RuntimeError("recovery job was not run exactly once")
    if record.get("display_seconds", 0) < 2:
        raise RuntimeError("fault cycle did not preserve display time")
    print("RAY_FAULT_RECOVERY_PASS", json.dumps(record), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL", type(exc).__name__, str(exc), file=sys.stderr, flush=True)
        raise
