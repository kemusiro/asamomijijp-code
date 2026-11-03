#!/usr/bin/env python3
"""Run the 16-node ray-tracing exhibition on a fixed display cycle."""

import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
MANDELBROT_NETWORK = (
    REPO_ROOT / "projects/raspberry-pi-pico-cluster/mandelbrot/network"
)
RAYTRACING_NETWORK = (
    REPO_ROOT / "projects/raspberry-pi-pico-cluster/raytracing/network"
)
for directory in (MANDELBROT_NETWORK, RAYTRACING_NETWORK):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import manager  # noqa: E402
import ray_manager  # noqa: E402


EXPECTED_WATCHDOG_MS = 8000


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _write_json(path, record):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_jsonl(path, record):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class DisplayPublisher:
    """Atomically publish the current render for the local kiosk."""

    def __init__(self, state_path, live_image_path, expected_workers):
        self.state_path = Path(state_path)
        self.live_image_path = Path(live_image_path)
        self.expected_workers = expected_workers
        self.state = {}
        self.last_image_write = 0.0
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.live_image_path.parent.mkdir(parents=True, exist_ok=True)

    def _publish(self):
        self.state["updated_at"] = _utc_now()
        _write_json(self.state_path, self.state)

    def start_cycle(self, cycle, job_id, recovery=False, held_result=None, scene=None):
        self.state = {
            "schema_version": 1,
            "demo": "pico-raytracing",
            "mode": "recovering" if recovery else "waiting_for_workers",
            "cycle": cycle,
            "job_id": job_id,
            "expected_workers": self.expected_workers,
            "ready_node_ids": [],
            "completed_tiles": 0,
            "total_tiles": 0,
            "worker_tiles": {},
            "tiles": [],
            "held_result": held_result,
            "scene": scene,
            "live_image": self.live_image_path.name,
            "phase_started_at": _utc_now(),
        }
        self.last_image_write = 0.0
        self._publish()

    def server_ready(self, _address):
        self.state["manager_ready"] = True
        self._publish()

    def on_progress(self, event, assembler=None):
        event_type = event.get("type")
        if event_type == "worker_ready":
            node_id = event["node_id"]
            ready = self.state.setdefault("ready_node_ids", [])
            if node_id not in ready:
                ready.append(node_id)
                ready.sort()
        elif event_type == "job_started":
            self.state["mode"] = "rendering"
            self.state["ready_node_ids"] = sorted(event["node_ids"])
            self.state["total_tiles"] = event["total_tiles"]
            self.state["phase_started_at"] = _utc_now()
        elif event_type == "tile_accepted":
            self.state["mode"] = "rendering"
            self.state["completed_tiles"] = event["completed_tiles"]
            self.state["total_tiles"] = event["total_tiles"]
            self.state["worker_tiles"] = event["worker_tiles"]
            tile = dict(event["tile"])
            tile["node_id"] = event["node_id"]
            self.state.setdefault("tiles", []).append(tile)

        now = time.monotonic()
        completed = self.state.get("completed_tiles", 0)
        total = self.state.get("total_tiles", 0)
        should_write_image = (
            assembler is not None
            and (now - self.last_image_write >= 0.25 or completed == total)
        )
        if should_write_image:
            temporary = self.live_image_path.with_suffix(".png.tmp")
            try:
                ray_manager.write_png(
                    temporary,
                    assembler.image,
                    assembler.job["width"],
                    assembler.job["height"],
                )
                temporary.replace(self.live_image_path)
                self.state["image_width"] = assembler.job["width"]
                self.state["image_height"] = assembler.job["height"]
                self.state.pop("display_error", None)
                self.last_image_write = now
            except OSError as exc:
                self.state["display_error"] = "live image write failed: " + str(exc)
        self._publish()

    def show_result(self, cycle, held_result, display_seconds, record):
        self.state.update(
            {
                "mode": "result",
                "cycle": cycle,
                "held_result": held_result,
                "completed_tiles": self.state.get("total_tiles", 0),
                "display_seconds": round(display_seconds, 3),
                "next_cycle_unix": time.time() + display_seconds,
                "result": record,
                "phase_started_at": _utc_now(),
            }
        )
        self._publish()

    def show_status(self, mode, record):
        self.state.update(record)
        self.state["mode"] = mode
        self.state["phase_started_at"] = _utc_now()
        self._publish()


def validate_summary(summary, expected_workers, allow_timeout=False):
    if summary.get("scene_type") == "vehicle":
        if summary.get("checksum_matches") is not None or summary.get("known_pixels_match") is not None or not isinstance(summary.get("tiles_completed"), int) or summary["tiles_completed"] <= 0 or summary["tiles_completed"] != summary.get("total_tiles"):
            raise RuntimeError("vehicle tile validation failed or unverified reference claimed verified")
    elif not summary.get("checksum_matches") or not summary.get("known_pixels_match"):
        raise RuntimeError("image validation failed")
    if summary.get("worker_count_started") != expected_workers:
        raise RuntimeError("unexpected started worker count")
    workers = summary.get("workers", [])
    if len(workers) != expected_workers:
        raise RuntimeError("worker summary count mismatch")
    for worker in workers:
        if not worker.get("watchdog_enabled"):
            raise RuntimeError("watchdog is disabled on " + worker["node_id"])
        if worker.get("watchdog_timeout_ms") != EXPECTED_WATCHDOG_MS:
            raise RuntimeError("unexpected watchdog timeout on " + worker["node_id"])
    timeouts = summary.get("worker_timeouts", [])
    if timeouts and not allow_timeout:
        raise RuntimeError("unexpected worker timeout: " + json.dumps(timeouts))
    expected_active = expected_workers - len(timeouts)
    if summary.get("worker_count_active_at_completion") != expected_active:
        raise RuntimeError("unexpected active worker count")
    expected_requeued = sum(item.get("requeued_tiles", -1) for item in timeouts)
    if summary.get("requeued_tiles") != expected_requeued:
        raise RuntimeError("unexpected requeued tile count")
    return timeouts


def run_job(args, suffix, recovery=False, allow_timeout=False, publisher=None, scene_spec=None):
    job_id = args.job_prefix + "-" + suffix
    mixed = getattr(args, "scene_mode", "sphere") == "alternating"
    if mixed:
        from scene_manager import SceneWorkload, public_scene, sphere_scene
        scene_spec = sphere_scene(recovery=True) if recovery else scene_spec
        if scene_spec is None:
            raise ValueError("alternating job requires a frozen scene")
        job = scene_spec["job"]
    else:
        job = ray_manager.RECOVERY_JOB if recovery else ray_manager.EXHIBITION_JOB
    output_path = args.output_dir / (job_id + ".png")
    trace_path = args.output_dir / (job_id + "-trace.json")
    vehicle_job = mixed and scene_spec["type"] == "vehicle"
    if vehicle_job:
        _write_json(args.output_dir / (job_id + ".vehicle.json"), scene_spec["snapshot"])
    summary = manager.run_tcp_server(
        job,
        args.vehicle_tile_size if vehicle_job else args.tile_size,
        args.host,
        args.port,
        args.manager_timeout,
        job_id,
        ready_callback=(
            (lambda address: publisher.server_ready(address))
            if publisher is not None
            else (lambda _addr: print("READY", job_id, flush=True))
        ),
        request_window=1 if vehicle_job else args.request_window,
        worker_count=args.workers,
        worker_timeout=args.worker_timeout,
        record_path=trace_path,
        workload=SceneWorkload(output_path, job) if mixed else ray_manager.RayTracingWorkload(output_path),
        progress_callback=(publisher.on_progress if publisher is not None else None),
    )
    if mixed:
        summary["scene_type"] = scene_spec["type"]
        summary["jobSpec"] = job
        summary["scene"] = public_scene(scene_spec)
    timeouts = validate_summary(summary, args.workers, allow_timeout=allow_timeout)
    _append_jsonl(args.output_dir / (args.job_prefix + "-summaries.jsonl"), summary)
    print(
        "PASS",
        job_id,
        "e2e_ms=%.3f" % summary["e2e_ms"],
        "timeouts=%d" % len(timeouts),
        flush=True,
    )
    return summary


def _manual_recovery_actions():
    return [
        "PicoとUSB serial deviceが16台すべて列挙されていることを確認する",
        "Pico、USBハブ、給電系の発熱、異臭、給電不安定を確認する",
        "16台未満の場合はUSB resetを行わず、物理接続と給電を確認する",
        "16台が揃っている場合だけray workerをresetして64×64復旧jobを1回実行する",
        "復旧確認後に新しいjob prefixで展示サイクルを再開する",
    ]


def run_cycles(args, job_runner=None):
    display_path = getattr(
        args,
        "display_state",
        args.output_dir / (args.job_prefix + "-display-state.json"),
    )
    live_image_path = getattr(
        args,
        "live_image",
        args.output_dir / (args.job_prefix + "-live-progress.png"),
    )
    publisher = DisplayPublisher(
        display_path,
        live_image_path,
        getattr(args, "workers", 16),
    )
    if job_runner is None:
        job_runner = lambda suffix, **kwargs: run_job(
            args, suffix, publisher=publisher, **kwargs
        )
    cycle_log = args.output_dir / (args.job_prefix + "-cycles.jsonl")
    if cycle_log.exists():
        raise RuntimeError("cycle log already exists; use a new job-prefix")
    records = []
    held_result = None
    mixed = getattr(args, "scene_mode", "sphere") == "alternating"
    if mixed:
        from scene_manager import choose_scene, public_scene, sphere_scene
        from live_vehicle import LiveVehicle
        source = {role: LiveVehicle(args.vehicle_api, args.output_dir / filename, args.vehicle_api_timeout, selection=role)
                  for role, filename in [('best','latest-vehicle.json'),('worst','latest-worst-vehicle.json')]}
    def recovery_scene():
        return public_scene(sphere_scene(recovery=True)) if mixed else None

    cycles = itertools.count(1) if args.cycles == 0 else range(1, args.cycles + 1)
    for cycle in cycles:
        started = time.monotonic()
        recovery_attempts = 0
        suffix = "cycle-%03d" % cycle
        spec = choose_scene(cycle, source, args.vehicle_preset, args.sphere_preset) if mixed else None
        job_options = {"scene_spec": spec} if mixed else {}
        scene = public_scene(spec) if mixed else None
        if scene and scene.get("sourceError"):
            print("VEHICLE_SOURCE_WARNING", scene["sourceError"], flush=True)
        publisher.start_cycle(
            cycle,
            args.job_prefix + "-" + suffix,
            held_result=held_result,
            scene=scene,
        )
        try:
            summary = job_runner(
                suffix,
                allow_timeout=True,
                **job_options,
            )
            if summary.get("worker_timeouts"):
                recovery_attempts = 1
                publisher.start_cycle(
                    cycle,
                    args.job_prefix + "-cycle-%03d-recovery" % cycle,
                    recovery=True,
                    held_result={
                        "job_id": summary["job_id"],
                        "checksum32": summary["checksum32"],
                        "output_path": summary["output_path"],
                        "scene": scene,
                    },
                    scene=recovery_scene(),
                )
                job_runner("cycle-%03d-recovery" % cycle, recovery=True)
            held_result = {
                "job_id": summary["job_id"],
                "checksum32": summary["checksum32"],
                "output_path": summary["output_path"],
                "scene": scene,
            }
        except Exception as exc:
            if recovery_attempts:
                recovery_exc = exc
                source_exc = RuntimeError(
                    "completed image reported a worker timeout"
                )
            else:
                source_exc = exc
                recovery_attempts = 1
                publisher.start_cycle(
                    cycle,
                    args.job_prefix + "-cycle-%03d-recovery" % cycle,
                    recovery=True,
                    held_result=held_result,
                    scene=recovery_scene(),
                )
                try:
                    recovery = job_runner(
                        "cycle-%03d-recovery" % cycle,
                        recovery=True,
                    )
                except Exception as caught_recovery_exc:
                    recovery_exc = caught_recovery_exc
                else:
                    recovery_exc = None
            if recovery_exc is not None:
                record = {
                    "cycle": cycle,
                    "outcome": "manual_recovery_required",
                    "error_type": type(source_exc).__name__,
                    "error": str(source_exc),
                    "recovery_attempts": recovery_attempts,
                    "recovery_error_type": type(recovery_exc).__name__,
                    "recovery_error": str(recovery_exc),
                    "held_result": held_result,
                    "manual_recovery_actions": _manual_recovery_actions(),
                }
                _append_jsonl(cycle_log, record)
                publisher.show_status("waiting_for_manual_recovery", record)
                print("WAITING_SCREEN", json.dumps(record), flush=True)
                return records + [record]
            record = {
                "cycle": cycle,
                "outcome": "recovered_without_new_image",
                "error_type": type(source_exc).__name__,
                "error": str(source_exc),
                "recovery_attempts": recovery_attempts,
                "recovery_job_id": recovery["job_id"],
                "held_result": held_result,
            }
            _append_jsonl(cycle_log, record)
            records.append(record)
            publisher.show_status("holding_previous_result", record)
            elapsed = time.monotonic() - started
            time.sleep(max(0, args.recovery_cycle_seconds - elapsed))
            continue

        elapsed = time.monotonic() - started
        cycle_target_seconds = (
            args.recovery_cycle_seconds if recovery_attempts else args.cycle_seconds
        )
        # 接続待ち等が長くても、検査済み完成画像を表示してから次cycleへ進む。
        # 計算のtimeoutは維持し、表示時間不足だけでsystemd再起動を発生させない。
        display_seconds = max(args.minimum_display_seconds, cycle_target_seconds - elapsed)
        record = {
            "cycle": cycle,
            "outcome": "completed",
            "job_id": summary["job_id"],
            "checksum32": summary["checksum32"],
            "e2e_ms": summary["e2e_ms"],
            "startup_ready_ms": summary["startup_ready_ms"],
            "worker_timeouts": summary["worker_timeouts"],
            "requeued_tiles": summary["requeued_tiles"],
            "recovery_attempts": recovery_attempts,
            "cycle_target_seconds": cycle_target_seconds,
            "scene": scene,
            "image_validation": summary.get("validation", "reference CRC + known pixels"),
            "display_seconds": round(display_seconds, 3),
            "cycle_extended_seconds": round(max(0, elapsed + display_seconds - cycle_target_seconds), 3),
        }
        _append_jsonl(cycle_log, record)
        records.append(record)
        publisher.show_result(cycle, held_result, display_seconds, record)
        print("RESULT_DISPLAY", json.dumps(record), flush=True)
        time.sleep(display_seconds)
    return records


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-mode", choices=("sphere", "alternating"), default="sphere")
    parser.add_argument("--sphere-preset", choices=("recovery", "preview", "exhibition", "detailed"), default="exhibition")
    parser.add_argument("--vehicle-api", help="Pi 4 /api/state URL; required for alternating")
    parser.add_argument("--vehicle-api-timeout", type=float, default=2)
    parser.add_argument("--vehicle-preset", choices=("recovery", "preview", "exhibition", "smooth"), default="preview")
    parser.add_argument("--vehicle-tile-size", type=int, default=8)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--tile-size", type=int, default=16)
    parser.add_argument("--request-window", type=int, default=4)
    parser.add_argument("--worker-timeout", type=float, default=5)
    parser.add_argument("--manager-timeout", type=float, default=60)
    parser.add_argument(
        "--cycles",
        type=int,
        default=0,
        help="number of cycles; 0 keeps running until stopped",
    )
    parser.add_argument("--cycle-seconds", type=float, default=40)
    parser.add_argument("--recovery-cycle-seconds", type=float, default=45)
    parser.add_argument("--minimum-display-seconds", type=float, default=2)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--job-prefix",
        default="raytracing-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument("--display-state", type=Path)
    parser.add_argument("--live-image", type=Path)
    args = parser.parse_args()
    if args.workers <= 0 or args.cycles < 0 or args.tile_size <= 0:
        parser.error("workers and tile size must be positive; cycles must be nonnegative")
    if (
        args.worker_timeout <= 0
        or args.manager_timeout <= 0
        or args.cycle_seconds <= 0
        or args.recovery_cycle_seconds < args.cycle_seconds
        or args.minimum_display_seconds < 0
    ):
        parser.error("timeouts must be positive")
    if not 1 <= args.workers <= 16 or not 1 <= args.tile_size <= 16 or not 1 <= args.vehicle_tile_size <= 16 or not 0 < args.vehicle_api_timeout <= 10:
        parser.error("workers:1..16, tile sizes:1..16, vehicle timeout:(0,10]")
    if args.scene_mode == "alternating":
        from live_vehicle import validate_api_url
        try:
            validate_api_url(args.vehicle_api or "")
        except ValueError as exc:
            parser.error(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.display_state is None:
        args.display_state = args.output_dir / "display-state.json"
    if args.live_image is None:
        args.live_image = args.output_dir / "live-progress.png"
    return args


if __name__ == "__main__":
    result = run_cycles(parse_args())
    if result and result[-1]["outcome"] == "manual_recovery_required":
        # systemd uses 78 to keep the waiting screen visible without retrying.
        raise SystemExit(78)
