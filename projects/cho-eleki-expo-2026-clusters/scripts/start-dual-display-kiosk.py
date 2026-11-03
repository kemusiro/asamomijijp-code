#!/usr/bin/env python3
"""Pi 5の車体進化・Pico用Chromiumを起動し、終了・配信元復旧時に該当画面だけを再表示する。"""

import argparse
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vehicle-url", "--traffic-url", dest="vehicle_url", required=True)
    parser.add_argument("--pico-url", default="http://127.0.0.1:8080/")
    parser.add_argument("--vehicle-position", "--traffic-position", dest="vehicle_position", default="0,0")
    parser.add_argument("--pico-position", default="0,1080")
    parser.add_argument("--window-size", default="1920,1080")
    parser.add_argument("--browser")
    parser.add_argument("--vehicle-output", "--traffic-output", dest="vehicle_output",
                        help="labwcで上段に使う出力名（wlr-randrで確認）")
    parser.add_argument("--pico-output", help="labwcで下段に使う出力名")
    parser.add_argument("--profile-dir", type=Path,
                        default=Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "cluster-dual-kiosk")
    parser.add_argument("--no-http-recovery", action="store_true",
                        help="配信元のHTTP監視・復旧後の再表示を無効化する（終了監視は継続）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for value in (args.vehicle_url, args.pico_url):
        try:
            url = urlsplit(value)
            valid = (url.scheme in ("http", "https") and url.hostname and
                     not url.username and not url.password and url.port != 0)
        except ValueError:
            valid = False
        if not valid or any(ord(char) < 32 or ord(char) == 127 for char in value):
            parser.error("表示URLは認証情報を含まないhttpまたはhttpsの絶対URLにしてください")
    for value in (args.vehicle_position, args.pico_position):
        if not re.fullmatch(r"-?\d+,-?\d+", value):
            parser.error("画面位置はX,Yで指定してください（例：0,1080）")
    if not re.fullmatch(r"[1-9]\d*,[1-9]\d*", args.window_size):
        parser.error("画面サイズは幅,高さで指定してください")
    if bool(args.vehicle_output) != bool(args.pico_output):
        parser.error("labwcの出力名は2画面とも指定してください")
    if args.vehicle_output:
        outputs = (args.vehicle_output, args.pico_output)
        if outputs[0] == outputs[1] or any(not re.fullmatch(r"[a-zA-Z0-9_.-]+", value) for value in outputs):
            parser.error("labwcには異なる2つの出力名を指定してください")
        urls = [urlsplit(value) for value in (args.vehicle_url, args.pico_url)]
        if urls[0].hostname == urls[1].hostname or any(url.path not in ("", "/") for url in urls):
            parser.error("labwcの専用app配置には、異なるホスト名のルートURLを使用してください")
    args.browser = args.browser or next((shutil.which(name) for name in
                                        ("chromium", "chromium-browser", "google-chrome") if shutil.which(name)), None)
    if not args.browser:
        parser.error("Chromiumが見つかりません。--browserで実行ファイルを指定してください")
    return args


def commands(args):
    common = [args.browser, "--ozone-platform=x11", "--no-first-run", "--noerrdialogs",
              "--disable-session-crashed-bubble", "--disable-extensions",
              "--disable-features=Translate,TranslateUI", "--lang=ja", "--password-store=basic",
              "--window-size=" + args.window_size]
    if not args.vehicle_output:
        common.append("--kiosk")
    # 旧#113のプロファイルとWM_CLASSを維持し、更新時の重複起動を避ける。
    screens = (("vehicle", "traffic", args.vehicle_position, args.vehicle_url),
               ("pico", "pico", args.pico_position, args.pico_url))
    return {role: common + ["--class=cluster-" + profile + "-kiosk",
                            "--user-data-dir=" + str(args.profile_dir.resolve() / profile),
                            "--window-position=" + position, "--app=" + url]
            for role, profile, position, url in screens}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_http(url):
    """別process専用。GETの2xxだけを成功とし、本文・エラーをログへ流さない。"""
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or
                parsed.username or parsed.password or parsed.port == 0):
            return 1
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with opener.open(request, timeout=2) as response:
            response.read(1)
            return 0 if 200 <= response.status < 300 else 1
    except urllib.error.HTTPError as exc:
        exc.close()
        return 1
    except (OSError, ValueError, urllib.error.URLError):
        return 1


class HttpRecovery:
    """画面ごとのprobeを並行実行。DNS/応答遅延も親のmonotonic期限で打ち切る。"""
    def __init__(self, urls, logger, interval=5, timeout=3):
        self.urls, self.logger = urls, logger
        self.interval, self.timeout = interval, timeout
        self.states = {role: dict(process=None, next_at=0, started=0, checked=False,
                                  last_ok=None, successes=0, pending=False)
                       for role in urls}

    def checked(self, role):
        return self.states[role]["checked"]

    def result(self, role, ok):
        state = self.states[role]
        state["checked"] = True
        if not ok:
            if state["last_ok"] is not False:
                self.logger.warning("%sのHTTP応答を確認できません。ブラウザは維持して復旧を待ちます。", role)
            state["pending"], state["successes"] = True, 0
        else:
            state["successes"] = min(2, state["successes"] + 1)
            if state["last_ok"] is False:
                self.logger.info("%sのHTTP応答が戻りました。2回連続の成功を確認します。", role)
        state["last_ok"] = ok
        if state["pending"] and state["successes"] >= 2:
            state["pending"] = False
            return True
        return False

    def poll(self):
        recovered = []
        for role, state in self.states.items():
            now = time.monotonic()
            process = state["process"]
            if process is not None:
                code = process.poll()
                if code is None:
                    if now - state["started"] < self.timeout:
                        continue
                    process.kill()
                    process.wait(timeout=1)
                    code = -1
                state["process"] = None
                if self.result(role, code == 0):
                    recovered.append(role)
            if state["process"] is None and now >= state["next_at"]:
                state["started"], state["next_at"] = now, now + self.interval
                try:
                    state["process"] = subprocess.Popen(
                        [sys.executable, "-B", str(Path(__file__).resolve()), "--probe-http", self.urls[role]],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    self.result(role, False)
        return recovered

    def close(self):
        for state in self.states.values():
            process = state["process"]
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=1)
                state["process"] = None


def stop_browser(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def supervise(launch, stopping, logger, recovery=None):
    children, retry_at = {}, {role: 0 for role in launch}
    try:
        while not stopping():
            recovered = recovery.poll() if recovery else []
            for role in recovered:
                process = children.pop(role, None)
                if process is not None:
                    stop_browser(process)
                retry_at[role] = 0
                logger.info("%sのHTTP復旧を確認しました。この画面だけを再表示します。", role)
            for role, command in launch.items():
                if recovery and not recovery.checked(role):
                    continue
                process = children.get(role)
                if process is not None and process.poll() is not None:
                    logger.warning("%sのブラウザが終了しました。5秒後に再起動します。", role)
                    children.pop(role)
                    retry_at[role] = time.monotonic() + 5
                if role not in children and time.monotonic() >= retry_at[role]:
                    try:
                        children[role] = subprocess.Popen(command)
                        logger.info("%sのブラウザを起動しました（PID %s）。", role, children[role].pid)
                    except OSError as exc:
                        logger.error("%sを起動できません。実行パスを確認してください: %s", role, exc)
                        retry_at[role] = time.monotonic() + 5
            time.sleep(0.25)
    finally:
        if recovery:
            recovery.close()
        for process in children.values():
            if process.poll() is None:
                process.terminate()
        for process in children.values():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        logger.info("2画面ランチャーを終了しました。計算サービスは継続します。")


def main():
    args = parse_args()
    launch = commands(args)
    if args.dry_run:
        print(json.dumps(launch, ensure_ascii=False, indent=2))
        return
    if not os.environ.get("DISPLAY"):
        raise SystemExit("DISPLAYがありません。Pi 5のデスクトップ端末で実行してください。WaylandではXwaylandが必要です。")
    args.profile_dir.mkdir(parents=True, exist_ok=True)
    lock = (args.profile_dir / "launcher.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("同じプロファイルの2画面ランチャーが既に起動しています。")
    with lock:
        logger = logging.getLogger("dual-kiosk")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for handler in (logging.StreamHandler(), RotatingFileHandler(
                args.profile_dir / "launcher.log", maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        if shutil.which("xset"):
            for setting in (["s", "off"], ["s", "noblank"], ["-dpms"]):
                try:
                    result = subprocess.run(["xset", *setting], check=False, timeout=5, capture_output=True)
                    if result.returncode:
                        logger.warning("画面の省電力設定はデスクトップで確認してください（xset失敗）。")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    logger.warning("画面の省電力設定を確認してください: %s", exc)
        stopped = False

        def stop(_signal, _frame):
            nonlocal stopped
            stopped = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        recovery = None if args.no_http_recovery else HttpRecovery(
            {"vehicle": args.vehicle_url, "pico": args.pico_url}, logger)
        logger.info("HTTP復旧監視: %s", "無効" if recovery is None else "5秒間隔・期限3秒・2回連続成功で再表示")
        supervise(launch, lambda: stopped, logger, recovery)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe-http":
        raise SystemExit(probe_http(sys.argv[2]))
    main()
