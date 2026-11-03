import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[4]
SERVER_SCRIPT = REPO_ROOT / "scripts" / "serve-pico-raytracing-display.py"
RUNNER_SCRIPT = REPO_ROOT / "scripts" / "run-pico-raytracing-exhibition.py"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DisplayStateStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = load_script("pico_display_server", SERVER_SCRIPT)
        cls.runner = load_script("pico_display_runner", RUNNER_SCRIPT)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_dir = Path(self.temporary.name)
        self.state_path = self.output_dir / "display-state.json"

    def test_missing_state_returns_starting_screen(self):
        store = self.server.DisplayStateStore(self.state_path, self.output_dir)
        self.assertEqual(store.read()["mode"], "starting")

    def test_result_image_is_exposed_without_local_path(self):
        image = self.output_dir / "completed.png"
        image.write_bytes(b"png")
        self.state_path.write_text(
            json.dumps(
                {
                    "mode": "result",
                    "live_image": "live-progress.png",
                    "held_result": {
                        "job_id": "test-1",
                        "output_path": str(image),
                    },
                }
            ),
            encoding="utf-8",
        )
        state = self.server.DisplayStateStore(
            self.state_path, self.output_dir
        ).read()
        self.assertEqual(state["result_image_url"], "/api/image/completed.png")
        self.assertNotIn("output_path", state["held_result"])

    def test_image_outside_output_directory_is_rejected(self):
        outside = self.output_dir.parent / "outside.png"
        self.state_path.write_text(
            json.dumps(
                {"mode": "result", "held_result": {"output_path": str(outside)}}
            ),
            encoding="utf-8",
        )
        state = self.server.DisplayStateStore(
            self.state_path, self.output_dir
        ).read()
        self.assertIsNone(state["result_image_url"])

    def test_publisher_writes_partial_png_and_progress(self):
        publisher = self.runner.DisplayPublisher(
            self.state_path,
            self.output_dir / "live-progress.png",
            expected_workers=16,
        )
        publisher.start_cycle(1, "test-cycle")
        publisher.on_progress(
            {
                "type": "job_started",
                "job_id": "test-cycle",
                "node_ids": ["pico-01"],
                "total_tiles": 1,
            },
            types.SimpleNamespace(
                image=bytearray([1, 2, 3]),
                job={"width": 1, "height": 1},
            ),
        )
        publisher.on_progress(
            {
                "type": "tile_accepted",
                "job_id": "test-cycle",
                "node_id": "pico-01",
                "tile": {"tile_id": 0, "x0": 0, "y0": 0, "width": 1, "height": 1},
                "completed_tiles": 1,
                "total_tiles": 1,
                "worker_tiles": {"pico-01": 1},
            },
            types.SimpleNamespace(
                image=bytearray([1, 2, 3]),
                job={"width": 1, "height": 1},
            ),
        )
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["mode"], "rendering")
        self.assertEqual(state["completed_tiles"], 1)
        self.assertEqual(state["tiles"][0]["node_id"], "pico-01")
        self.assertTrue((self.output_dir / "live-progress.png").read_bytes().startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
