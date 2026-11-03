import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "validate-pico-manager.py"


def load_validator():
    mpremote = types.ModuleType("mpremote")
    transport_serial = types.ModuleType("mpremote.transport_serial")
    transport_serial.SerialTransport = object
    sys.modules.setdefault("mpremote", mpremote)
    sys.modules.setdefault("mpremote.transport_serial", transport_serial)
    spec = importlib.util.spec_from_file_location("validate_pico_manager", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class ExhibitionOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        module = self.validator
        module.LOG = Path(self.temporary.name)
        module.JOB_PREFIX = "issue53-test"
        module.NODE_IDS = ["pico-%02d" % index for index in range(1, 17)]
        module.CYCLE_SECONDS = 40.0
        module.MINIMUM_RESULT_DISPLAY_SECONDS = 2.0
        self.clock = FakeClock()
        self.original_monotonic = module.time.monotonic
        self.original_sleep = module.time.sleep
        self.original_run_case = module.run_case
        module.time.monotonic = self.clock.monotonic
        module.time.sleep = self.clock.sleep
        self.addCleanup(self.restore_module)

    def restore_module(self):
        module = self.validator
        module.time.monotonic = self.original_monotonic
        module.time.sleep = self.original_sleep
        module.run_case = self.original_run_case

    def summary(self, job_id, count, checksum="1a26b685"):
        return {
            "job_id": job_id,
            "checksum32": checksum,
            "known_pixels_match": True,
            "tiles_completed": 16 if checksum == "e590a9e7" else 320,
            "worker_count_started": count,
            "worker_count_active_at_completion": count,
            "worker_timeouts": [],
            "requeued_tiles": 0,
            "node_ids": self.validator.NODE_IDS[:count],
            "startup_ready_ms": 1000.0,
            "e2e_ms": 2000.0,
        }

    def test_failure_type_and_workers_are_parsed(self):
        errors = "\n".join([
            "FAILURE_TYPE AllWorkersUnavailable",
            "FAILURE_MESSAGE all workers unavailable",
            'FAILURE_WORKERS [{"node_id": "pico-01", "timed_out": true}]',
        ])
        failure_type, failures, records = (
            self.validator._manager_failure_details(errors)
        )
        self.assertEqual(failure_type, "AllWorkersUnavailable")
        self.assertEqual(failures[0]["node_id"], "pico-01")
        self.assertEqual(len(records), 1)

    def test_one_node_failure_recovers_once_and_next_cycle_completes(self):
        calls = []

        def fake_run_case(tag, count, job="small", started_callback=None, **_kwargs):
            calls.append((tag, count, job))
            if started_callback is not None:
                started_callback(self.clock.monotonic())
            if tag == "cycle-02-01n":
                self.clock.now += 5
                raise self.validator.AllWorkersUnavailableCase(
                    "issue53-test-cycle-02-01n",
                    [{"node_id": "pico-01", "timed_out": True}],
                    "controlled timeout",
                )
            if job == "recovery":
                self.clock.now += 10
                return self.summary(
                    "issue53-test-cycle-02-recovery",
                    16,
                    "e590a9e7",
                )
            self.clock.now += 2 if count == 1 else 3
            return self.summary("issue53-test-" + tag, count)

        self.validator.run_case = fake_run_case
        records = self.validator.run_exhibition_cycles(3)

        self.assertEqual([record["outcome"] for record in records], [
            "completed", "recovered", "completed",
        ])
        recovery_calls = [call for call in calls if call[2] == "recovery"]
        self.assertEqual(len(recovery_calls), 1)
        self.assertIn(("cycle-03-01n", 1, "exhibition"), calls)
        incidents = self.read_jsonl("issue53-test-incidents.jsonl")
        self.assertEqual(incidents[0]["source_job_id"], "issue53-test-cycle-02-01n")
        self.assertEqual(
            incidents[0]["recovery_job_id"],
            "issue53-test-cycle-02-recovery",
        )
        display = json.loads(
            (self.validator.LOG / "issue53-test-display-state.json").read_text()
        )
        self.assertEqual(display["mode"], "result")

    def test_failed_recovery_enters_waiting_state_without_retry(self):
        calls = []

        def fake_run_case(tag, count, job="small", started_callback=None, **_kwargs):
            calls.append((tag, count, job))
            if started_callback is not None:
                started_callback(self.clock.monotonic())
            if tag == "cycle-02-01n":
                self.clock.now += 5
                raise self.validator.AllWorkersUnavailableCase(
                    "issue53-test-cycle-02-01n",
                    [{"node_id": "pico-01", "timed_out": True}],
                    "controlled timeout",
                )
            if job == "recovery":
                self.clock.now += 10
                raise RuntimeError("recovery unavailable")
            self.clock.now += 2 if count == 1 else 3
            return self.summary("issue53-test-" + tag, count)

        self.validator.run_case = fake_run_case
        records = self.validator.run_exhibition_cycles(3)

        self.assertEqual(records[-1]["outcome"], "manual_recovery_required")
        self.assertEqual(len([call for call in calls if call[2] == "recovery"]), 1)
        self.assertNotIn(("cycle-03-01n", 1, "exhibition"), calls)
        display = json.loads(
            (self.validator.LOG / "issue53-test-display-state.json").read_text()
        )
        self.assertEqual(display["mode"], "waiting_for_manual_recovery")
        self.assertGreater(len(display["manual_recovery_actions"]), 0)

    def read_jsonl(self, filename):
        return [
            json.loads(line)
            for line in (self.validator.LOG / filename).read_text().splitlines()
        ]


if __name__ == "__main__":
    unittest.main()
