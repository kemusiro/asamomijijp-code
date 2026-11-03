import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/validate-pico-wifi-power-cycles.py"
SPEC = importlib.util.spec_from_file_location("wifi_power_cycles", SCRIPT)
wifi_power_cycles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wifi_power_cycles)


def valid_summary():
    return {
        "checksum32": "4e25d3ba",
        "checksum_matches": True,
        "known_pixels_match": True,
        "worker_count_started": 16,
        "node_ids": ["pico-%02d" % number for number in range(1, 17)],
        "worker_count_active_at_completion": 16,
        "worker_timeouts": [],
        "requeued_tiles": 0,
        "startup_ready_ms": 59000,
    }


class WifiPowerCycleSummaryTests(unittest.TestCase):
    def test_accepts_complete_recovery_within_deadline(self):
        self.assertEqual(
            wifi_power_cycles.validate_recovery_summary(
                valid_summary(), 16, 60
            ),
            59,
        )

    def test_excludes_manual_wait_before_power_on(self):
        summary = valid_summary()
        summary["startup_ready_ms"] = 83000
        self.assertEqual(
            wifi_power_cycles.validate_recovery_summary(
                summary,
                16,
                60,
                power_on_detected_after_manager_seconds=24,
            ),
            59,
        )

    def test_rejects_recovery_after_deadline(self):
        summary = valid_summary()
        summary["startup_ready_ms"] = 60001
        with self.assertRaisesRegex(RuntimeError, "期限超過"):
            wifi_power_cycles.validate_recovery_summary(summary, 16, 60)

    def test_rejects_missing_node_even_if_count_is_sixteen(self):
        summary = valid_summary()
        summary["node_ids"][-1] = "pico-15"
        with self.assertRaisesRegex(RuntimeError, "node ID集合"):
            wifi_power_cycles.validate_recovery_summary(summary, 16, 60)

    def test_rejects_timeout_or_requeue(self):
        summary = valid_summary()
        summary["worker_timeouts"] = [{"node_id": "pico-04"}]
        summary["requeued_tiles"] = 1
        with self.assertRaisesRegex(RuntimeError, "worker timeout.*再割り当て"):
            wifi_power_cycles.validate_recovery_summary(summary, 16, 60)


if __name__ == "__main__":
    unittest.main()
