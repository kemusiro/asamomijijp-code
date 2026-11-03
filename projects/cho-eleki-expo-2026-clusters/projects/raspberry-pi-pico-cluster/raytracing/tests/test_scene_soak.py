import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zlib


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/audit-pico-scene-soak.py"
spec = importlib.util.spec_from_file_location("scene_soak", SCRIPT)
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


def fixture():
    cycles, summaries, journal = [], [], []
    for i, role in enumerate(("worst", "best", "sphere"), 1):
        sphere = role == "sphere"
        width, height, size, count = (480, 270, 16, 510) if sphere else (320, 180, 8, 920)
        scene = dict(type="sphere") if sphere else dict(
            type="vehicle", role=role, modelId=role,
            source=dict(distanceM=0.1 if role == "worst" else 100, carId=role))
        job = "test-cycle-%03d" % i
        checksum = "a70b3024" if sphere else "12345678"
        workers = [dict(node_id="pico-%02d" % n, tiles_completed=count//16 + (n <= count%16),
                        worker_mem_free_min_sampled=1000, reset_cause_name="PWRON_RESET",
                        failure=None, disconnected=False, timed_out=False, requeued_tiles=0,
                        ignored_tile_results=0, watchdog_enabled=True, watchdog_timeout_ms=8000)
                   for n in range(1, 17)]
        c = dict(cycle=i, outcome="completed", job_id=job, scene=scene,
                 checksum32=checksum, recovery_attempts=0, worker_timeouts=[], requeued_tiles=0)
        cycles.append(c)
        summaries.append(dict(job_id=job, scene=deepcopy(scene), jobSpec=dict(width=width,height=height),
                              tile_size=size, tiles_completed=count, recording_events=count,
                              payload_bytes_received=width*height*3, checksum32=checksum,
                              workers=workers, node_ids=[w["node_id"] for w in workers],
                              worker_count_started=16, worker_count_active_at_completion=16,
                              worker_timeouts=[], startup_failures=[], startup_failure_count=0,
                              requeued_tiles=0, ignored_tile_results=0, checksum_matches=True,
                              known_pixels_match=True, e2e_ms=44000))
        at = datetime(2026, 10, 17, tzinfo=timezone.utc) + timedelta(hours=i*2)
        journal.append(at.isoformat() + " host runner: RESULT_DISPLAY " + json.dumps(c))
    return cycles, summaries, "\n".join(journal)


class SceneSoakTests(unittest.TestCase):
    def test_complete_three_hour_interval(self):
        report = soak.audit(*fixture(), 1, 3)
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["completed_interval_seconds"], 14400)

    def test_missing_duplicate_cycle_and_summary_rejected(self):
        for target in ("cycle", "summary"):
            for duplicate in (False, True):
                with self.subTest(target=target, duplicate=duplicate):
                    c, s, j = fixture()
                    rows = c if target == "cycle" else s
                    rows.append(deepcopy(rows[0])) if duplicate else rows.pop(1)
                    self.assertFalse(soak.audit(c, s, j, 1, 3)["passed"])

    def test_recovery_worker_loss_reference_and_heap_rejected(self):
        for defect in ("recovery", "missing_node", "timeout", "heap", "reference", "reset"):
            with self.subTest(defect=defect):
                c, s, j = fixture()
                if defect == "recovery": c[1]["outcome"] = "recovered_without_new_image"
                if defect == "missing_node": s[1]["workers"].pop()
                if defect == "timeout": s[1]["workers"][0]["timed_out"] = True
                if defect == "heap": s[1]["workers"][0]["worker_mem_free_min_sampled"] = None
                if defect == "reference": s[2]["checksum_matches"] = False
                if defect == "reset": s[1]["workers"][0]["reset_cause_name"] = "WDT_RESET"
                self.assertFalse(soak.audit(c, s, j, 1, 3)["passed"])

    def test_short_interval_and_wrong_order_rejected(self):
        self.assertFalse(soak.audit(*fixture(), 1, 3, minimum_hours=5)["passed"])
        c, s, j = fixture()
        s[0]["scene"]["role"] = "best"
        self.assertFalse(soak.audit(c, s, j, 1, 3)["passed"])

    def test_valid_same_role_cache_warning_is_retained(self):
        c, s, _ = fixture()
        c[0]["scene"]["sourceError"] = "API offline; same-role cache"
        s[0]["scene"] = deepcopy(c[0]["scene"])
        j = "\n".join((datetime(2026, 10, 17, tzinfo=timezone.utc)+timedelta(hours=i*2)).isoformat()
                      + " host runner: RESULT_DISPLAY " + json.dumps(row) for i,row in enumerate(c))
        report = soak.audit(c, s, j, 1, 3)
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(len(report["warnings"]), 1)

    def test_truncated_jsonl_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"partial.jsonl"
            p.write_text('{"cycle":1}\n{"cycle":')
            with self.assertRaises(ValueError): soak.read_jsonl(p)

    def test_trace_crc_grid_and_duplicate_events(self):
        c, summaries, j = fixture()
        s = summaries[0]
        # A small independent trace exercises edge tiles and RGB integrity.
        s["jobSpec"] = dict(width=3, height=2)
        s["tile_size"] = 2
        s["workers"] = [dict(node_id="pico-01", tiles_completed=2)]
        pixels = bytes(range(18))
        s["checksum32"] = "%08x" % zlib.crc32(pixels)
        trace = dict(format="tile-progress-v2", image_encoding="base64-rgb888-row-major",
                     tile_mirroring="none", job_id=s["job_id"], job=s["jobSpec"],
                     summary={k:v for k,v in s.items() if k not in ("scene","scene_type","jobSpec")},
                     tiles=[dict(tile_id=0,x0=0,y0=0,width=2,height=2),
                            dict(tile_id=1,x0=2,y0=0,width=1,height=2)],
                     events=[dict(tile_id=0,node_id="pico-01"),dict(tile_id=1,node_id="pico-01")],
                     image_base64=base64.b64encode(pixels).decode())
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"trace.json"
            p.write_text(json.dumps(trace))
            soak.check_trace(p,s)
            for defect in ("crc", "grid", "events"):
                broken = deepcopy(trace)
                if defect == "crc": broken["image_base64"] = base64.b64encode(bytes(18)).decode()
                if defect == "grid": broken["tiles"][1]["x0"] = 1
                if defect == "events": broken["events"][1]["tile_id"] = 0
                p.write_text(json.dumps(broken))
                with self.assertRaises(ValueError): soak.check_trace(p,s)


if __name__ == "__main__":
    unittest.main()
