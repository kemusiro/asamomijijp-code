# SPDX-License-Identifier: MIT
"""Verify the original import snapshot;run at its migration commit."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    record = json.loads((ROOT / 'migration.json').read_text())
    expected = {row['path']: row['imported_sha256'] for row in record['files']}
    expected.update(record['added_files_sha256'])
    found = set()
    for file in ROOT.rglob('*'):
        relative = file.relative_to(ROOT)
        if any(part in {'.cache', 'node_modules', '__pycache__', 'outputs', 'local-test-data'}
               for part in relative.parts):
            continue
        if not file.is_file() and not file.is_symlink():
            continue
        if file.suffix in {'.pyc', '.pyo'}:
            continue
        assert not file.is_symlink(), relative
        assert file.suffix.lower() not in {'.zip', '.pdf', '.png', '.bin', '.uf2', '.vgm', '.vgz', '.kicad_prl'}, relative
        data = file.read_bytes()
        data.decode('utf-8')
        private_home = b'/' + b'Users/'
        attachment_path = b'.codex/' + b'attachments'
        private_key = b'-----BEGIN ' + b'PRIVATE KEY-----'
        assert private_home not in data and attachment_path not in data, relative
        assert private_key not in data, relative
        name = relative.as_posix()
        if name == 'migration.json':
            continue
        assert name in expected, ('unrecorded', name)
        assert hashlib.sha256(data).hexdigest() == expected[name], ('changed', name)
        found.add(name)
    assert found == set(expected), ('missing', set(expected) - found)
    assert 'MIT License' in (ROOT / 'LICENSE').read_text()
    lock = json.loads((ROOT / 'hardware/ym2203-single-board/firmware/runtime-lock.json').read_text())
    for name, digest in lock['sha256'].items():
        path = ROOT / 'hardware/ym2203-single-board/diagnostics' / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
    print('PASS: import inventory,all payload hashes,MIT license,unchanged runtime helpers and text-only publication checks')
    print('files:', len(found), 'plus migration.json')


if __name__ == '__main__':
    main()
