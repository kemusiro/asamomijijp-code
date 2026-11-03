#!/usr/bin/env python3
"""USBハブの電源再投入後に16台のWi-Fi worker復旧を反復検証する。"""

import argparse
from datetime import datetime, timezone
import glob
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


EXPECTED_CHECKSUM = "4e25d3ba"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def discover_devices(port_glob):
    return sorted(glob.glob(port_glob))


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def remote_manager_source(args, cycle, job_id):
    ray_dir = (
        args.remote_root.rstrip("/")
        + "/projects/raspberry-pi-pico-cluster/raytracing/network"
    )
    remote_base = "/tmp/%s-cycle-%02d" % (args.job_prefix, cycle)
    return f'''import json, sys
sys.path.insert(0, {ray_dir!r})
import ray_manager
try:
    result = ray_manager.cluster_manager.run_tcp_server(
        ray_manager.RECOVERY_JOB,
        16,
        "0.0.0.0",
        {args.manager_port},
        {args.cycle_timeout_seconds},
        {job_id!r},
        ready_callback=lambda addr: print("READY", flush=True),
        request_window=1,
        worker_count={args.expected},
        worker_timeout=5,
        record_path={remote_base + '-trace.json'!r},
        workload=ray_manager.RayTracingWorkload({remote_base + '.png'!r}),
    )
    print(json.dumps({{"type": "summary", "data": result}}), flush=True)
except Exception as exc:
    print("FAILURE_TYPE", type(exc).__name__, file=sys.stderr, flush=True)
    print("FAILURE_MESSAGE", str(exc), file=sys.stderr, flush=True)
    raise
'''


def start_manager(args, cycle):
    job_id = "%s-cycle-%02d-recovery" % (args.job_prefix, cycle)
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        args.ssh_host,
        "python3 -u -c "
        + shlex.quote(remote_manager_source(args, cycle, job_id)),
    ]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first_line = proc.stdout.readline().strip()
    if first_line != "READY":
        output, error = proc.communicate(timeout=5)
        raise RuntimeError(
            "managerが待受を開始できません: " + first_line + output + error
        )
    return proc, job_id


def finish_manager(proc, timeout):
    output, error = proc.communicate(timeout=timeout)
    if proc.returncode:
        raise RuntimeError("manager失敗: " + error.strip())
    records = []
    for line in output.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "summary":
            records.append(record["data"])
    if len(records) != 1:
        raise RuntimeError("manager summaryを1件取得できません")
    return records[0], output, error


def stop_manager(proc):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()


def validate_recovery_summary(
    summary,
    expected,
    deadline,
    power_on_detected_after_manager_seconds=0,
):
    expected_nodes = ["pico-%02d" % number for number in range(1, expected + 1)]
    errors = []
    if summary.get("checksum32") != EXPECTED_CHECKSUM:
        errors.append("CRC不一致")
    if not summary.get("checksum_matches"):
        errors.append("checksum検査失敗")
    if not summary.get("known_pixels_match"):
        errors.append("既知画素検査失敗")
    if summary.get("worker_count_started") != expected:
        errors.append("worker開始数が%dではありません" % expected)
    if sorted(summary.get("node_ids", [])) != expected_nodes:
        errors.append("node ID集合が不正です")
    if summary.get("worker_count_active_at_completion") != expected:
        errors.append("完了時worker数が%dではありません" % expected)
    if summary.get("worker_timeouts"):
        errors.append("worker timeoutがあります")
    if summary.get("requeued_tiles") != 0:
        errors.append("tile再割り当てがあります")
    manager_startup_seconds = summary.get("startup_ready_ms", float("inf")) / 1000
    startup_seconds = max(
        0,
        manager_startup_seconds - power_on_detected_after_manager_seconds,
    )
    if startup_seconds > deadline:
        errors.append("worker復旧が%.3f秒で期限超過" % startup_seconds)
    if errors:
        raise RuntimeError("; ".join(errors))
    return startup_seconds


def ping_fixed_ips(args):
    source = '''import json, subprocess
result = {}
for host in range(%d, %d):
    address = %r + str(host)
    proc = subprocess.run(
        ["ping", "-c", "1", "-W", %r, address],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    result[address] = proc.returncode == 0
print(json.dumps(result, sort_keys=True))
''' % (
        args.first_ip_host,
        args.first_ip_host + args.expected,
        args.ip_prefix,
        str(args.ping_timeout_seconds),
    )
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            args.ssh_host,
            "python3 -c " + shlex.quote(source),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=args.expected * args.ping_timeout_seconds + 10,
    )
    result = json.loads(completed.stdout.strip())
    failed = sorted(address for address, ok in result.items() if not ok)
    if failed:
        raise RuntimeError("固定IP ping失敗: " + ", ".join(failed))
    return result


def changed_event(log_path, cycle, started, phase, devices):
    record = {
        "timestamp": utc_now(),
        "cycle": cycle,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "phase": phase,
        "usb_count": len(devices),
        "usb_devices": devices,
    }
    append_jsonl(log_path, record)
    print(
        "cycle %02d %s: USB %d台 (%.3f秒)"
        % (cycle, phase, len(devices), record["elapsed_seconds"]),
        flush=True,
    )


def run_cycle(args, cycle, baseline, log_path):
    started = time.monotonic()
    deadline = started + args.cycle_timeout_seconds
    previous = baseline
    zero_since = None
    print(
        "cycle %02d/%02d: USBハブの電源をOFFにしてください"
        % (cycle, args.cycles),
        flush=True,
    )
    while time.monotonic() < deadline:
        devices = discover_devices(args.port_glob)
        if devices != previous:
            changed_event(log_path, cycle, started, "wait_for_off", devices)
            previous = devices
        if not devices:
            zero_since = zero_since or time.monotonic()
            if time.monotonic() - zero_since >= args.off_min_seconds:
                break
        else:
            zero_since = None
        time.sleep(args.interval)
    else:
        raise RuntimeError("cycle %02d: 電源OFF待ちが期限切れ" % cycle)

    append_jsonl(
        log_path,
        {
            "timestamp": utc_now(),
            "cycle": cycle,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "phase": "off_confirmed",
            "usb_count": 0,
        },
    )
    print(
        "cycle %02d: 0台を%.1f秒維持。manager待受を開始します"
        % (cycle, args.off_min_seconds),
        flush=True,
    )

    proc = None
    try:
        proc, job_id = start_manager(args, cycle)
        manager_ready = time.monotonic()
        append_jsonl(
            log_path,
            {
                "timestamp": utc_now(),
                "cycle": cycle,
                "elapsed_seconds": round(manager_ready - started, 3),
                "phase": "manager_ready",
                "job_id": job_id,
            },
        )
        print(
            "cycle %02d: USBハブの電源をONにしてください（復旧期限%.0f秒）"
            % (cycle, args.recovery_deadline_seconds),
            flush=True,
        )

        power_on_detected = None
        usb_stable_since = None
        previous = []
        summary = None
        manager_output = ""
        manager_error = ""
        while time.monotonic() < deadline:
            now = time.monotonic()
            devices = discover_devices(args.port_glob)
            if devices != previous:
                changed_event(log_path, cycle, started, "wait_for_recovery", devices)
                previous = devices
            if devices and power_on_detected is None:
                power_on_detected = now
                append_jsonl(
                    log_path,
                    {
                        "timestamp": utc_now(),
                        "cycle": cycle,
                        "elapsed_seconds": round(now - started, 3),
                        "phase": "power_on_detected",
                        "usb_count": len(devices),
                    },
                )
            if (
                power_on_detected is not None
                and now - power_on_detected
                > args.recovery_deadline_seconds + 10
            ):
                break
            if devices == baseline:
                usb_stable_since = usb_stable_since or now
            else:
                usb_stable_since = None
            if proc.poll() is not None:
                summary, manager_output, manager_error = finish_manager(proc, 1)
                break
            time.sleep(args.interval)
        if summary is None:
            raise RuntimeError("cycle %02d: worker復旧が期限切れ" % cycle)

        if power_on_detected is None:
            raise RuntimeError("cycle %02d: USB再給電を検出できません" % cycle)
        power_on_delay = power_on_detected - manager_ready
        startup_seconds = validate_recovery_summary(
            summary,
            args.expected,
            args.recovery_deadline_seconds,
            power_on_delay,
        )
        while (
            usb_stable_since is None
            or time.monotonic() - usb_stable_since < args.stable_seconds
        ):
            if time.monotonic() > deadline:
                raise RuntimeError("cycle %02d: USB安定確認が期限切れ" % cycle)
            devices = discover_devices(args.port_glob)
            if devices != baseline:
                raise RuntimeError("cycle %02d: 復旧後にUSB device集合が変化" % cycle)
            usb_stable_since = usb_stable_since or time.monotonic()
            time.sleep(args.interval)

        ping_result = ping_fixed_ips(args)
        result = {
            "timestamp": utc_now(),
            "cycle": cycle,
            "phase": "passed",
            "job_id": job_id,
            "manager_ready_to_workers_seconds": round(
                summary["startup_ready_ms"] / 1000, 3
            ),
            "power_on_to_workers_seconds": round(startup_seconds, 3),
            "power_on_detected_after_manager_seconds": round(power_on_delay, 3),
            "usb_recovered_after_manager_seconds": round(
                usb_stable_since - manager_ready, 3
            ),
            "usb_stable_seconds": args.stable_seconds,
            "usb_count": len(baseline),
            "fixed_ip_ping": ping_result,
            "summary": summary,
            "manager_stdout": manager_output,
            "manager_stderr": manager_error,
        }
        append_jsonl(log_path, result)
        print(
            "cycle %02d OK: 16/16 worker %.3f秒、CRC %s、固定IP 16/16、USB安定"
            % (cycle, startup_seconds, summary["checksum32"]),
            flush=True,
        )
        return result
    finally:
        stop_manager(proc)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--job-prefix", required=True)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--expected", type=int, default=16)
    parser.add_argument("--port-glob", default="/dev/cu.usbmodem*")
    parser.add_argument("--manager-port", type=int, default=8765)
    parser.add_argument("--recovery-deadline-seconds", type=float, default=60)
    parser.add_argument("--off-min-seconds", type=float, default=5)
    parser.add_argument("--stable-seconds", type=float, default=10)
    parser.add_argument("--cycle-timeout-seconds", type=float, default=300)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--ip-prefix", default="192.168.2.")
    parser.add_argument("--first-ip-host", type=int, default=41)
    parser.add_argument("--ping-timeout-seconds", type=int, default=1)
    args = parser.parse_args()
    if args.cycles <= 0 or args.expected <= 0:
        parser.error("cyclesとexpectedは1以上にしてください")
    if not 1 <= args.manager_port <= 65535:
        parser.error("manager-portが範囲外です")
    for name in (
        "recovery_deadline_seconds",
        "off_min_seconds",
        "stable_seconds",
        "cycle_timeout_seconds",
        "interval",
        "ping_timeout_seconds",
    ):
        if getattr(args, name) <= 0:
            parser.error("時間指定は0より大きくしてください")
    return args


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.output_dir / (args.job_prefix + "-power-cycles.jsonl")
    if log_path.exists():
        raise RuntimeError("出力済みです。新しいjob-prefixを指定してください")
    baseline = discover_devices(args.port_glob)
    if len(baseline) != args.expected:
        raise RuntimeError(
            "開始時のUSB serial deviceは%d/%d台です"
            % (len(baseline), args.expected)
        )
    append_jsonl(
        log_path,
        {
            "timestamp": utc_now(),
            "phase": "baseline",
            "usb_count": len(baseline),
            "usb_devices": baseline,
            "cycles": args.cycles,
            "recovery_deadline_seconds": args.recovery_deadline_seconds,
        },
    )
    results = []
    for cycle in range(1, args.cycles + 1):
        try:
            results.append(run_cycle(args, cycle, baseline, log_path))
        except Exception as exc:
            append_jsonl(
                log_path,
                {
                    "timestamp": utc_now(),
                    "cycle": cycle,
                    "phase": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise
    summary_path = args.output_dir / (args.job_prefix + "-summary.json")
    summary_path.write_text(
        json.dumps(
            {
                "timestamp": utc_now(),
                "result": "passed",
                "cycles": len(results),
                "permanent_missing_nodes": 0,
                "maximum_power_on_to_workers_seconds": max(
                    result["power_on_to_workers_seconds"] for result in results
                ),
                "log_path": str(log_path),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print("反復試験完了: " + str(summary_path), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("NG:", type(exc).__name__, str(exc), file=sys.stderr, flush=True)
        raise
