import importlib.util
from pathlib import Path
import tempfile
import types
import unittest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "run-pico-raytracing-exhibition.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_pico_ray_exhibition", SCRIPT)
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


class ExhibitionCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.args = types.SimpleNamespace(
            output_dir=Path(self.temporary.name),
            job_prefix="ray-test",
            cycles=2,
            cycle_seconds=40,
            recovery_cycle_seconds=45,
            minimum_display_seconds=2,
        )
        self.clock = FakeClock()
        self.original_monotonic = self.runner.time.monotonic
        self.original_sleep = self.runner.time.sleep
        self.runner.time.monotonic = self.clock.monotonic
        self.runner.time.sleep = self.clock.sleep
        self.addCleanup(self.restore_clock)

    def restore_clock(self):
        self.runner.time.monotonic = self.original_monotonic
        self.runner.time.sleep = self.original_sleep

    @staticmethod
    def summary(job_id, timeouts=None):
        return {
            "job_id": job_id,
            "checksum32": "b6b3fcf8",
            "output_path": "/tmp/" + job_id + ".png",
            "e2e_ms": 29000,
            "startup_ready_ms": 3000,
            "worker_timeouts": list(timeouts or []),
            "requeued_tiles": sum(
                item["requeued_tiles"] for item in (timeouts or [])
            ),
        }

    def test_two_cycles_keep_forty_second_interval(self):
        def job(suffix, **_kwargs):
            self.clock.now += 32
            return self.summary("ray-test-" + suffix)

        records = self.runner.run_cycles(self.args, job_runner=job)
        self.assertEqual(len(records), 2)
        self.assertEqual(self.clock.now, 80)
        self.assertEqual(records[0]["display_seconds"], 8)

    def test_timeout_runs_one_recovery_before_display(self):
        calls = []

        def job(suffix, recovery=False, **_kwargs):
            calls.append((suffix, recovery))
            self.clock.now += 30 if not recovery else 2
            if recovery:
                return self.summary("ray-test-" + suffix)
            return self.summary(
                "ray-test-" + suffix,
                [{"node_id": "pico-01", "requeued_tiles": 4}],
            )

        self.args.cycles = 1
        records = self.runner.run_cycles(self.args, job_runner=job)
        self.assertEqual(records[0]["recovery_attempts"], 1)
        self.assertEqual(records[0]["cycle_target_seconds"], 45)
        self.assertEqual(records[0]["display_seconds"], 13)
        self.assertEqual(calls, [("cycle-001", False), ("cycle-001-recovery", True)])

    def test_slow_success_keeps_result_visible_without_restarting(self):
        def job(suffix, **_kwargs):
            self.clock.now += 45
            return self.summary("ray-test-" + suffix)

        self.args.cycles = 1
        records = self.runner.run_cycles(self.args, job_runner=job)
        self.assertEqual(records[0]["outcome"], "completed")
        self.assertEqual(records[0]["display_seconds"], 2)
        self.assertEqual(records[0]["cycle_extended_seconds"], 7)
        self.assertEqual(self.clock.now, 47)

    def test_failed_job_and_recovery_enter_waiting_state_once(self):
        calls = []

        def job(suffix, recovery=False, **_kwargs):
            calls.append((suffix, recovery))
            raise RuntimeError("unavailable")

        self.args.cycles = 1
        records = self.runner.run_cycles(self.args, job_runner=job)
        self.assertEqual(records[-1]["outcome"], "manual_recovery_required")
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls,
            [("cycle-001", False), ("cycle-001-recovery", True)],
        )

    def test_failed_timeout_recovery_is_not_retried(self):
        calls = []

        def job(suffix, recovery=False, **_kwargs):
            calls.append((suffix, recovery))
            if recovery:
                raise RuntimeError("recovery unavailable")
            return self.summary(
                "ray-test-" + suffix,
                [{"node_id": "pico-01", "requeued_tiles": 4}],
            )

        self.args.cycles = 1
        records = self.runner.run_cycles(self.args, job_runner=job)
        self.assertEqual(records[-1]["outcome"], "manual_recovery_required")
        self.assertEqual(
            calls,
            [("cycle-001", False), ("cycle-001-recovery", True)],
        )


if __name__ == "__main__":
    unittest.main()
