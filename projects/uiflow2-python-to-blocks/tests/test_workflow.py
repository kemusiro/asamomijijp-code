import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from best_effort import BestEffortError
from workflow import artifact_paths, build_once, copy_path


SOURCE = '''\
import time
def setup():
    pass
def loop():
    if enabled:
        time.sleep(1)
'''


class WorkflowTests(unittest.TestCase):
    def test_build_writes_complete_handoff_and_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'main.py'
            source.write_text(SOURCE, encoding='utf-8')
            result = build_once(source, root / 'build')
            self.assertTrue(result.changed)
            for path in (
                    result.project, result.notes_json, result.notes_markdown,
                    result.ready_manifest):
                self.assertTrue(path.is_file())
            manifest = json.loads(result.ready_manifest.read_text())
            self.assertEqual(manifest['status'], 'ready')
            self.assertEqual(manifest['project'], str(result.project))
            self.assertEqual(manifest['source'], str(source.resolve()))
            self.assertEqual(manifest['warning_count'], result.warning_count)
            second = build_once(source, root / 'build')
            self.assertFalse(second.changed)

    def test_failed_build_preserves_last_ready_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'main.py'
            source.write_text(SOURCE, encoding='utf-8')
            result = build_once(source, root / 'build')
            previous = result.project.read_bytes()
            source.write_text('def broken(:\n', encoding='utf-8')
            with self.assertRaises(BestEffortError):
                build_once(source, root / 'build')
            self.assertEqual(result.project.read_bytes(), previous)

    def test_artifact_name_cannot_escape_output_directory(self):
        source = Path('/tmp/main.py')
        output = Path('/tmp/build')
        with self.assertRaises(ValueError):
            artifact_paths(source, output, '../outside')

    @patch('workflow.subprocess.run')
    @patch('workflow.shutil.which', return_value='/usr/bin/pbcopy')
    @patch('workflow.sys.platform', 'darwin')
    def test_macos_copy_path_uses_pbcopy(self, _which, run):
        copy_path(Path('/tmp/example.m5f2'))
        run.assert_called_once_with(
            ['pbcopy'], input='/private/tmp/example.m5f2', text=True, check=True)


if __name__ == '__main__':
    unittest.main()
