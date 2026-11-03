#!/usr/bin/env python3
"""Independently audit management/traffic/Pico/iSCSI soak snapshots."""

import argparse
from datetime import datetime
import hashlib
import json
import math
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def value(row, role, name):
    require(row[role]["ok"] is True, role + " SSH/probe failed")
    probe = row[role]["value"][name]
    require(probe["ok"] is True, role + "/" + name + " failed")
    return probe["value"]


def audit(rows, minimum_seconds=10800, maximum_gap=90):
    failures, observations = [], []
    identities, boots, previous_monitor = {}, {}, {}
    traffic_uids = None
    previous_elapsed = None
    for index, row in enumerate(rows):
        obs = dict(index=index, at=row.get("at"), elapsed_seconds=row.get("elapsed_seconds"))
        def reject(reason):
            failures.append(dict(index=index, reason=reason))
        try:
            elapsed = row["elapsed_seconds"]
            require(isinstance(elapsed, (int, float)) and math.isfinite(elapsed), "invalid elapsed time")
            if previous_elapsed is None:
                require(0 <= elapsed <= maximum_gap, "invalid first sample time")
            else:
                require(0 < elapsed-previous_elapsed <= maximum_gap, "sampling gap/duplicate/out-of-order")
            previous_elapsed = elapsed
            require(not row["failures"], "sampler reported failure: " + str(row["failures"]))
        except (KeyError, ValueError, TypeError) as exc:
            reject(str(exc))
        for role in ("local", "pico"):
            try:
                monitor = value(row, role, "monitor")
                require(monitor["status"] == "ok" and not monitor["failures"], role + " monitor unhealthy")
                require(0 <= monitor["age_seconds"] < 75, role + " monitor stale")
                require(all(p["ok"] for p in monitor["probes"].values()), role + " inner probe failed")
                if role in boots:
                    require(monitor["boot_id"] == boots[role], role + " boot changed")
                    require(monitor["monotonic_seconds"] > previous_monitor[role], role + " monitor did not advance")
                boots[role] = monitor["boot_id"]
                previous_monitor[role] = monitor["monotonic_seconds"]
                units = value(row, role, "units")
                current = {u["Id"]: u for u in units}
                expected = {"ssh.service", "k3s.service"} if role == "local" else {
                    "pico-raytracing-runner.service", "pico-raytracing-display.service"}
                require(len(units) == 2 and set(current) == expected, role + " wrong units")
                require(all(u["ActiveState"] == "active" and int(u["MainPID"]) > 0 for u in units), role + " inactive unit")
                if role in identities:
                    require(current == identities[role], role + " service PID/start/restart count changed")
                identities[role] = current
                if role == "local":
                    p = monitor["probes"]
                    nodes = p["nodes"]["value"]
                    require(nodes["count"] == nodes["ready"] == nodes["expected"] == 13, "nodes not 13/13")
                    require(p["livez"]["value"] == p["kubelet"]["value"] == "ok", "livez/kubelet unhealthy")
                    require(p["power"]["value"] == "throttled=0x0", "power warning")
                    obs["available_kib"] = p["resources"]["value"]["memory"]["MemAvailable_kib"]
            except (KeyError, ValueError, TypeError) as exc:
                reject(role + ": " + str(exc))
        try:
            t = value(row, "local", "traffic")
            e = t["exhibition"]
            require(t["ready"] == t["expected"] == 12 and not t["errors"], "traffic workers/errors")
            require(e["status"] == "running" and not e["error"], "traffic exhibition unhealthy")
            age = (timestamp(row["at"])-timestamp(e["updatedAt"])).total_seconds()
            require(-5 <= age <= 90, "traffic exhibition stale")
            pods = value(row, "local", "workloads")
            require(len(pods) == 13 and all(p["phase"] == "Running" and p["ready"] and p["restarts"] == 0 for p in pods), "traffic pods unhealthy")
            uids = {p["uid"] for p in pods}
            require(len(uids) == 13, "duplicate pod UID")
            if traffic_uids is not None:
                require(uids == traffic_uids, "traffic pods replaced")
            traffic_uids = uids
            v = value(row, "local", "vehicle")
            require(v["running"] and not v["error"], "vehicle unhealthy")
            obs.update(traffic_cycle=e["cycle"], traffic_phase=e["phase"],
                       vehicle_experiment=v["experiment"], vehicle_evaluated=v["evaluated"])
        except (KeyError, ValueError, TypeError) as exc:
            reject(str(exc))
        try:
            p = value(row, "pico", "pico")
            require(p["mode"] in ("waiting_for_workers", "rendering", "result"), "Pico error/recovery mode")
            age = (timestamp(row["at"])-timestamp(p["updated_at"])).total_seconds()
            require(-5 <= age <= 90, "Pico progress stale")
            require(p["expected_workers"] == 16, "unexpected Pico worker count")
            obs["pico_cycle"] = p["cycle"]
        except (KeyError, ValueError, TypeError) as exc:
            reject(str(exc))
        try:
            require(value(row, "storage", "sessions") == 12, "iSCSI sessions not 12")
        except (KeyError, ValueError, TypeError) as exc:
            reject(str(exc))
        observations.append(obs)
    span = rows[-1]["elapsed_seconds"]-rows[0]["elapsed_seconds"] if rows else 0
    if span < minimum_seconds:
        failures.append(dict(reason="shorter than required duration"))
    if len(rows) < math.ceil(minimum_seconds/maximum_gap)+1:
        failures.append(dict(reason="insufficient samples"))
    def advance(key):
        values = [r[key] for r in observations if key in r]
        if not values or any(b < a for a,b in zip(values, values[1:])) or values[-1] <= values[0]:
            failures.append(dict(reason=key + " did not advance monotonically"))
            return 0
        return values[-1]-values[0]
    traffic = advance("traffic_cycle")
    pico = advance("pico_cycle")
    vehicle_advance = 0
    for a,b in zip(observations, observations[1:]):
        if all(k in a and k in b for k in ("vehicle_experiment", "vehicle_evaluated")) and a["vehicle_experiment"] == b["vehicle_experiment"]:
            delta = b["vehicle_evaluated"]-a["vehicle_evaluated"]
            if delta < 0:
                failures.append(dict(index=b["index"], reason="vehicle count regressed in same experiment"))
            vehicle_advance += max(0, delta)
    if vehicle_advance <= 0:
        failures.append(dict(reason="vehicle did not advance"))
    heaps = [r["available_kib"] for r in observations if "available_kib" in r]
    gaps = [b["elapsed_seconds"]-a["elapsed_seconds"] for a,b in zip(rows,rows[1:])]

    return dict(schema_version=1, passed=not failures, sample_count=len(rows), duration_seconds=span,
                required_seconds=minimum_seconds, allowed_maximum_gap_seconds=maximum_gap,
                observed_maximum_gap_seconds=max(gaps) if gaps else None,
                first_at=rows[0]["at"] if rows else None, last_at=rows[-1]["at"] if rows else None,
                traffic_cycle_advance=traffic, pico_cycle_advance=pico,
                vehicle_evaluated_advance=vehicle_advance,
                minimum_available_kib=min(heaps) if heaps else None,
                boot_ids=boots, units=identities, failures=failures, observations=observations,
                limits=["Pico job completion/CRC/recovery must also be audited from its full cycle logs",
                        "a clean soak cannot identify or rule out the original unreproduced failure"])


def monitor_records(directory):
    merged = {}
    for path in directory.glob("samples.jsonl*"):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            key = (record["boot_id"], record["monotonic_seconds"])
            if key in merged and merged[key] != record:
                raise ValueError("conflicting duplicate monitor record")
            merged[key] = record
    return sorted(merged.values(), key=lambda row: timestamp(row["at"]))


def audit_monitor(records, first_at, last_at, mode):
    start, end = timestamp(first_at), timestamp(last_at)
    selected = [r for r in records if start <= timestamp(r["at"]) <= end]
    failures = []
    if not selected:
        return dict(passed=False, sample_count=0, failures=["no monitor records in test interval"])
    if (timestamp(selected[0]["at"])-start).total_seconds() > 45 or (end-timestamp(selected[-1]["at"])).total_seconds() > 45:
        failures.append("monitor coverage gap at interval boundary")
    boot = selected[0]["boot_id"]
    previous = None
    maximum_gap = 0
    for index, record in enumerate(selected):
        if record["mode"] != mode or record["boot_id"] != boot:
            failures.append("monitor mode/boot changed at " + str(index))
        if record["status"] != "ok" or record["failures"] or not all(p["ok"] for p in record["probes"].values()):
            failures.append("monitor reported abnormal sample " + str(index))
        if previous is not None:
            gap = record["monotonic_seconds"]-previous
            maximum_gap = max(maximum_gap, gap)
            if not 0 < gap <= 45:
                failures.append("monitor gap/order violation at " + str(index))
        previous = record["monotonic_seconds"]
    return dict(passed=not failures, sample_count=len(selected), boot_id=boot,
                observed_maximum_gap_seconds=maximum_gap, failures=failures)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("samples", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--local-monitor-dir", type=Path)
    p.add_argument("--pico-monitor-dir", type=Path)
    a = p.parse_args()
    if a.samples.resolve() == a.output.resolve():
        p.error("output must differ from input")
    try:
        rows = [json.loads(line) for line in a.samples.read_text().splitlines()]
        report = audit(rows)
        report["input_sha256"] = hashlib.sha256(a.samples.read_bytes()).hexdigest()
        report["full_monitor_logs_checked"] = bool(a.local_monitor_dir and a.pico_monitor_dir)
        if bool(a.local_monitor_dir) != bool(a.pico_monitor_dir):
            raise ValueError("both monitor directories are required together")
        if report["full_monitor_logs_checked"]:
            report["monitor_logs"] = {}
            for mode, directory in (("local", a.local_monitor_dir), ("observer", a.pico_monitor_dir)):
                detail = audit_monitor(monitor_records(directory), report["first_at"], report["last_at"], mode)
                detail["input_sha256"] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in directory.glob("samples.jsonl*")}
                report["monitor_logs"][mode] = detail
                if not detail["passed"]:
                    report["passed"] = False
                    report["failures"].append(dict(reason=mode + " full monitor logs failed"))
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("監査できません。確定したJSONLと出力先を確認してください: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({k:v for k,v in report.items() if k != "observations"}, ensure_ascii=False))
    return 0 if report["passed"] else 1



if __name__ == "__main__":
    raise SystemExit(main())
