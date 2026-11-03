#!/usr/bin/env python3
"""常駐Pico workerのwatchdog復旧をPi 5 managerから検証する。"""

import argparse
import glob
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


EXPECTED_CHECKSUM = "1a26b685"
EXPECTED_RECOVERY_CHECKSUM = "e590a9e7"
EXPECTED_WATCHDOG_MS = 8000


def remote_manager_source(
    args,
    job_id,
    manager_timeout=None,
    minimum_worker_count=None,
    recovery_probe=False,
    worker_count=16,
    manager_port=None,
):
    if manager_timeout is None:
        manager_timeout = args.manager_timeout
    if minimum_worker_count is None:
        minimum_worker_count = args.expected_device_count
    if manager_port is None:
        manager_port = args.manager_port
    network_dir = (
        args.remote_root.rstrip("/")
        + "/projects/raspberry-pi-pico-cluster/mandelbrot/network"
    )
    record_path = args.remote_root.rstrip("/") + "/" + job_id + "-trace.json"
    tile_size = 16
    return f'''import json, sys
sys.path.insert(0, {network_dir!r})
import manager
try:
    result = manager.run_tcp_server(
        manager.{"RECOVERY_JOB" if recovery_probe else "EXHIBITION_JOB"},
        {tile_size}, "0.0.0.0", {manager_port},
        {manager_timeout}, {job_id!r},
        ready_callback=lambda addr: print("READY", flush=True),
        request_window={1 if recovery_probe else 4}, worker_count={worker_count},
        worker_timeout=5,
        minimum_worker_count={minimum_worker_count},
        record_path={record_path!r})
    print(json.dumps(result), flush=True)
except Exception as exc:
    print("FAILURE_TYPE", type(exc).__name__, file=sys.stderr, flush=True)
    print("FAILURE_MESSAGE", str(exc), file=sys.stderr, flush=True)
    failures = getattr(exc, "worker_failures", None)
    if failures is not None:
        print("FAILURE_WORKERS", json.dumps(failures), file=sys.stderr, flush=True)
    raise
'''


def start_manager(
    args,
    job_id,
    manager_timeout=None,
    minimum_worker_count=None,
    recovery_probe=False,
    worker_count=16,
    manager_port=None,
):
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        args.ssh_host,
        "python3 -u -c "
        + shlex.quote(
            remote_manager_source(
                args,
                job_id,
                manager_timeout,
                minimum_worker_count,
                recovery_probe,
                worker_count,
                manager_port,
            )
        ),
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
            "manager did not become ready: " + first_line + output + error
        )
    return proc


def _manager_failure_details(error):
    failure_type = None
    worker_failures = []
    for line in error.splitlines():
        if line.startswith("FAILURE_TYPE "):
            failure_type = line.split(" ", 1)[1]
        elif line.startswith("FAILURE_WORKERS "):
            worker_failures = json.loads(line.split(" ", 1)[1])
    return failure_type, worker_failures


def finish_manager_failure(args, proc, job_id, manager_timeout=None):
    if manager_timeout is None:
        manager_timeout = args.manager_timeout
    output, error = proc.communicate(timeout=manager_timeout + 15)
    (args.output_dir / (job_id + "-manager.log")).write_text(
        output + error, encoding="utf-8"
    )
    if proc.returncode == 0:
        raise RuntimeError("manager unexpectedly completed for " + job_id)
    failure_type, worker_failures = _manager_failure_details(error)
    if failure_type != "AllWorkersUnavailable":
        raise RuntimeError(
            "manager did not report AllWorkersUnavailable: " + error.strip()
        )
    return {
        "job_id": job_id,
        "failure_type": failure_type,
        "worker_failures": worker_failures,
    }


def finish_manager(args, proc, job_id, manager_timeout=None):
    if manager_timeout is None:
        manager_timeout = args.manager_timeout
    output, error = proc.communicate(timeout=manager_timeout + 15)
    (args.output_dir / (job_id + "-manager.log")).write_text(
        output + error, encoding="utf-8"
    )
    if proc.returncode:
        raise RuntimeError("manager failed for %s: %s" % (job_id, error.strip()))
    records = [
        json.loads(line)
        for line in output.splitlines()
        if line.startswith("{")
    ]
    if len(records) != 1:
        raise RuntimeError("manager summary is missing for " + job_id)
    return records[0]


def validate_summary(
    summary,
    allow_timeout=False,
    allow_partial_startup=False,
    recovery_probe=False,
):
    expected_checksum = (
        EXPECTED_RECOVERY_CHECKSUM if recovery_probe else EXPECTED_CHECKSUM
    )
    if summary.get("checksum32") != expected_checksum:
        raise RuntimeError("checksum mismatch")
    if not summary.get("checksum_matches") or not summary.get("known_pixels_match"):
        raise RuntimeError("manager result validation failed")
    expected_tiles = 16 if recovery_probe else 320
    if summary.get("tiles_completed") != expected_tiles:
        raise RuntimeError("unexpected tile count")
    workers = summary.get("workers", [])
    started = summary.get("worker_count_started")
    if (
        type(started) is not int
        or not 1 <= started <= 16
        or len(workers) != started
    ):
        raise RuntimeError("unexpected started worker count")
    if not allow_partial_startup and started != 16:
        raise RuntimeError("16 workers did not start")
    for worker in workers:
        if not worker.get("watchdog_enabled"):
            raise RuntimeError("watchdog is disabled on " + worker["node_id"])
        if worker.get("watchdog_timeout_ms") != EXPECTED_WATCHDOG_MS:
            raise RuntimeError("unexpected watchdog timeout on " + worker["node_id"])
    timeouts = summary.get("worker_timeouts", [])
    if timeouts and not allow_timeout:
        raise RuntimeError("unexpected worker timeout: " + json.dumps(timeouts))
    expected_active = started - len(timeouts)
    if summary.get("worker_count_active_at_completion") != expected_active:
        raise RuntimeError("unexpected active worker count")
    expected_requeued = sum(item.get("requeued_tiles", -1) for item in timeouts)
    maximum_requeued = 1 if recovery_probe else 4
    if any(
        not 1 <= item.get("requeued_tiles", -1) <= maximum_requeued
        for item in timeouts
    ):
        raise RuntimeError("unexpected timeout requeue count")
    if summary.get("requeued_tiles") != expected_requeued:
        raise RuntimeError("unexpected requeued tile count")
    return timeouts


def run_job(
    args,
    suffix,
    allow_timeout=False,
    manager_timeout=None,
    minimum_worker_count=None,
    allow_partial_startup=False,
    recovery_probe=False,
    worker_count=16,
    manager_port=None,
):
    job_id = args.job_prefix + "-" + suffix
    proc = start_manager(
        args,
        job_id,
        manager_timeout,
        minimum_worker_count,
        recovery_probe,
        worker_count,
        manager_port,
    )
    summary = finish_manager(args, proc, job_id, manager_timeout)
    timeouts = validate_summary(
        summary,
        allow_timeout=allow_timeout,
        allow_partial_startup=allow_partial_startup,
        recovery_probe=recovery_probe,
    )
    with (args.output_dir / (args.job_prefix + "-summaries.jsonl")).open(
        "a", encoding="utf-8"
    ) as stream:
        stream.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(
        "PASS",
        job_id,
        "startup_ready_ms=%.3f" % summary["startup_ready_ms"],
        "e2e_ms=%.3f" % summary["e2e_ms"],
        "timeouts=%d" % len(timeouts),
        flush=True,
    )
    return summary


def run_repeat(args):
    for index in range(1, args.runs + 1):
        run_job(args, "repeat-%03d" % index)


def run_soak(args):
    timeout_events = []
    started = time.monotonic()
    for cycle in range(1, args.cycles + 1):
        cycle_started = time.monotonic()
        for job_number in (1, 2):
            summary = run_job(
                args,
                "soak-%03d-job-%d" % (cycle, job_number),
                allow_timeout=True,
            )
            for timeout in summary["worker_timeouts"]:
                timeout_events.append(
                    {
                        "cycle": cycle,
                        "job": job_number,
                        **timeout,
                    }
                )
            if summary["worker_timeouts"]:
                run_recovery(
                    args,
                    "soak-%03d-job-%d-auto-recovery" % (cycle, job_number),
                    [item["node_id"] for item in summary["worker_timeouts"]],
                )
        elapsed = time.monotonic() - cycle_started
        remaining = args.cycle_seconds - elapsed
        if remaining < args.minimum_result_display_seconds:
            raise RuntimeError(
                "cycle %d exceeded display budget: %.3f seconds remain"
                % (cycle, remaining)
            )
        status = {
            "cycle": cycle,
            "elapsed_seconds": round(elapsed, 3),
            "remaining_seconds": round(remaining, 3),
            "timeout_events": len(timeout_events),
        }
        with (args.output_dir / (args.job_prefix + "-cycles.jsonl")).open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(status) + "\n")
        print("CYCLE", json.dumps(status), flush=True)
        time.sleep(remaining)
    result = {
        "cycles": args.cycles,
        "jobs": args.cycles * 2,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timeout_events": timeout_events,
    }
    (args.output_dir / (args.job_prefix + "-result.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("SOAK_PASS", json.dumps(result, ensure_ascii=False), flush=True)


def run_fault(args):
    if not args.target_port or not args.target_node_id:
        raise RuntimeError("fault16 requires --target-port and --target-node-id")
    try:
        from mpremote.transport_serial import SerialTransport
    except ImportError as exc:
        raise RuntimeError("fault16 requires mpremote") from exc

    board = SerialTransport(args.target_port)
    proc = None
    try:
        board.enter_raw_repl(soft_reset=False)
        # The resident worker has already enabled the hardware watchdog.  Keep
        # it alive while raw REPL verifies the target and starts the manager;
        # otherwise it can reset before the injected session begins.
        board.exec("import machine; machine.WDT(timeout=8000).feed()")
        identity = board.exec(
            "import network_config; print(network_config.NODE_ID)"
        ).decode().strip()
        if identity != args.target_node_id:
            raise RuntimeError("unexpected node: " + identity)
        board.exec("import machine; machine.WDT(timeout=8000).feed()")
        job_id = args.job_prefix + "-fault"
        proc = start_manager(args, job_id)
        source = (
            "import network_config\n"
            "network_config.MANAGER_HOST=%r\n" % args.manager_host
            + "network_config.MANAGER_PORT=%d\n" % args.manager_port
            + "import pico_worker\n"
            + "w,c,n,t=pico_worker._create_watchdog()\n"
            + "pico_worker.run_once(stall_after_tiles=0, stall_seconds=30, "
            + "watchdog=w, reset_cause=c, reset_cause_name=n, "
            + "watchdog_timeout_ms=t)\n"
        )
        board.exec_raw_no_follow(source)
    except Exception:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.communicate(timeout=5)
        raise
    finally:
        try:
            board.close()
        except Exception:
            pass
    summary = finish_manager(args, proc, job_id)
    timeouts = validate_summary(summary, allow_timeout=True)
    if len(timeouts) != 1 or timeouts[0]["node_id"] != args.target_node_id:
        raise RuntimeError("target watchdog timeout was not observed")
    if summary["worker_count_active_at_completion"] != 15:
        raise RuntimeError("fault job did not complete with 15 workers")
    time.sleep(5)
    recovery = run_job(args, "fault-recovery")
    target = next(
        worker
        for worker in recovery["workers"]
        if worker["node_id"] == args.target_node_id
    )
    if target.get("reset_cause_name") != "WDT_RESET":
        raise RuntimeError("target did not report WDT_RESET")
    if recovery["startup_ready_ms"] >= args.cycle_seconds * 1000:
        raise RuntimeError("watchdog recovery exceeded the exhibition cycle")
    print(
        "FAULT_PASS",
        args.target_node_id,
        "timeout_ms=%.3f" % timeouts[0]["detected_after_ms"],
        "recovery_ready_ms=%.3f" % recovery["startup_ready_ms"],
        flush=True,
    )


def _append_jsonl(path, record):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_display_state(args, state):
    path = args.output_dir / (args.job_prefix + "-display-state.json")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _held_result(summary):
    return {
        "job_id": summary["job_id"],
        "checksum32": summary["checksum32"],
        "known_pixels_match": summary["known_pixels_match"],
    }


def _manual_recovery_actions():
    return [
        "PicoとUSB serial deviceが16台すべて列挙されていることを確認する",
        "Pico、USBハブ、給電系の発熱、異臭、給電不安定を確認する",
        "16台未満の場合はUSB resetを行わず、物理接続と給電を確認する",
        "16台が揃っている場合だけrecover16を1回実行する",
        "復旧確認後に新しいjob prefixで展示サイクルを再開する",
    ]


def run_one_worker_unavailable(args):
    if not args.target_port or not args.target_node_id:
        raise RuntimeError(
            "all-workers-recovery requires --target-port and --target-node-id"
        )
    try:
        from mpremote.transport_serial import SerialTransport
    except ImportError as exc:
        raise RuntimeError("all-workers-recovery requires mpremote") from exc

    job_id = args.job_prefix + "-all-workers-unavailable"
    board = SerialTransport(args.target_port)
    proc = None
    try:
        board.enter_raw_repl(soft_reset=False)
        board.exec("import machine; machine.WDT(timeout=8000).feed()")
        identity = board.exec(
            "import network_config; print(network_config.NODE_ID)"
        ).decode().strip()
        if identity != args.target_node_id:
            raise RuntimeError("unexpected node: " + identity)
        board.exec("import machine; machine.WDT(timeout=8000).feed()")
        proc = start_manager(
            args,
            job_id,
            minimum_worker_count=1,
            worker_count=1,
            manager_port=args.fault_manager_port,
        )
        source = (
            "import network_config\n"
            "network_config.MANAGER_HOST=%r\n" % args.manager_host
            + "network_config.MANAGER_PORT=%d\n" % args.fault_manager_port
            + "import pico_worker\n"
            + "w,c,n,t=pico_worker._create_watchdog()\n"
            + "pico_worker.run_once(stall_after_tiles=0, stall_seconds=30, "
            + "watchdog=w, reset_cause=c, reset_cause_name=n, "
            + "watchdog_timeout_ms=t)\n"
        )
        board.exec_raw_no_follow(source)
    except Exception:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.communicate(timeout=5)
        raise
    finally:
        try:
            board.close()
        except Exception:
            pass
    if proc is None:
        raise RuntimeError("fault manager did not start")
    failure = finish_manager_failure(args, proc, job_id)
    worker_failures = failure["worker_failures"]
    if (
        len(worker_failures) != 1
        or worker_failures[0].get("node_id") != args.target_node_id
        or not worker_failures[0].get("timed_out")
    ):
        raise RuntimeError(
            "unexpected all-worker failure: "
            + json.dumps(worker_failures, ensure_ascii=False)
        )
    time.sleep(args.post_fault_wait_seconds)
    return failure


def run_all_workers_recovery(
    args,
    normal_runner=None,
    failure_runner=None,
    recovery_runner=None,
):
    if normal_runner is None:
        normal_runner = lambda suffix: run_job(args, suffix)
    if failure_runner is None:
        failure_runner = lambda: run_one_worker_unavailable(args)
    if recovery_runner is None:
        recovery_runner = lambda suffix: run_job(
            args,
            suffix,
            recovery_probe=True,
        )

    incident_path = args.output_dir / (args.job_prefix + "-incidents.jsonl")
    if incident_path.exists():
        raise RuntimeError("incident log already exists; use a new job-prefix")

    previous = normal_runner("cycle-before-fault")
    held_result = _held_result(previous)
    _write_display_state(
        args,
        {
            "mode": "result",
            "held_result": held_result,
            "message": "展示結果を表示中です。",
        },
    )
    failure = failure_runner()
    incident_id = args.job_prefix + "-incident-01"
    recovery_job_id = args.job_prefix + "-recovery"
    incident = {
        "incident_id": incident_id,
        "source_job_id": failure["job_id"],
        "source_failure_type": failure["failure_type"],
        "source_worker_failures": failure["worker_failures"],
        "held_result": held_result,
        "recovery_attempts": 1,
        "recovery_job_id": recovery_job_id,
    }
    _write_display_state(
        args,
        {
            "mode": "recovering",
            "incident_id": incident_id,
            "held_result": held_result,
            "message": "全worker停止を検出したため、16台復旧確認を実行中です。",
        },
    )
    try:
        recovery = recovery_runner("recovery")
    except Exception as exc:
        incident.update(
            {
                "outcome": "manual_recovery_required",
                "recovery_error_type": type(exc).__name__,
                "recovery_error": str(exc),
                "manual_recovery_actions": _manual_recovery_actions(),
            }
        )
        _append_jsonl(incident_path, incident)
        _write_display_state(
            args,
            {
                "mode": "waiting_for_manual_recovery",
                "incident_id": incident_id,
                "held_result": held_result,
                "message": "自動復旧に失敗しました。機材を確認してください。",
                "manual_recovery_actions": incident["manual_recovery_actions"],
            },
        )
        print(
            "WAITING_SCREEN",
            json.dumps(incident, ensure_ascii=False, sort_keys=True),
            flush=True,
        )
        return incident

    incident.update(
        {
            "outcome": "recovered",
            "recovery_checksum32": recovery["checksum32"],
            "recovery_ready_ms": recovery["startup_ready_ms"],
            "recovery_e2e_ms": recovery["e2e_ms"],
        }
    )
    _append_jsonl(incident_path, incident)
    _write_display_state(
        args,
        {
            "mode": "holding_previous_result",
            "incident_id": incident_id,
            "held_result": held_result,
            "message": "16台の復旧を確認しました。次の展示サイクルで更新します。",
        },
    )
    following = normal_runner("cycle-after-recovery")
    _write_display_state(
        args,
        {
            "mode": "result",
            "incident_id": incident_id,
            "held_result": _held_result(following),
            "message": "復旧後の展示結果を表示中です。",
        },
    )
    result = {
        "incident": incident,
        "previous_job_id": previous["job_id"],
        "following_job_id": following["job_id"],
    }
    (args.output_dir / (args.job_prefix + "-result.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("ALL_WORKERS_RECOVERY_PASS", json.dumps(result), flush=True)
    return incident


def _reset_ports(args, ports, label, stagger_seconds):
    mpremote = str(Path(sys.executable).with_name("mpremote"))
    failures = []
    batch_size = min(args.reset_batch_size, len(ports))
    for start in range(0, len(ports), batch_size):
        batch = ports[start : start + batch_size]
        processes = [
            (
                port,
                subprocess.Popen(
                    [mpremote, "connect", port, "reset"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                ),
            )
            for port in batch
        ]
        for port, process in processes:
            try:
                _output, error = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                _output, error = process.communicate()
                error = (error + " reset command timed out").strip()
            print(
                "RESET",
                label,
                port,
                "exit=%d" % process.returncode,
                flush=True,
            )
            if process.returncode:
                failures.append(
                    {
                        "port": port,
                        "exit_code": process.returncode,
                        "error": error.strip(),
                    }
                )
        if start + batch_size < len(ports) and stagger_seconds:
            time.sleep(stagger_seconds)
    return failures


def _load_device_map(args, connected_ports):
    if args.device_map is None:
        return None
    device_map = json.loads(args.device_map.read_text(encoding="utf-8"))
    if not isinstance(device_map, dict) or len(device_map) != args.expected_device_count:
        raise RuntimeError("device map must contain every expected node")
    if not all(
        isinstance(node_id, str) and isinstance(port, str)
        for node_id, port in device_map.items()
    ):
        raise RuntimeError("device map node IDs and ports must be strings")
    if len(set(device_map.values())) != len(device_map):
        raise RuntimeError("device map contains duplicate ports")
    unknown_ports = sorted(set(device_map.values()) - set(connected_ports))
    if unknown_ports:
        raise RuntimeError("device map ports are not connected: " + json.dumps(unknown_ports))
    return device_map


def _run_recovery_verification(args, suffix, manager_timeout=None):
    if manager_timeout is None:
        manager_timeout = args.recovery_manager_timeout
    return run_job(
        args,
        suffix,
        allow_timeout=True,
        manager_timeout=manager_timeout,
        minimum_worker_count=args.recovery_minimum_workers,
        allow_partial_startup=True,
        recovery_probe=True,
    )


def _recover_incomplete_summary(
    args,
    summary,
    suffix,
    device_map,
    recovery_started_at,
):
    for attempt in range(1, args.recovery_attempts + 1):
        started_node_ids = set(summary["node_ids"])
        timeout_node_ids = {
            item["node_id"] for item in summary["worker_timeouts"]
        }
        if (
            len(started_node_ids) == args.expected_device_count
            and not timeout_node_ids
        ):
            return summary
        if device_map is None:
            raise RuntimeError(
                "incomplete recovery requires --device-map: "
                + json.dumps(
                    {
                        "started": sorted(started_node_ids),
                        "timed_out": sorted(timeout_node_ids),
                    }
                )
            )
        node_ids = sorted(
            (set(device_map) - started_node_ids) | timeout_node_ids
        )
        unknown_nodes = sorted(set(node_ids) - set(device_map))
        if unknown_nodes:
            raise RuntimeError(
                "nodes are missing from device map: " + json.dumps(unknown_nodes)
            )
        print(
            "RECOVERY_INCOMPLETE",
            json.dumps(
                {
                    "attempt": attempt,
                    "elapsed_seconds": round(
                        time.monotonic() - recovery_started_at,
                        3,
                    ),
                    "missing": sorted(set(device_map) - started_node_ids),
                    "timed_out": sorted(timeout_node_ids),
                }
            ),
            flush=True,
        )
        failures = _reset_ports(
            args,
            [device_map[node_id] for node_id in node_ids],
            "verification=%d" % attempt,
            0,
        )
        if failures:
            print(
                "RECOVERY_RESET_FAILURE",
                json.dumps(failures),
                flush=True,
            )
        time.sleep(args.recovery_wait_seconds)
        summary = _run_recovery_verification(
            args,
            "%s-verification-%02d" % (suffix, attempt),
        )
        if (
            len(set(summary["node_ids"])) == args.expected_device_count
            and not summary["worker_timeouts"]
        ):
            return summary
    missing_node_ids = sorted(set(device_map or {}) - set(summary["node_ids"]))
    timeout_node_ids = sorted(
        {item["node_id"] for item in summary["worker_timeouts"]}
    )
    raise RuntimeError(
        "recovery did not reach 16 healthy workers: "
        + json.dumps(
            {
                "missing": missing_node_ids,
                "timed_out": timeout_node_ids,
            }
        )
    )


def run_recovery(args, suffix="recovery", target_node_ids=None):
    recovery_started_at = time.monotonic()
    ports = sorted(glob.glob(args.port_glob))
    if len(ports) != args.expected_device_count:
        raise RuntimeError(
            "expected %d recovery devices, found %d: %s"
            % (args.expected_device_count, len(ports), json.dumps(ports))
        )
    errors = []
    device_map = _load_device_map(args, ports)
    target_node_ids = list(target_node_ids or args.recovery_node_id)
    if target_node_ids:
        if device_map is None:
            raise RuntimeError("targeted recovery requires --device-map")
        unknown_nodes = sorted(set(target_node_ids) - set(device_map))
        if unknown_nodes:
            raise RuntimeError("nodes are missing from device map: " + json.dumps(unknown_nodes))
        target_ports = [device_map[node_id] for node_id in sorted(set(target_node_ids))]
        failures = _reset_ports(args, target_ports, "target", 0)
        if failures:
            error = "target USB reset failed: " + json.dumps(failures)
        else:
            time.sleep(args.recovery_wait_seconds)
            try:
                summary = _run_recovery_verification(
                    args, suffix + "-target"
                )
                summary = _recover_incomplete_summary(
                    args,
                    summary,
                    suffix + "-target",
                    device_map,
                    recovery_started_at,
                )
                print(
                    "TARGET_RECOVERY_PASS",
                    json.dumps(sorted(set(target_node_ids))),
                    flush=True,
                )
                return summary
            except Exception as exc:
                error = "%s: %s" % (type(exc).__name__, exc)
        errors.append(
            {
                "attempt": "target",
                "elapsed_seconds": round(
                    time.monotonic() - recovery_started_at,
                    3,
                ),
                "error": error,
            }
        )
        print("RECOVERY_FALLBACK", json.dumps(errors[-1]), flush=True)
    for attempt in range(1, args.full_reset_attempts + 1):
        failures = _reset_ports(
            args,
            ports,
            "attempt=%d" % attempt,
            args.reset_stagger_seconds,
        )
        if failures:
            error = "USB reset failed: " + json.dumps(failures)
        else:
            time.sleep(args.recovery_wait_seconds)
            try:
                attempt_suffix = "%s-%02d" % (suffix, attempt)
                summary = _run_recovery_verification(
                    args,
                    attempt_suffix,
                    args.full_recovery_manager_timeout,
                )
                summary = _recover_incomplete_summary(
                    args,
                    summary,
                    attempt_suffix,
                    device_map,
                    recovery_started_at,
                )
                print("RECOVERY_PASS", "attempt=%d" % attempt, flush=True)
                return summary
            except Exception as exc:
                error = "%s: %s" % (type(exc).__name__, exc)
        errors.append(
            {
                "attempt": attempt,
                "elapsed_seconds": round(
                    time.monotonic() - recovery_started_at,
                    3,
                ),
                "error": error,
            }
        )
        print("RECOVERY_RETRY", json.dumps(errors[-1]), flush=True)
    raise RuntimeError("recovery attempts exhausted: " + json.dumps(errors))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=(
            "normal16",
            "repeat16",
            "fault16",
            "soak3h",
            "recover16",
            "all-workers-recovery",
        ),
    )
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--manager-host", required=True)
    parser.add_argument("--manager-port", type=int, default=8765)
    parser.add_argument("--fault-manager-port", type=int, default=18765)
    parser.add_argument("--manager-timeout", type=float, default=30)
    parser.add_argument("--recovery-manager-timeout", type=float, default=15)
    parser.add_argument(
        "--full-recovery-manager-timeout",
        type=float,
        default=15,
    )
    parser.add_argument("--recovery-minimum-workers", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--job-prefix", required=True)
    parser.add_argument("--target-port")
    parser.add_argument("--target-node-id")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--cycles", type=int, default=270)
    parser.add_argument("--cycle-seconds", type=float, default=40)
    parser.add_argument("--minimum-result-display-seconds", type=float, default=2)
    parser.add_argument("--port-glob", default="/dev/cu.usbmodem*")
    parser.add_argument("--device-map", type=Path)
    parser.add_argument("--recovery-node-id", action="append", default=[])
    parser.add_argument("--expected-device-count", type=int, default=16)
    parser.add_argument("--recovery-wait-seconds", type=float, default=0)
    parser.add_argument("--post-fault-wait-seconds", type=float, default=5)
    parser.add_argument("--recovery-attempts", type=int, default=3)
    parser.add_argument("--full-reset-attempts", type=int, default=1)
    parser.add_argument("--reset-stagger-seconds", type=float, default=0.25)
    parser.add_argument("--reset-batch-size", type=int, default=2)
    args = parser.parse_args()
    if (
        args.runs <= 0
        or args.cycles <= 0
        or args.expected_device_count <= 0
        or args.recovery_attempts <= 0
        or args.full_reset_attempts <= 0
        or args.reset_batch_size <= 0
        or not 1 <= args.recovery_minimum_workers <= args.expected_device_count
    ):
        parser.error("counts must be positive")
    if (
        args.manager_timeout <= 0
        or args.recovery_manager_timeout <= 0
        or args.full_recovery_manager_timeout <= 0
        or args.cycle_seconds <= 0
    ):
        parser.error("timeouts must be positive")
    if (
        args.recovery_wait_seconds < 0
        or args.post_fault_wait_seconds < 0
        or args.reset_stagger_seconds < 0
    ):
        parser.error("recovery delays must not be negative")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    return args


def main():
    args = parse_args()
    if args.phase == "normal16":
        run_job(args, "normal")
    elif args.phase == "repeat16":
        run_repeat(args)
    elif args.phase == "fault16":
        run_fault(args)
    elif args.phase == "soak3h":
        run_soak(args)
    elif args.phase == "all-workers-recovery":
        incident = run_all_workers_recovery(args)
        if incident["outcome"] != "recovered":
            raise RuntimeError("automatic recovery requires manual intervention")
    else:
        run_recovery(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL", type(exc).__name__, str(exc), file=sys.stderr, flush=True)
        raise
