"""設定は一時ディレクトリ、監視対象は試験用プロセスのみで検証する。"""

from contextlib import contextmanager, redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load("dual_launcher", "start-dual-display-kiosk.py")
installer = load("dual_installer", "install-dual-display-kiosk.py")


def args_for(*extra):
    return launcher.parse_args(["--vehicle-url", "http://192.0.2.1:30096/", "--browser", sys.executable, *extra])


class KioskTests(unittest.TestCase):
    def test_independent_profiles_and_legacy_aliases(self):
        modern = args_for("--vehicle-position=-1920,0")
        legacy = launcher.parse_args(["--traffic-url", "http://192.0.2.1:30096/", "--browser", sys.executable,
                                      "--traffic-position=-1920,0"])
        self.assertEqual(launcher.commands(modern), launcher.commands(legacy))
        commands = launcher.commands(modern)
        self.assertIn("--window-position=-1920,0", commands["vehicle"])
        self.assertIn("--window-position=0,1080", commands["pico"])
        profiles = [next(arg for arg in command if arg.startswith("--user-data-dir=")) for command in commands.values()]
        self.assertNotEqual(*profiles)
        self.assertTrue(profiles[0].endswith("/traffic"))
        self.assertIn("--class=cluster-traffic-kiosk", commands["vehicle"])
        self.assertIn("--kiosk", commands["vehicle"])
        self.assertNotIn("--no-sandbox", commands["vehicle"])

    def test_labwc_commands_and_invalid_inputs(self):
        args = args_for("--vehicle-output", "HDMI-A-2", "--pico-output", "HDMI-A-1")
        command = launcher.commands(args)["vehicle"]
        self.assertIn("--ozone-platform=x11", command)
        self.assertNotIn("--kiosk", command)
        for extra in (("--vehicle-output", "HDMI-A-2"),
                      ("--vehicle-output", "HDMI-A-1", "--pico-output", "HDMI-A-1"),
                      ("--window-size", "0,1080"), ("--pico-url", "file:///tmp/x"),
                      ("--pico-url", "http://user:secret@localhost/"),
                      ("--pico-url", "http://localhost:bad/"),
                      ("--pico-url", "http://localhost/\nName=bad"),
                      ("--vehicle-output", "HDMI-A-2", "--pico-output", "HDMI-A-1",
                       "--pico-url", "http://192.0.2.1:8080/"),
                      ("--vehicle-output", "HDMI-A-2", "--pico-output", "HDMI-A-1",
                       "--pico-url", "http://localhost/subpath")):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                args_for(*extra)

    def test_desktop_exec_escaping(self):
        self.assertEqual(installer.exec_quote("/tmp/path with spaces"), '"/tmp/path with spaces"')
        self.assertEqual(installer.exec_quote("http://localhost/a%20b"), '"http://localhost/a%%20b"')
        self.assertEqual(installer.exec_quote("a\\b"), '"a' + "\\" * 4 + 'b"')
        for value in ('"', '`', '$'):
            self.assertEqual(installer.exec_quote(value), '"' + "\\" * 2 + value + '"')
        with self.assertRaises(ValueError):
            installer.exec_quote("path\nTerminal=true")

    def test_labwc_preserves_namespace_rules_comments_and_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / "labwc").mkdir()
            xml = '<labwc_config xmlns="urn:labwc"><keyboard><keybind key="A-F4"/></keyboard><!--keep--><windowRules><windowRule identifier="other"/></windowRules></labwc_config>'
            rc = config / "labwc/rc.xml"
            rc.write_text(xml)
            for _ in range(2):
                installer.configure_labwc(config, "HDMI-A-2", "HDMI-A-1", "192.0.2.1", "127.0.0.1")
            root = installer.ET.parse(rc).getroot()
            ns = {"l": "urn:labwc"}
            self.assertIsNotNone(root.find("l:keyboard/l:keybind", ns))
            self.assertEqual(len(root.findall("l:windowRules/l:windowRule", ns)), 3)
            rule = root.find("l:windowRules/l:windowRule[@identifier='192.0.2.1']", ns)
            self.assertEqual([action.get("name") for action in rule], ["MoveToOutput", "ToggleFullscreen"])
            self.assertEqual(rule[0].get("output"), "HDMI-A-2")
            self.assertIn("<!--keep-->", rc.read_text())
            backups = list((config / "cluster-dual-kiosk-backups").glob("labwc-*.xml"))
            self.assertEqual(len(backups), 2)
            self.assertIn(xml, [p.read_text() for p in backups])

    def test_malformed_management_markers_do_not_overwrite_settings(self):
        for markers in ("<!--cluster-dual-kiosk:start-->", "<!--cluster-dual-kiosk:end-->"):
            with self.subTest(markers=markers), tempfile.TemporaryDirectory() as directory:
                config = Path(directory)
                (config / "labwc").mkdir()
                rc = config / "labwc/rc.xml"
                original = '<labwc_config><windowRules>' + markers + '<windowRule identifier="other"/></windowRules></labwc_config>'
                rc.write_text(original)
                with self.assertRaises(ValueError):
                    installer.configure_labwc(config, "HDMI-A-2", "HDMI-A-1", "192.0.2.1", "127.0.0.1")
                self.assertEqual(rc.read_text(), original)

    def install(self, config, *extra):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "LABWC_PID": "123"}), \
                patch.object(installer.os, "geteuid", return_value=1000), \
                patch("sys.argv", ["installer", "--vehicle-url", "http://192.0.2.1:30096/", "--browser", sys.executable, *extra]), \
                redirect_stdout(io.StringIO()):
            installer.main()

    def test_reinstall_backs_up_previous_dual_and_single_autostart(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            autostart = config / "autostart"
            autostart.mkdir()
            legacy = autostart / "pico-raytracing-kiosk.desktop"
            legacy.write_text("original single")
            desktop = autostart / "cluster-dual-kiosk.desktop"
            desktop.write_text("original dual")
            self.install(config)
            installed = desktop.read_text()
            self.assertIn("--vehicle-url", installed)
            self.install(config)
            self.assertEqual(desktop.read_text(), installed)
            contents = [p.read_text() for p in (config / "cluster-dual-kiosk-backups").glob("*.desktop")]
            self.assertCountEqual(contents, ["original single", "original dual", installed])
            self.assertFalse(legacy.exists())

    def test_generated_desktop_supports_negative_positions_on_python313(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            self.install(config, "--vehicle-position=-1920,0", "--pico-position=0,-1080")
            desktop = (config / "autostart/cluster-dual-kiosk.desktop").read_text()
            self.assertIn('"--vehicle-position=-1920,0"', desktop)
            self.assertIn('"--pico-position=0,-1080"', desktop)

    def test_dry_run_does_not_modify_config_or_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.install(root / "config", "--profile-dir", str(root / "profile"), "--dry-run")
            self.assertEqual(list(root.iterdir()), [])

    def test_labwc_reload_failure_restores_config_and_keeps_autostart(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / "labwc").mkdir()
            rc = config / "labwc/rc.xml"
            rc.write_text("<labwc_config><keyboard/></labwc_config>")
            original = rc.read_bytes()
            with patch.object(installer.shutil, "which", return_value="/test/labwc"), \
                    patch.object(installer.subprocess, "run", side_effect=subprocess.TimeoutExpired("labwc", 5)), \
                    self.assertRaises(SystemExit):
                self.install(config, "--vehicle-output", "HDMI-A-2", "--pico-output", "HDMI-A-1")
            self.assertEqual(rc.read_bytes(), original)
            self.assertFalse((config / "autostart").exists())

    def test_launch_failure_backs_off_and_other_screen_runs(self):
        clock, events = [0], []
        fake = unittest.mock.Mock()
        fake.pid = 999
        fake.poll.return_value = None

        def popen(command):
            events.append((command[0], clock[0]))
            if command[0] == "missing":
                raise FileNotFoundError("test missing executable")
            return fake

        def tick(_):
            clock[0] += 1

        with patch.object(launcher.subprocess, "Popen", side_effect=popen), \
                patch.object(launcher.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(launcher.time, "sleep", side_effect=tick):
            launcher.supervise({"vehicle": ["missing"], "pico": ["ok"]}, lambda: clock[0] >= 7,
                               unittest.mock.Mock())
        self.assertEqual(events, [("missing", 0), ("ok", 0), ("missing", 5)])
        fake.terminate.assert_called_once()
        fake.wait.assert_called_once_with(timeout=5)

    def test_unresponsive_child_is_killed_on_shutdown(self):
        child = unittest.mock.Mock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired("fake", 5), 0]
        stopped = [False]

        def tick(_):
            stopped[0] = True

        with patch.object(launcher.subprocess, "Popen", return_value=child), \
                patch.object(launcher.time, "sleep", side_effect=tick):
            launcher.supervise({"vehicle": ["fake"]}, lambda: stopped[0], unittest.mock.Mock())
        child.terminate.assert_called_once()
        child.kill.assert_called_once()
        self.assertEqual(child.wait.call_count, 2)

    def test_live_process_restart_duplicate_lock_and_graceful_stop(self):
        # 専用fakeだけを起動・終了する。実Chromium、DISPLAY、ユーザー設定は使わない。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.jsonl"
            browser = root / "fake-browser"
            browser.write_text("#!" + sys.executable + '\n' +
                               'import json, os, sys, time\n' +
                               'with open(os.environ["KIOSK_EVENTS"], "a") as f:\n' +
                               ' f.write(json.dumps({"pid":os.getpid(),"args":sys.argv[1:],"at":time.monotonic()}) + "\\n")\n' +
                               'while True: time.sleep(1)\n')
            browser.chmod(0o755)
            command = [sys.executable, "-B", str(HERE / "start-dual-display-kiosk.py"),
                       "--vehicle-url", "http://192.0.2.1:30096/", "--browser", str(browser),
                       "--profile-dir", str(root / "profiles"), "--no-http-recovery"]
            env = {**os.environ, "DISPLAY": ":test-only", "PATH": str(root), "KIOSK_EVENTS": str(events)}
            process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            child_pids = set()
            graceful_exit = False

            def read_events():
                data = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
                child_pids.update(item["pid"] for item in data)
                return data

            def wait_for(count, seconds):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    data = read_events()
                    if len(data) >= count:
                        return data
                    time.sleep(0.05)
                self.fail("fake browser起動が期限内に完了しませんでした")

            try:
                initial = wait_for(2, 5)
                duplicate = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
                self.assertNotEqual(duplicate.returncode, 0)
                self.assertIn("既に起動", duplicate.stderr)
                upper = next(item for item in initial if "--class=cluster-traffic-kiosk" in item["args"])
                lower = next(item for item in initial if "--class=cluster-pico-kiosk" in item["args"])
                closed_at = time.monotonic()
                os.kill(upper["pid"], signal.SIGTERM)
                after = wait_for(3, 9)
                self.assertEqual(len(after), 3)
                self.assertIn("--class=cluster-traffic-kiosk", after[-1]["args"])
                self.assertGreaterEqual(after[-1]["at"] - closed_at, 4.9)
                os.kill(lower["pid"], 0)  # 下段は同じプロセスのまま。
                process.terminate()
                _, stderr = process.communicate(timeout=8)
                self.assertEqual(process.returncode, 0, stderr)
                graceful_exit = True
                self.assertIn("終了しました", (root / "profiles/launcher.log").read_text())
                for pid in (lower["pid"], after[-1]["pid"]):
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=8)
                read_events()
                for pid in (() if graceful_exit else child_pids):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass



@contextmanager
def http_server():
    config = dict(code=200, wait=None, calls=[])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            config["calls"].append((time.monotonic(), config["code"]))
            if config["wait"]:
                config["wait"].wait(5)
            self.send_response(config["code"])
            if config["code"] == 302:
                self.send_header("Location", "/redirect-target")
            self.end_headers()
            try:
                self.wfile.write(b"ok")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02), daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d/" % server.server_port, config
    finally:
        if config["wait"]:
            config["wait"].set()
        server.shutdown()
        server.server_close()
        thread.join(2)


class HttpRecoveryTests(unittest.TestCase):
    def wait_until(self, check, seconds=5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if check():
                return
            time.sleep(.025)
        self.fail("HTTP復旧の条件が期限内に成立しませんでした")

    def test_initial_success_does_not_reload_and_failure_latches_until_two_successes(self):
        recovery = launcher.HttpRecovery({"vehicle": "http://localhost/"}, unittest.mock.Mock())
        for _ in range(4):
            self.assertFalse(recovery.result("vehicle", True))
        for _ in range(4):
            self.assertFalse(recovery.result("vehicle", False))
        self.assertFalse(recovery.result("vehicle", True))
        self.assertFalse(recovery.result("vehicle", False))
        self.assertFalse(recovery.result("vehicle", True))
        self.assertTrue(recovery.result("vehicle", True))
        for _ in range(4):
            self.assertFalse(recovery.result("vehicle", True))
        self.assertTrue(recovery.checked("vehicle"))

    def test_get_status_redirect_tls_and_connection_failure(self):
        with http_server() as (url, state):
            for code in (200, 204, 302, 404, 503):
                state["code"] = code
                before = len(state["calls"])
                self.assertEqual(launcher.probe_http(url), 0 if code < 300 else 1)
                self.assertEqual(len(state["calls"]), before + 1)  # redirectを追わない。
            self.assertEqual(launcher.probe_http(url.replace("http:", "https:")), 1)
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))  # bindのみ、listenしないので確実に接続拒否。
            self.assertEqual(launcher.probe_http("http://127.0.0.1:%d/" % reserved.getsockname()[1]), 1)
        for url in ("file:///tmp/x", "http://user:pass@localhost/", "http://localhost:bad/"):
            self.assertEqual(launcher.probe_http(url), 1)

    def test_probe_deadline_does_not_block_other_screen_and_close_reaps_children(self):
        with http_server() as (slow, slow_state), http_server() as (fast, _):
            slow_state["wait"] = threading.Event()
            recovery = launcher.HttpRecovery({"vehicle": slow, "pico": fast}, unittest.mock.Mock(),
                                             interval=.15, timeout=.45)
            started = time.monotonic()
            try:
                recovery.poll()
                processes = [s["process"] for s in recovery.states.values()]
                def checked():
                    recovery.poll()
                    return recovery.checked("vehicle") and recovery.checked("pico")
                self.wait_until(checked, 3)
                self.assertLess(time.monotonic() - started, 2)
                self.assertFalse(recovery.states["vehicle"]["last_ok"])
                self.assertTrue(recovery.states["vehicle"]["pending"])
                self.assertTrue(recovery.states["pico"]["last_ok"])
                self.assertFalse(recovery.states["pico"]["pending"])
            finally:
                recovery.close()
            self.assertTrue(all(p.poll() is not None for p in processes))
            self.assertTrue(all(s["process"] is None for s in recovery.states.values()))

    def test_dns_or_other_stuck_probe_has_parent_deadline(self):
        child = unittest.mock.Mock()
        child.poll.return_value = None
        recovery = launcher.HttpRecovery({"vehicle": "http://example.invalid/"}, unittest.mock.Mock())
        with patch.object(launcher.subprocess, "Popen", return_value=child), \
                patch.object(launcher.time, "monotonic", return_value=0):
            recovery.poll()
        with patch.object(launcher.time, "monotonic", return_value=3.1):
            self.assertEqual(recovery.poll(), [])
        child.kill.assert_called_once()
        child.wait.assert_called_once_with(timeout=1)
        self.assertFalse(recovery.states["vehicle"]["last_ok"])

    def test_probe_spawn_failure_backs_off(self):
        recovery = launcher.HttpRecovery({"vehicle": "http://localhost/"}, unittest.mock.Mock())
        with patch.object(launcher.subprocess, "Popen", side_effect=OSError("unavailable")) as popen, \
                patch.object(launcher.time, "monotonic", return_value=0):
            recovery.poll()
            recovery.poll()
        self.assertEqual(popen.call_count, 1)
        self.assertTrue(recovery.checked("vehicle"))
        self.assertTrue(recovery.states["vehicle"]["pending"])
        self.assertEqual(recovery.states["vehicle"]["next_at"], 5)

    def test_opt_out_survives_installer_and_is_not_passed_to_chromium(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            KioskTests().install(config, "--no-http-recovery")
            desktop = (config / "autostart/cluster-dual-kiosk.desktop").read_text()
            self.assertIn('"--no-http-recovery"', desktop)
        self.assertNotIn("--no-http-recovery", launcher.commands(args_for("--no-http-recovery"))["vehicle"])

    def test_real_http_and_browser_processes_recover_startup_and_runtime_only_once(self):
        with tempfile.TemporaryDirectory() as directory, http_server() as (upper, up), http_server() as (lower, _):
            root = Path(directory)
            events = root / "events.jsonl"
            browser = root / "browser.py"
            browser.write_text('import json,os,sys,time\n'
                               'with open(sys.argv[2],"a") as f:\n'
                               ' f.write(json.dumps({"role":sys.argv[1],"pid":os.getpid()})+"\\n")\n'
                               'while True: time.sleep(1)\n')
            commands = {role: [sys.executable, str(browser), role, str(events)] for role in ("vehicle", "pico")}
            up["code"] = 503
            recovery = launcher.HttpRecovery({"vehicle": upper, "pico": lower}, unittest.mock.Mock(),
                                             interval=.15, timeout=1)
            stopping = threading.Event()
            errors = []
            def run():
                try:
                    launcher.supervise(commands, stopping.is_set, unittest.mock.Mock(), recovery)
                except BaseException as exc:
                    errors.append(exc)
            thread = threading.Thread(target=run, daemon=True)
            def read():
                return [json.loads(l) for l in events.read_text().splitlines()] if events.exists() else []
            thread.start()
            try:
                self.wait_until(lambda: len(read()) == 2)
                first = read()
                lower_pid = next(r["pid"] for r in first if r["role"] == "pico")
                self.wait_until(lambda: len(up["calls"]) >= 3)
                self.assertEqual(len(read()), 2)  # 不通のまま再起動しない。
                up["code"] = 200
                self.wait_until(lambda: len(read()) == 3)
                self.assertEqual(read()[-1]["role"], "vehicle")
                up["code"] = 503
                self.wait_until(lambda: recovery.states["vehicle"]["pending"])
                self.assertEqual(len(read()), 3)
                up["code"] = 200
                self.wait_until(lambda: len(read()) == 4)
                self.assertEqual(read()[-1]["role"], "vehicle")
                calls = len(up["calls"])
                self.wait_until(lambda: len(up["calls"]) >= calls + 3)
                self.assertEqual(len(read()), 4)  # 正常時にも繰り返さない。
                os.kill(lower_pid, 0)
            finally:
                stopping.set()
                thread.join(9)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            for row in read():
                with self.assertRaises(ProcessLookupError):
                    os.kill(row["pid"], 0)


if __name__ == "__main__":
    unittest.main()
