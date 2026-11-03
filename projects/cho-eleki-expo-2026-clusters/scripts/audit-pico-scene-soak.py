#!/usr/bin/env python3
"""Read-only audit of a bounded worst/best/sphere exhibition log interval."""

import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
import zlib


def read_jsonl(path):
    # Reject truncated/invalid snapshots rather than silently skipping records.
    return [json.loads(line) for line in path.read_text().splitlines()]


def journal_times(text):
    result = {}
    for line in text.splitlines():
        if "RESULT_DISPLAY " in line:
            record = json.loads(line.split("RESULT_DISPLAY ", 1)[1])
            key = record.get("job_id")
            if key in result:
                raise ValueError("duplicate journal job: " + str(key))
            result[key] = (datetime.fromisoformat(line.split()[0]), record)
    return result


def check_trace(path, summary):
    trace = json.loads(path.read_text())
    spec = summary["jobSpec"]
    width, height, size = spec["width"], spec["height"], summary["tile_size"]
    tiles = [dict(tile_id=i, x0=x, y0=y, width=min(size, width-x),
                  height=min(size, height-y))
             for i, (y, x) in enumerate((y, x) for y in range(0, height, size)
                                        for x in range(0, width, size))]
    if (trace["job_id"] != summary["job_id"] or trace["job"] != spec
            or trace["format"] != "tile-progress-v2"
            or trace["image_encoding"] != "base64-rgb888-row-major"
            or trace["tile_mirroring"] != "none"
            or trace["summary"] != {k: v for k, v in summary.items()
                                    if k not in ("scene", "scene_type", "jobSpec")}
            or trace["tiles"] != tiles):
        raise ValueError("trace job/summary/grid mismatch")
    events = trace["events"]
    if (len(events) != len(tiles)
            or {e["tile_id"] for e in events} != set(range(len(tiles)))
            or Counter(e["node_id"] for e in events) != Counter(
                {w["node_id"]: w["tiles_completed"] for w in summary["workers"]})):
        raise ValueError("trace events incomplete or duplicated")
    pixels = base64.b64decode(trace["image_base64"], validate=True)
    if len(pixels) != width * height * 3:
        raise ValueError("trace RGB length mismatch")
    if "%08x" % zlib.crc32(pixels) != summary["checksum32"]:
        raise ValueError("trace image CRC mismatch")


def audit(cycles, summaries, journal, first, last, minimum_hours=3,
          artifact_dir=None):
    failures, warnings, rows = [], [], []
    by_job = defaultdict(list)
    for summary in summaries:
        by_job[summary["job_id"]].append(summary)
    selected = [c for c in cycles if first <= c["cycle"] <= last]
    if [c["cycle"] for c in selected] != list(range(first, last + 1)):
        failures.append("cycle numbers missing, duplicated or out of order")
    times = journal_times(journal)
    expected_nodes = {"pico-%02d" % n for n in range(1, 17)}
    previous_resets = None
    for cycle in selected:
        job = cycle.get("job_id", "unknown")
        try:
            if (cycle["outcome"] != "completed" or cycle["recovery_attempts"] != 0
                    or cycle["worker_timeouts"] or cycle["requeued_tiles"] != 0):
                raise ValueError("cycle required recovery or lost workers")
            found = by_job[job]
            if len(found) != 1:
                raise ValueError("missing or duplicate summary")
            s = found[0]
            at, logged = times[job]
            if logged != cycle:
                raise ValueError("journal/cycle mismatch")
            expected_role = ("worst", "best", "sphere")[(cycle["cycle"] - 1) % 3]
            scene = s["scene"]
            role = scene.get("role") if scene["type"] == "vehicle" else "sphere"
            if role != expected_role or scene != cycle["scene"]:
                raise ValueError("scene order/metadata mismatch")
            spec = s["jobSpec"]
            width, height = (480, 270) if role == "sphere" else (320, 180)
            size = 16 if role == "sphere" else 8
            count = ((width + size - 1)//size) * ((height + size - 1)//size)
            if (spec["width"] != width or spec["height"] != height
                    or s["tile_size"] != size or s["tiles_completed"] != count
                    or s["recording_events"] != count
                    or s["payload_bytes_received"] != width * height * 3
                    or s["checksum32"] != cycle["checksum32"]):
                raise ValueError("image/tile completeness mismatch")
            workers = s["workers"]
            if (len(workers) != 16 or {w["node_id"] for w in workers} != expected_nodes
                    or set(s["node_ids"]) != expected_nodes
                    or s["worker_count_started"] != 16
                    or s["worker_count_active_at_completion"] != 16
                    or sum(w["tiles_completed"] for w in workers) != count):
                raise ValueError("16-worker participation mismatch")
            if (s["worker_timeouts"] or s["startup_failures"]
                    or s["startup_failure_count"] or s["requeued_tiles"]
                    or s["ignored_tile_results"]):
                raise ValueError("summary reports communication failure")
            for w in workers:
                if (w["failure"] or w["disconnected"] or w["timed_out"]
                        or w["requeued_tiles"] or w["ignored_tile_results"]
                        or w["tiles_completed"] <= 0
                        or not w["watchdog_enabled"] or w["watchdog_timeout_ms"] != 8000
                        or not isinstance(w["worker_mem_free_min_sampled"], int)
                        or w["worker_mem_free_min_sampled"] <= 0):
                    raise ValueError("worker failure or missing heap/watchdog evidence")
            resets = {w["node_id"]: w["reset_cause_name"] for w in workers}
            if previous_resets is not None and resets != previous_resets:
                raise ValueError("worker reset cause changed within interval")
            previous_resets = resets
            if role == "sphere":
                if (s["checksum32"] != "a70b3024" or s["checksum_matches"] is not True
                        or s["known_pixels_match"] is not True):
                    raise ValueError("sphere reference mismatch")
            else:
                source = scene["source"]
                if role == "worst" and source["distanceM"] < 0.05:
                    raise ValueError("worst includes displayed zero distance")
                if not scene["modelId"] or not source["carId"]:
                    raise ValueError("vehicle provenance missing")
                if scene.get("sourceError"):
                    warnings.append(dict(cycle=cycle["cycle"], source_error=scene["sourceError"]))
            if artifact_dir is not None:
                check_trace(artifact_dir / (job + "-trace.json"), s)
            rows.append(dict(cycle=cycle["cycle"], job_id=job, completed_at=at.isoformat(),
                             role=role, checksum32=s["checksum32"], tiles=count,
                             e2e_ms=s["e2e_ms"], model_id=scene.get("modelId"),
                             heap_min_by_node={w["node_id"]: w["worker_mem_free_min_sampled"]
                                               for w in workers}))
        except (KeyError, ValueError, TypeError, OSError) as exc:
            failures.append(job + ": " + str(exc))
    elapsed = ((datetime.fromisoformat(rows[-1]["completed_at"])
                - datetime.fromisoformat(rows[0]["completed_at"])).total_seconds()
               if len(rows) >= 2 else 0)
    if elapsed < minimum_hours * 3600:
        failures.append("completion-to-completion interval shorter than required hours")
    roles = Counter(row["role"] for row in rows)
    if not all(roles[r] for r in ("worst", "best", "sphere")):
        failures.append("all three scene roles required")
    models = {row["model_id"] for row in rows if row["model_id"]}
    if len(models) < 2:
        failures.append("multiple distinct vehicle models required")
    metrics = {}
    for role in roles:
        values = [r["e2e_ms"] for r in rows if r["role"] == role]
        heaps = [v for r in rows if r["role"] == role for v in r["heap_min_by_node"].values()]
        metrics[role] = dict(count=roles[role], e2e_ms_min=min(values),
                             e2e_ms_median=statistics.median(values), e2e_ms_max=max(values),
                             heap_min_sampled_bytes=min(heaps))
    return dict(schema_version=1, passed=not failures, first_cycle=first, last_cycle=last,
                completed_interval_seconds=elapsed, minimum_hours=minimum_hours,
                metrics=metrics, unique_vehicle_models=len(models), warnings=warnings,
                failures=failures, traces_checked=artifact_dir is not None, cycles=rows,
                limits=["sampled minimum heap is not post-GC free heap or a leak measurement",
                        "unchanged reset cause cannot rule out a same-cause reboot",
                        "vehicle CRC checks stored RGB integrity, not an independent render reference"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=Path, required=True)
    parser.add_argument("--summaries", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--first-cycle", type=int, required=True)
    parser.add_argument("--last-cycle", type=int, required=True)
    parser.add_argument("--minimum-hours", type=float, default=3)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.first_cycle < 1 or args.last_cycle < args.first_cycle
            or not 0 < args.minimum_hours < float("inf")):
        parser.error("positive cycle range and finite minimum hours required")
    inputs = (args.cycles, args.summaries, args.journal)
    if args.output.resolve() in [p.resolve() for p in inputs]:
        parser.error("output must differ from input logs")
    try:
        report = audit(read_jsonl(args.cycles), read_jsonl(args.summaries),
                       args.journal.read_text(), args.first_cycle, args.last_cycle,
                       args.minimum_hours, args.artifact_dir)
        report["input_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in inputs}
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("NG: ログを検査できません: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in report.items() if k != "cycles"}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
