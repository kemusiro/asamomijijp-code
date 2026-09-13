"""Host-only tests for the Pico carrier-board RGB status LED."""

from pathlib import Path
import sys
import types
import unittest

NETWORK_DIR = Path(__file__).resolve().parents[1]
PICO_DIR = NETWORK_DIR.parent / "pico"
for directory in (str(NETWORK_DIR), str(PICO_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import rgb_status  # noqa: E402


class FakePin:
    OUT = 1

    def __init__(self, number, mode):
        self.number = number
        self.mode = mode
        self.value = None

    def init(self, mode, value=None):
        self.mode = mode
        self.value = value


class FakePwm:
    def __init__(self, pin):
        self.pin = pin
        self.frequency = None
        self.duty = None
        self.deinitialized = False

    def freq(self, value):
        self.frequency = value

    def duty_u16(self, value):
        self.duty = value

    def deinit(self):
        self.deinitialized = True


class FakeMachine:
    Pin = FakePin
    PWM = FakePwm


class RgbStatusLedTests(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        self.led = rgb_status.RgbStatusLed(
            machine_module=FakeMachine,
            sleep_ms=self.sleeps.append,
        )

    def duties(self):
        return {
            color: pwm.duty for color, pwm in self.led._pwm.items()
        }

    def test_initializes_expected_pins_at_2khz_and_off(self):
        self.assertEqual(self.led._pins["green"].number, 8)
        self.assertEqual(self.led._pins["blue"].number, 9)
        self.assertEqual(self.led._pins["red"].number, 10)
        self.assertTrue(
            all(
                pwm.frequency == rgb_status.PWM_FREQUENCY_HZ
                for pwm in self.led._pwm.values()
            )
        )
        self.assertEqual(self.duties(), {"green": 0, "blue": 0, "red": 0})

    def test_worker_states_have_distinct_colors(self):
        expected = {
            "waiting": {"green": 8192, "blue": 0, "red": 0},
            "job_received": {"green": 32768, "blue": 32768, "red": 32768},
            "computing": {"green": 16384, "blue": 32768, "red": 0},
            "sending": {"green": 32768, "blue": 32768, "red": 32768},
            "tile_waiting": {"green": 0, "blue": 8192, "red": 0},
            "success": {"green": 32768, "blue": 0, "red": 0},
        }
        for state, duties in expected.items():
            with self.subTest(state=state):
                getattr(self.led, state)()
                self.assertEqual(self.duties(), duties)

    def test_communication_error_flashes_twice_then_returns_to_waiting(self):
        self.led.communication_error()
        self.assertEqual(self.sleeps, [120, 100, 120, 100])
        self.assertEqual(self.duties(), {"green": 8192, "blue": 0, "red": 0})

    def test_other_error_flashes_red_then_returns_to_waiting(self):
        self.led.error()
        self.assertEqual(self.sleeps, [250])
        self.assertEqual(self.duties(), {"green": 8192, "blue": 0, "red": 0})

    def test_invalid_duty_is_rejected(self):
        for invalid in (-1, 65536, 1.5, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.led.set_rgb(invalid, 0, 0)

    def test_deinit_stops_pwm_and_drives_every_pin_low(self):
        self.led.success()
        self.led.deinit()
        self.assertTrue(all(pwm.deinitialized for pwm in self.led._pwm.values()))
        self.assertTrue(all(pin.value == 0 for pin in self.led._pins.values()))


class RecordingStatusLed:
    def __init__(self):
        self.states = []

    def __getattr__(self, name):
        return lambda: self.states.append(name)


class FakeProtocol:
    PROTOCOL_VERSION = "protocol"
    ALGORITHM_VERSION = "algorithm"
    OUTPUT_VERSION = "output"
    CHECKSUM_VERSION = "checksum"

    class ProtocolError(Exception):
        pass

    def __init__(self):
        self.messages = [
            (
                {
                    "type": "job",
                    "protocol_version": self.PROTOCOL_VERSION,
                    "algorithm_version": self.ALGORITHM_VERSION,
                    "output_version": self.OUTPUT_VERSION,
                    "checksum_version": self.CHECKSUM_VERSION,
                    "symmetry": "real-axis-upper-half",
                    "job_id": "led-test",
                    "job": {},
                    "tile_size": 1,
                },
                b"",
            ),
            (
                {
                    "type": "tile",
                    "job_id": "led-test",
                    "tile_id": 1,
                    "x0": 0,
                    "y0": 0,
                    "width": 1,
                    "height": 1,
                },
                b"",
            ),
            (
                {"type": "complete", "job_id": "led-test", "checksum32": "0"},
                b"",
            ),
        ]

    def send_frame(self, _conn, _message, _payload=b""):
        pass

    def recv_frame(self, _conn):
        return self.messages.pop(0)

    def require_message_type(self, message, expected):
        if message.get("type") != expected:
            raise self.ProtocolError("unexpected message")

    def parse_start_datagram(self, _data, _job_id):
        return {"type": "start"}


class FakeUdp:
    def recvfrom(self, _size):
        return b"start", ("127.0.0.1", 8766)


class PicoWorkerLedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_network = types.SimpleNamespace(STA_IF=0)
        fake_config = types.SimpleNamespace(
            WIFI_TIMEOUT_SECONDS=20,
            SOCKET_TIMEOUT_SECONDS=30,
            RECONNECT_DELAY_SECONDS=3,
        )
        saved_network = sys.modules.get("network")
        saved_config = sys.modules.get("network_config")
        sys.modules["network"] = fake_network
        sys.modules["network_config"] = fake_config
        try:
            import pico_worker

            cls.worker = pico_worker
        finally:
            if saved_network is None:
                del sys.modules["network"]
            else:
                sys.modules["network"] = saved_network
            if saved_config is None:
                del sys.modules["network_config"]
            else:
                sys.modules["network_config"] = saved_config

    def test_worker_session_emits_led_states_in_processing_order(self):
        fake_protocol = FakeProtocol()
        fake_core = types.SimpleNamespace(
            ALGORITHM_VERSION=fake_protocol.ALGORITHM_VERSION,
            OUTPUT_VERSION=fake_protocol.OUTPUT_VERSION,
            CHECKSUM_VERSION=fake_protocol.CHECKSUM_VERSION,
            validate_job=lambda _job: None,
            compute_tile_into=(
                lambda _job, _x, _y, _w, _h, output, _mode: output.__setitem__(
                    0, 0
                )
            ),
        )
        original_protocol = self.worker.protocol
        original_core = self.worker.core
        original_ticks_ms = self.worker._ticks_ms
        original_ticks_diff = self.worker._ticks_diff
        original_mem_free = self.worker._mem_free
        self.worker.protocol = fake_protocol
        self.worker.core = fake_core
        self.worker._ticks_ms = lambda: 1
        self.worker._ticks_diff = lambda later, earlier: later - earlier
        self.worker._mem_free = lambda: 1000
        led = RecordingStatusLed()
        try:
            result = self.worker.run_worker_session(
                object(), FakeUdp(), "pico-led-test", 8766, status_led=led
            )
        finally:
            self.worker.protocol = original_protocol
            self.worker.core = original_core
            self.worker._ticks_ms = original_ticks_ms
            self.worker._ticks_diff = original_ticks_diff
            self.worker._mem_free = original_mem_free

        self.assertEqual(result["tiles_completed"], 1)
        self.assertEqual(
            led.states,
            [
                "job_received",
                "tile_waiting",
                "computing",
                "sending",
                "tile_waiting",
                "success",
            ],
        )

    def test_run_once_deinitializes_an_internally_created_led(self):
        led = RecordingStatusLed()
        original_led_class = self.worker.rgb_status.RgbStatusLed
        original_run_once = self.worker._run_once
        self.worker.rgb_status.RgbStatusLed = lambda: led
        self.worker._run_once = lambda _stall, _seconds, _led: "completed"
        try:
            result = self.worker.run_once()
        finally:
            self.worker.rgb_status.RgbStatusLed = original_led_class
            self.worker._run_once = original_run_once

        self.assertEqual(result, "completed")
        self.assertEqual(led.states, ["deinit"])

    def test_communication_errors_are_classified_separately(self):
        self.assertTrue(self.worker._is_communication_error(OSError("network")))
        self.assertTrue(
            self.worker._is_communication_error(
                RuntimeError("Wi-Fi connection timed out")
            )
        )
        self.assertFalse(self.worker._is_communication_error(ValueError("job")))


if __name__ == "__main__":
    unittest.main()
