import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest


SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "validate-pico-watchdog.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_pico_watchdog", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WatchdogOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.args = types.SimpleNamespace(
            output_dir=Path(self.temporary.name),
            job_prefix="issue53-test",
        )

    @staticmethod
    def summary(job_id):
        return {
            "job_id": job_id,
            "checksum32": "1a26b685",
            "known_pixels_match": True,
            "startup_ready_ms": 1000.0,
            "e2e_ms": 2000.0,
        }

    def test_failure_details_are_parsed(self):
        error = "\n".join(
            [
                "FAILURE_TYPE AllWorkersUnavailable",
                'FAILURE_WORKERS [{"node_id": "pico-01", "timed_out": true}]',
            ]
        )
        failure_type, failures = self.validator._manager_failure_details(error)
        self.assertEqual(failure_type, "AllWorkersUnavailable")
        self.assertEqual(failures[0]["node_id"], "pico-01")

    def test_success_recovers_once_and_runs_following_cycle(self):
        calls = []

        def normal(suffix):
            calls.append(("normal", suffix))
            return self.summary("issue53-test-" + suffix)

        def failure():
            calls.append(("failure", None))
            return {
                "job_id": "issue53-test-all-workers-unavailable",
                "failure_type": "AllWorkersUnavailable",
                "worker_failures": [
                    {"node_id": "pico-01", "timed_out": True}
                ],
            }

        def recovery(suffix):
            calls.append(("recovery", suffix))
            result = self.summary("issue53-test-" + suffix)
            result["checksum32"] = "e590a9e7"
            return result

        incident = self.validator.run_all_workers_recovery(
            self.args,
            normal_runner=normal,
            failure_runner=failure,
            recovery_runner=recovery,
        )

        self.assertEqual(incident["outcome"], "recovered")
        self.assertEqual(len([call for call in calls if call[0] == "recovery"]), 1)
        self.assertEqual(calls[-1], ("normal", "cycle-after-recovery"))
        saved = json.loads(
            (self.args.output_dir / "issue53-test-incidents.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(saved["source_job_id"], incident["source_job_id"])
        display = json.loads(
            (self.args.output_dir / "issue53-test-display-state.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(display["mode"], "result")

    def test_failed_recovery_waits_without_retry_or_following_cycle(self):
        calls = []

        def normal(suffix):
            calls.append(("normal", suffix))
            return self.summary("issue53-test-" + suffix)

        def failure():
            return {
                "job_id": "issue53-test-all-workers-unavailable",
                "failure_type": "AllWorkersUnavailable",
                "worker_failures": [
                    {"node_id": "pico-01", "timed_out": True}
                ],
            }

        def recovery(suffix):
            calls.append(("recovery", suffix))
            raise RuntimeError("recovery unavailable")

        incident = self.validator.run_all_workers_recovery(
            self.args,
            normal_runner=normal,
            failure_runner=failure,
            recovery_runner=recovery,
        )

        self.assertEqual(incident["outcome"], "manual_recovery_required")
        self.assertEqual(len([call for call in calls if call[0] == "recovery"]), 1)
        self.assertNotIn(("normal", "cycle-after-recovery"), calls)
        display = json.loads(
            (self.args.output_dir / "issue53-test-display-state.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(display["mode"], "waiting_for_manual_recovery")
        self.assertTrue(display["manual_recovery_actions"])


if __name__ == "__main__":
    unittest.main()
