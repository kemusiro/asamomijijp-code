#!/usr/bin/env python3
"""Serve the Pico ray-tracing visitor display without external dependencies."""

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_DIR = (
    REPO_ROOT / "projects/raspberry-pi-pico-cluster/raytracing/display"
)


class DisplayStateStore:
    def __init__(self, state_path, output_dir):
        self.state_path = Path(state_path).resolve()
        self.output_dir = Path(output_dir).resolve()

    def _image_url(self, raw_path):
        if not raw_path:
            return None
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.output_dir / candidate
        candidate = candidate.resolve()
        try:
            relative = candidate.relative_to(self.output_dir)
        except ValueError:
            return None
        if candidate.suffix.lower() != ".png" or len(relative.parts) != 1:
            return None
        return "/api/image/" + relative.name

    def read(self):
        if not self.state_path.exists():
            return {
                "schema_version": 1,
                "demo": "pico-raytracing",
                "mode": "starting",
                "message": "展示プログラムの起動を待っています",
            }
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {
                "schema_version": 1,
                "demo": "pico-raytracing",
                "mode": "display_error",
                "message": "表示状態を読み取れません",
                "error": type(exc).__name__,
            }
        live_image = state.pop("live_image", "live-progress.png")
        state["live_image_url"] = self._image_url(live_image)
        held_result = state.get("held_result")
        if isinstance(held_result, dict):
            held_result = dict(held_result)
            result_url = self._image_url(held_result.pop("output_path", None))
            state["held_result"] = held_result
            state["result_image_url"] = result_url
        return state

    def image_path(self, name):
        if Path(name).name != name or not name.lower().endswith(".png"):
            return None
        candidate = (self.output_dir / name).resolve()
        try:
            candidate.relative_to(self.output_dir)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None


def make_handler(asset_dir, store):
    asset_dir = Path(asset_dir).resolve()

    class DisplayHandler(SimpleHTTPRequestHandler):
        server_version = "PicoDisplay/1"

        def log_message(self, _format_string, *_args):
            # The kiosk polls four times per second; keep the journal bounded.
            pass

        def _headers(self, status, content_type, length):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'",
            )
            self.end_headers()

        def _send_bytes(self, payload, content_type, status=200):
            self._headers(status, content_type, len(payload))
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _send_json(self, record, status=200):
            payload = (
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            self._send_bytes(payload, "application/json; charset=utf-8", status)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/health":
                self._send_json({"ok": True})
                return
            if path == "/api/state":
                self._send_json(store.read())
                return
            if path.startswith("/api/image/"):
                image_path = store.image_path(path.removeprefix("/api/image/"))
                if image_path is None:
                    self._send_json({"error": "image not found"}, 404)
                    return
                try:
                    payload = image_path.read_bytes()
                except OSError:
                    self._send_json({"error": "image unavailable"}, 503)
                    return
                self._send_bytes(payload, "image/png")
                return

            relative = "index.html" if path == "/" else path.lstrip("/")
            if "/" in relative or relative not in {
                "index.html",
                "display.css",
                "display.mjs",
                "display-state.mjs",
            }:
                self._send_json({"error": "not found"}, 404)
                return
            target = asset_dir / relative
            try:
                payload = target.read_bytes()
            except OSError:
                self._send_json({"error": "asset unavailable"}, 503)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".mjs":
                content_type = "text/javascript"
            self._send_bytes(payload, content_type + "; charset=utf-8")

    return DisplayHandler


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSET_DIR)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.state is None:
        args.state = args.output_dir / "display-state.json"
    return args


def main():
    args = parse_args()
    if not (args.assets / "index.html").is_file():
        raise SystemExit("display assets are missing: " + str(args.assets))
    store = DisplayStateStore(args.state, args.output_dir)
    server = ThreadingHTTPServer(
        (args.host, args.port), make_handler(args.assets, store)
    )
    print("DISPLAY_READY http://%s:%d/" % server.server_address, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
