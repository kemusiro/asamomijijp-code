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
        self.sent = []
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
                    "type": "start",
                    "protocol_version": self.PROTOCOL_VERSION,
                    "job_id": "led-test",
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

    def send_frame(self, _conn, message, _payload=b""):
        self.sent.append(message)

    def recv_frame(self, _conn, timeout_handler=None):
        return self.messages.pop(0)

    def require_message_type(self, message, expected):
        if message.get("type") != expected:
            raise self.ProtocolError("unexpected message")

    def parse_start_datagram(self, _data, _job_id):
        return {"type": "start"}

    def validate_start_message(self, message, job_id):
        self.require_message_type(message, "start")
        if message.get("job_id") != job_id:
            raise self.ProtocolError("unexpected job")
        return message


class FakeUdp:
    def recvfrom(self, _size):
        return b"start", ("127.0.0.1", 8766)


class FakeConn:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


class FakeWatchdog:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.feed_count = 0

    def feed(self):
        self.feed_count += 1


class FakeWifiTime:
    def __init__(self):
        self.now_ms = 0
        self.sleeps = []

    def ticks_ms(self):
        return self.now_ms

    def ticks_diff(self, later, earlier):
        return later - earlier

    def sleep_ms(self, milliseconds):
        self.sleeps.append(milliseconds)
        self.now_ms += milliseconds


class FakeWlan:
    PM_NONE = 16
    PM_PERFORMANCE = 10555714
    PM_POWERSAVE = 17

    def __init__(self, connect_after_polls=1, connected=False):
        self.connect_after_polls = connect_after_polls
        self.connected = connected
        self.connecting = False
        self.polls = 0
        self.active_state = connected
        self.actions = []
        self.pm = None

    def isconnected(self):
        if self.connecting and self.connect_after_polls is not None:
            self.polls += 1
            if self.polls >= self.connect_after_polls:
                self.connected = True
        return self.connected

    def active(self, value=None):
        if value is None:
            return self.active_state
        self.actions.append(("active", value))
        self.active_state = value
        if not value:
            self.connected = False
            self.connecting = False

    def connect(self, ssid, password):
        self.actions.append(("connect", ssid, password))
        self.connecting = True
        self.polls = 0

    def disconnect(self):
        self.actions.append(("disconnect",))
        self.connected = False
        self.connecting = False

    def config(self, **kwargs):
        self.actions.append(("config", kwargs))
        self.pm = kwargs.get("pm")

    def status(self):
        return -1


class FakeWatchdogMachine:
    PWRON_RESET = 1
    WDT_RESET = 3

    def __init__(self, reset_cause=3):
        self._reset_cause = reset_cause
        self.watchdogs = []

    def reset_cause(self):
        return self._reset_cause

    def WDT(self, timeout):
        watchdog = FakeWatchdog(timeout)
        self.watchdogs.append(watchdog)
        return watchdog


class FakeStartupUdp:
    def __init__(self):
        self.timeouts = []
        self.bind_address = None
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def bind(self, address):
        self.bind_address = address

    def close(self):
        self.closed = True


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
        conn = FakeConn()
        try:
            result = self.worker.run_worker_session(
                conn,
                FakeUdp(),
                "pico-led-test",
                8766,
                status_led=led,
                watchdog=FakeWatchdog(),
                reset_cause=3,
                reset_cause_name="WDT_RESET",
                watchdog_timeout_ms=8000,
            )
        finally:
            self.worker.protocol = original_protocol
            self.worker.core = original_core
            self.worker._ticks_ms = original_ticks_ms
            self.worker._ticks_diff = original_ticks_diff
            self.worker._mem_free = original_mem_free

        self.assertEqual(result["tiles_completed"], 1)
        self.assertEqual(conn.timeouts, [7])
        self.assertGreater(fake_protocol.sent[0]["watchdog_enabled"], 0)
        self.assertEqual(fake_protocol.sent[0]["reset_cause"], 3)
        self.assertEqual(fake_protocol.sent[0]["reset_cause_name"], "WDT_RESET")
        self.assertEqual(fake_protocol.sent[0]["watchdog_timeout_ms"], 8000)
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
        self.worker._run_once = (
            lambda _stall, _seconds, _led, **_kwargs: "completed"
        )
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

    def test_wifi_stagger_uses_node_number_and_validates_step(self):
        original_node_id = getattr(self.worker.config, "NODE_ID", None)
        self.worker.config.NODE_ID = "pico-16"
        self.worker.config.WIFI_STAGGER_STEP_MS = 200
        try:
            self.assertEqual(self.worker._wifi_stagger_delay_ms(), 3000)
            self.worker.config.NODE_ID = "unlabelled"
            self.assertEqual(self.worker._wifi_stagger_delay_ms(), 0)
            self.worker.config.WIFI_STAGGER_STEP_MS = 501
            with self.assertRaises(ValueError):
                self.worker._wifi_stagger_step_ms()
        finally:
            if original_node_id is None:
                del self.worker.config.NODE_ID
            else:
                self.worker.config.NODE_ID = original_node_id
            del self.worker.config.WIFI_STAGGER_STEP_MS

    def test_connect_wifi_resets_radio_staggers_and_disables_power_saving(self):
        wlan = FakeWlan(connect_after_polls=2)
        clock = FakeWifiTime()
        watchdog = FakeWatchdog()
        original_wlan = getattr(self.worker.network, "WLAN", None)
        original_time = self.worker.time
        original_values = {
            name: getattr(self.worker.config, name, None)
            for name in (
                "NODE_ID",
                "WIFI_SSID",
                "WIFI_PASSWORD",
                "WIFI_STAGGER_STEP_MS",
                "WIFI_RESET_DELAY_MS",
                "WIFI_POWER_MANAGEMENT",
            )
        }
        self.worker.network.WLAN = lambda _interface: wlan
        self.worker.time = clock
        self.worker.config.NODE_ID = "pico-04"
        self.worker.config.WIFI_SSID = "test-ssid"
        self.worker.config.WIFI_PASSWORD = "test-password"
        self.worker.config.WIFI_STAGGER_STEP_MS = 200
        self.worker.config.WIFI_RESET_DELAY_MS = 250
        self.worker.config.WIFI_POWER_MANAGEMENT = "none"
        try:
            result = self.worker.connect_wifi(
                timeout_seconds=2,
                watchdog=watchdog,
            )
        finally:
            if original_wlan is None:
                del self.worker.network.WLAN
            else:
                self.worker.network.WLAN = original_wlan
            self.worker.time = original_time
            for name, value in original_values.items():
                if value is None:
                    delattr(self.worker.config, name)
                else:
                    setattr(self.worker.config, name, value)

        self.assertIs(result, wlan)
        self.assertEqual(clock.sleeps[:3], [500, 100, 250])
        self.assertEqual(
            wlan.actions[:4],
            [
                ("disconnect",),
                ("active", False),
                ("active", True),
                ("config", {"pm": FakeWlan.PM_NONE}),
            ],
        )
        self.assertEqual(wlan.actions[4], ("connect", "test-ssid", "test-password"))
        self.assertGreater(watchdog.feed_count, 0)

    def test_connect_wifi_timeout_leaves_radio_inactive_for_clean_retry(self):
        wlan = FakeWlan(connect_after_polls=None)
        clock = FakeWifiTime()
        original_wlan = getattr(self.worker.network, "WLAN", None)
        original_time = self.worker.time
        original_values = {
            name: getattr(self.worker.config, name, None)
            for name in (
                "NODE_ID",
                "WIFI_SSID",
                "WIFI_PASSWORD",
                "WIFI_STAGGER_STEP_MS",
            )
        }
        self.worker.network.WLAN = lambda _interface: wlan
        self.worker.time = clock
        self.worker.config.NODE_ID = "pico-01"
        self.worker.config.WIFI_SSID = "test-ssid"
        self.worker.config.WIFI_PASSWORD = "test-password"
        self.worker.config.WIFI_STAGGER_STEP_MS = 0
        try:
            with self.assertRaisesRegex(RuntimeError, "status=-1"):
                self.worker.connect_wifi(timeout_seconds=0.2)
        finally:
            if original_wlan is None:
                del self.worker.network.WLAN
            else:
                self.worker.network.WLAN = original_wlan
            self.worker.time = original_time
            for name, value in original_values.items():
                if value is None:
                    delattr(self.worker.config, name)
                else:
                    setattr(self.worker.config, name, value)

        self.assertFalse(wlan.active_state)
        self.assertEqual(
            [action for action in wlan.actions if action == ("active", False)],
            [("active", False), ("active", False)],
        )

    def test_manager_timeout_resets_wifi_but_reachable_errors_do_not(self):
        watchdog = FakeWatchdog()
        timed_out = FakeWlan(connected=True)
        refused = FakeWlan(connected=True)
        reset_by_peer = FakeWlan(connected=True)
        clock = FakeWifiTime()
        original_time = self.worker.time
        original_errors = self.worker._consecutive_manager_connect_errors
        self.worker.time = clock
        self.worker._consecutive_manager_connect_errors = 0

        try:
            self.worker._reset_wifi_after_manager_connect_error(
                timed_out,
                OSError(110),
                watchdog,
            )
            self.worker._reset_wifi_after_manager_connect_error(
                refused,
                OSError(111),
                watchdog,
            )
            self.worker._reset_wifi_after_manager_connect_error(
                reset_by_peer,
                OSError(104),
                watchdog,
            )
        finally:
            self.worker.time = original_time
            self.worker._consecutive_manager_connect_errors = original_errors

        self.assertFalse(timed_out.active_state)
        self.assertEqual(refused.actions, [])
        self.assertEqual(reset_by_peer.actions, [])

    def test_repeated_manager_errors_eventually_reset_stale_wifi(self):
        wlan = FakeWlan(connected=True)
        clock = FakeWifiTime()
        watchdog = FakeWatchdog()
        original_time = self.worker.time
        original_errors = self.worker._consecutive_manager_connect_errors
        self.worker.time = clock
        self.worker._consecutive_manager_connect_errors = 0
        self.worker.config.MANAGER_ERRORS_BEFORE_WIFI_RESET = 3
        try:
            for _attempt in range(2):
                self.assertFalse(
                    self.worker._reset_wifi_after_manager_connect_error(
                        wlan, OSError(104), watchdog
                    )
                )
                self.assertTrue(wlan.active_state)
            self.assertTrue(
                self.worker._reset_wifi_after_manager_connect_error(
                    wlan, OSError(104), watchdog
                )
            )
        finally:
            self.worker.time = original_time
            self.worker._consecutive_manager_connect_errors = original_errors
            del self.worker.config.MANAGER_ERRORS_BEFORE_WIFI_RESET

        self.assertFalse(wlan.active_state)
        self.assertEqual(
            self.worker._consecutive_manager_connect_errors,
            original_errors,
        )

    def test_successful_manager_connection_clears_error_count(self):
        wlan = FakeWlan(connected=True)
        connection = object()
        original_connect = self.worker._connect_tcp
        original_errors = self.worker._consecutive_manager_connect_errors
        self.worker._connect_tcp = lambda *_args, **_kwargs: connection
        self.worker._consecutive_manager_connect_errors = 4
        try:
            self.assertIs(
                self.worker._connect_manager_tcp(wlan, "manager", 8765, 7),
                connection,
            )
            self.assertEqual(self.worker._consecutive_manager_connect_errors, 0)
        finally:
            self.worker._connect_tcp = original_connect
            self.worker._consecutive_manager_connect_errors = original_errors

    def test_manager_error_reset_threshold_is_bounded(self):
        self.assertEqual(self.worker._manager_errors_before_wifi_reset(), 8)
        for value in (0, 61, 8.0, True):
            self.worker.config.MANAGER_ERRORS_BEFORE_WIFI_RESET = value
            try:
                with self.assertRaises(ValueError):
                    self.worker._manager_errors_before_wifi_reset()
            finally:
                del self.worker.config.MANAGER_ERRORS_BEFORE_WIFI_RESET

    def test_socket_timeout_accepts_micropython_text_and_errno_forms(self):
        self.assertTrue(self.worker._is_socket_timeout(OSError("timed out")))
        self.assertTrue(self.worker._is_socket_timeout(OSError("ETIMEDOUT")))
        self.assertTrue(self.worker._is_socket_timeout(OSError(110)))
        self.assertTrue(self.worker._is_socket_timeout(OSError(-116)))
        self.assertFalse(self.worker._is_socket_timeout(OSError("network down")))

    def test_startup_timeout_has_safe_default_and_can_be_configured(self):
        self.assertEqual(self.worker._startup_timeout_seconds(), 90)
        self.worker.config.STARTUP_TIMEOUT_SECONDS = 120
        try:
            self.assertEqual(self.worker._startup_timeout_seconds(), 120)
        finally:
            del self.worker.config.STARTUP_TIMEOUT_SECONDS

    def test_connect_timeout_has_safe_default_and_can_be_configured(self):
        self.assertEqual(self.worker._connect_timeout_seconds(), 10)
        self.worker.config.CONNECT_TIMEOUT_SECONDS = 7
        try:
            self.assertEqual(self.worker._connect_timeout_seconds(), 7)
        finally:
            del self.worker.config.CONNECT_TIMEOUT_SECONDS

    def test_runtime_socket_timeout_has_safe_default_and_can_be_configured(self):
        self.assertEqual(self.worker._runtime_socket_timeout_seconds(), 7)
        self.worker.config.RUNTIME_SOCKET_TIMEOUT_SECONDS = 3
        try:
            self.assertEqual(self.worker._runtime_socket_timeout_seconds(), 3)
        finally:
            del self.worker.config.RUNTIME_SOCKET_TIMEOUT_SECONDS

    def test_watchdog_timeout_has_safe_default_and_rejects_unsafe_values(self):
        self.assertEqual(self.worker._watchdog_timeout_ms(), 8000)
        self.worker.config.WATCHDOG_TIMEOUT_MS = 7000
        try:
            self.assertEqual(self.worker._watchdog_timeout_ms(), 7000)
        finally:
            del self.worker.config.WATCHDOG_TIMEOUT_MS
        for value in (999, 8389, 8.0, True):
            self.worker.config.WATCHDOG_TIMEOUT_MS = value
            try:
                with self.assertRaises(ValueError):
                    self.worker._watchdog_timeout_ms()
            finally:
                del self.worker.config.WATCHDOG_TIMEOUT_MS

    def test_create_watchdog_records_prior_reset_cause(self):
        machine = FakeWatchdogMachine(reset_cause=3)
        watchdog, cause, cause_name, timeout = self.worker._create_watchdog(machine)
        self.assertIs(watchdog, machine.watchdogs[0])
        self.assertEqual(watchdog.timeout, 8000)
        self.assertEqual(watchdog.feed_count, 1)
        self.assertEqual((cause, cause_name, timeout), (3, "WDT_RESET", 8000))

    def test_run_once_separates_connect_and_startup_timeouts(self):
        udp = FakeStartupUdp()
        conn = FakeConn()
        conn.closed = False
        conn.close = lambda: setattr(conn, "closed", True)
        connect_calls = []
        original_socket = self.worker.socket.socket
        original_connect_wifi = self.worker.connect_wifi
        original_connect_tcp = self.worker._connect_tcp
        original_run_worker_session = self.worker.run_worker_session
        original_emit = self.worker._emit
        self.worker.config.MANAGER_HOST = "192.0.2.10"
        self.worker.config.MANAGER_PORT = 8765
        self.worker.config.UDP_PORT = 8766
        self.worker.config.NODE_ID = "pico-test"
        self.worker.socket.socket = lambda *_args: udp
        self.worker.connect_wifi = lambda **_kwargs: types.SimpleNamespace(
            ifconfig=lambda: ("192.0.2.20", "255.255.255.0", "192.0.2.1", "192.0.2.1")
        )
        self.worker._connect_tcp = (
            lambda host, port, timeout, watchdog=None: (
                connect_calls.append((host, port, timeout)) or conn
            )
        )
        self.worker.run_worker_session = lambda *_args, **_kwargs: {
            "job_id": "timeout-test"
        }
        self.worker._emit = lambda *_args: None
        try:
            result = self.worker._run_once(None, 0, None)
        finally:
            self.worker.socket.socket = original_socket
            self.worker.connect_wifi = original_connect_wifi
            self.worker._connect_tcp = original_connect_tcp
            self.worker.run_worker_session = original_run_worker_session
            self.worker._emit = original_emit

        self.assertEqual(result, {"job_id": "timeout-test"})
        self.assertEqual(udp.timeouts, [90])
        self.assertEqual(udp.bind_address, ("0.0.0.0", 8766))
        self.assertTrue(udp.closed)
        self.assertTrue(conn.closed)
        self.assertEqual(connect_calls, [("192.0.2.10", 8765, 10)])


if __name__ == "__main__":
    unittest.main()
