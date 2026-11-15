# SPDX-License-Identifier: MIT
"""Package a HOST-only recovery check; no target UF2 or Ys II data included."""
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
        raise FileExistsError('Use a new output filename; accepted artifacts are immutable')
    score = demo()
    members = {
        'host/recovery_check.py': (ROOT / 'host/recovery_check.py').read_bytes(),
        'host/lib/ym2203_revc_stream.py': (ROOT / 'host/lib/ym2203_revc_stream.py').read_bytes(),
        'host/music/recovery.bin': score,
        'README-ja.txt': (ROOT / 'I2C-RECOVERY-README.txt').read_bytes(),
        'LICENSE-MIT.txt': (ROOT.parent / 'LICENSE').read_bytes(),
    }
    manifest = {
        'check_version': 1,
        'target_version': '0.4.0-alpha.2',
        'target_firmware_included': False,
        'hardware_tested': False,
        'scope': 'HOST-only STOP/lease/rebind/replay check; original diagnostic score, not Ys II',
        'score': validate(score),
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
    print('PASS: HOST-only ZIP, original score, CRC and member hashes')
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())
    print(output)


if __name__ == '__main__':
    main()
