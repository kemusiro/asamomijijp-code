# SPDX-License-Identifier: MIT
"""Package controller-only player; no target UF2 or copyrighted songs."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from embed_song import demo, validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError('Use a new filename; accepted artifacts are immutable')
    members = {
        name: (ROOT / name).read_bytes() for name in
        ('host/player.py', 'host/lib/ym2203_revc_player.py', 'host/lib/ym2203_revc_stream.py')
    }
    members['host/music/recovery.bin'] = demo()
    members['README-ja.txt'] = (ROOT / 'PLAYER-README.txt').read_bytes()
    members['LICENSE-MIT.txt'] = (ROOT.parent / 'LICENSE').read_bytes()
    manifest = {
        'player_version': 1, 'target_version': '0.5.0-alpha.3',
        'target_firmware_included': False, 'hardware_tested': False,
        'scope': 'New HOST menu/playlist wrapper; unchanged accepted stream library and target firmware',
        'score': validate(demo()),
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in members.items()},
    }
    members['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(name, (2026, 11, 14, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    print('PASS: HOST player-only ZIP, original diagnostic and member hashes verified')
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print(output)


if __name__ == '__main__':
    main()
