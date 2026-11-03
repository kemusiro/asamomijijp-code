#!/usr/bin/env python3
"""Bounded, read-only local and external diagnostics for the Pi 4 manager."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import urlopen


MAX_BODY = 262144


def command(argv, timeout=5):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError("command failed: " + argv[0] + " (exit %s)" % result.returncode)
    return result.stdout.strip()


def attempt(fn):
    started = time.monotonic()
    try:
        result = dict(ok=True, value=fn())
    except Exception as exc:
        # Include bounded diagnostics, never command lines/environment/credentials.
        result = dict(ok=False, error_type=type(exc).__name__, error=str(exc)[:300])
    result["elapsed_ms"] = round((time.monotonic()-started)*1000, 3)
    return result


def parallel(probes):
    with ThreadPoolExecutor(max_workers=len(probes)) as pool:
        pending = {name: pool.submit(attempt, fn) for name, fn in probes.items()}
        return {name: future.result() for name, future in pending.items()}


def text_file(path):
    return Path(path).read_text().strip()


def resources():
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree", "Dirty", "Writeback"):
            memory[key+"_kib"] = int(value.split()[0])
    processes, blocked = Counter(), []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            stat = (directory/"stat").read_text()
            name, rest = stat.split("(", 1)[1].rsplit(")", 1)
            state = rest.split()[0]
            processes[state] += 1
            if state == "D" and len(blocked) < 16:
                blocked.append(dict(pid=int(directory.name), comm=name[:64],
                                    wchan=text_file(directory/"wchan")))
        except (OSError, ValueError, IndexError):
            continue
    return dict(memory=memory, loadavg=text_file("/proc/loadavg"),
                pressure={name: text_file("/proc/pressure/"+name) for name in ("cpu","memory","io")},
                process_states=dict(processes), blocked_tasks=blocked,
                fd_allocated=text_file("/proc/sys/fs/file-nr"),
                diskstats=text_file("/proc/diskstats"), netdev=text_file("/proc/net/dev"))


def services():
    return command(["systemctl", "show", "ssh", "k3s", "-p", "Id", "-p", "ActiveState",
                    "-p", "MainPID", "-p", "NRestarts", "-p", "ExecMainStartTimestampMonotonic",
                    "-p", "TasksCurrent", "-p", "MemoryCurrent", "-p", "LimitNOFILE"])


def nodes(expected):
    data = json.loads(command(["k3s", "kubectl", "get", "nodes", "-o", "json", "--request-timeout=4s"]))
    rows = [dict(name=n["metadata"]["name"], ready=any(
        c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"]))
            for n in data["items"]]
    return dict(nodes=rows, count=len(rows), ready=sum(n["ready"] for n in rows), expected=expected)


def local_sample(config):
    return parallel(dict(
        resources=resources,
        services=services,
        ssh_listener=lambda: command(["ss", "-H", "-lnt", "sport", "=", ":22"]),
        sockets=lambda: command(["ss", "-s"]),
        livez=lambda: command(["k3s", "kubectl", "get", "--raw=/livez", "--request-timeout=4s"]),
        kubelet=lambda: command(["curl", "--fail", "--silent", "--show-error", "--max-time", "3",
                                 "http://127.0.0.1:10248/healthz"]),
        nodes=lambda: nodes(config["expected_nodes"]),
        power=lambda: command(["vcgencmd", "get_throttled"]),
        kernel_warnings=lambda: command(["journalctl", "-k", "-b", "--since=-2min", "-p", "warning",
                                         "-n", "20", "-o", "short-monotonic", "--no-pager", "--quiet"])[-8192:],
    ))


def ssh_banner(host, port, timeout):
    deadline = time.monotonic() + timeout
    with socket.create_connection((host, port), timeout=timeout) as sock:
        data = b""
        while b"\n" not in data:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("SSH banner deadline exceeded")
            sock.settimeout(remaining)
            part = sock.recv(256-len(data))
            if not part:
                raise RuntimeError("SSH closed before banner")
            data += part
            if len(data) >= 256:
                raise RuntimeError("SSH banner too long")
    line = data.splitlines()[0].decode("ascii")
    if not line.startswith("SSH-2.0-"):
        raise RuntimeError("invalid SSH banner")
    return line


def http_read(url, timeout, context=None, transport_only=False):
    try:
        response = urlopen(url, timeout=timeout, context=context)
    except HTTPError as exc:
        if transport_only and exc.code == 401:
            exc.close()
            # Auth failure establishes TLS/API reachability, NOT livez health.
            return dict(status=401, transport_ok=True, health=None)
        raise
    with response:
        body = response.read(MAX_BODY+1)
        if len(body) > MAX_BODY:
            raise ValueError("HTTP response too large")
        if transport_only:
            return dict(status=response.status, transport_ok=True, health=body.strip()==b"ok")
        return json.loads(body)


def vehicle(config):
    data = http_read(config["vehicle_url"].rstrip("/")+"/api/state", config["timeout"])
    return dict(running=data["running"], error=data.get("error"),
                experiment=data["comparison"]["id"], generation=data["generation"],
                evaluated=data["ranking"]["evaluated"], version=data["version"])


def pico(config):
    data = http_read(config["pico_url"].rstrip("/")+"/api/state", config["timeout"])
    return {k: data.get(k) for k in ("mode", "cycle", "job_id", "completed_tiles", "total_tiles",
                                    "updated_at", "expected_workers", "ready_node_ids")}


def observer_sample(config):
    return parallel(dict(
        ssh_banner=lambda: ssh_banner(config["host"], config["ssh_port"], config["timeout"]),
        api_transport=lambda: http_read(config["k3s_url"], config["timeout"],
                                       ssl.create_default_context(cafile=config["k3s_ca"]), True),
        vehicle=lambda: vehicle(config),
        pico=lambda: pico(config),
    ))


def failures(mode, probes):
    result = [name for name, probe in probes.items() if not probe["ok"]]
    if mode == "local":
        if probes["nodes"]["ok"]:
            n = probes["nodes"]["value"]
            if n["count"] != n["expected"] or n["ready"] != n["expected"]:
                result.append("node_readiness")
        for key in ("livez", "kubelet"):
            if probes[key]["ok"] and probes[key]["value"] != "ok":
                result.append(key + "_unhealthy")
        if probes["ssh_listener"]["ok"] and not probes["ssh_listener"]["value"]:
            result.append("ssh_not_listening")
        if probes["power"]["ok"] and probes["power"]["value"] != "throttled=0x0":
            result.append("power_warning")
        if probes["services"]["ok"] and probes["services"]["value"].count("ActiveState=active") != 2:
            result.append("service_inactive")
    else:
        if probes["api_transport"]["ok"] and probes["api_transport"]["value"]["health"] is False:
            result.append("api_unhealthy")
        if probes["vehicle"]["ok"] and probes["vehicle"]["value"]["error"]:
            result.append("vehicle_error")
        if probes["pico"]["ok"] and probes["pico"]["value"]["mode"] in (
                "waiting_for_manual_recovery", "display_error"):
            result.append("pico_error")
    return result


def sample(config, consecutive):
    probes = local_sample(config) if config["mode"] == "local" else observer_sample(config)
    bad = failures(config["mode"], probes)
    count = consecutive+1 if bad else 0
    return dict(schema_version=1, at=datetime.now(timezone.utc).isoformat(),
                monotonic_seconds=time.monotonic(), boot_id=text_file("/proc/sys/kernel/random/boot_id"),
                mode=config["mode"], probes=probes, failures=bad, consecutive_failures=count,
                status="degraded" if count >= 3 else "suspect" if count else "ok",
                recovery_action="none"), count


def validate_config(config):
    if config.get("mode") not in ("local", "observer"):
        raise ValueError("mode must be local or observer")
    config = {"interval":30, "timeout":4, "expected_nodes":13, "ssh_port":22, **config}
    for key in ("interval", "timeout"):
        if not isinstance(config[key], (int,float)) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError("positive finite " + key + " required")
    if config["interval"] < 10 or config["timeout"] > 10:
        raise ValueError("interval >= 10 and timeout <= 10 required")
    if config["mode"] == "observer":
        for key in ("host", "k3s_ca", "k3s_url", "vehicle_url", "pico_url"):
            if not config.get(key):
                raise ValueError("missing config: " + key)
        if not config["k3s_url"].startswith("https://"):
            raise ValueError("K3s URL must use verified HTTPS")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    try:
        config = validate_config(json.loads(args.config.read_text()))
        if not args.once and args.output_dir is None:
            parser.error("--output-dir is required for continuous monitoring")
        logger = logging.getLogger("management-diagnostics")
        logger.setLevel(logging.INFO)
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(args.output_dir/"samples.jsonl", maxBytes=2*1024*1024,
                                          backupCount=12, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        count = 0
        while True:
            start = time.monotonic()
            record, count = sample(config, count)
            line = json.dumps(record, ensure_ascii=False)
            if args.output_dir:
                logger.info(line)
                temporary = args.output_dir/"latest.json.tmp"
                temporary.write_text(line+"\n")
                temporary.replace(args.output_dir/"latest.json")
            if args.once:
                print(line)
                return 1 if record["failures"] else 0
            print(json.dumps({k:record[k] for k in ("at","mode","status","failures","consecutive_failures")}), flush=True)
            time.sleep(max(0, config["interval"]-(time.monotonic()-start)))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print("監視を継続できません: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
