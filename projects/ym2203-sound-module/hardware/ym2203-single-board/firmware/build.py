# SPDX-License-Identifier: MIT
"""Build a reproducible source firmware ZIP; refuse to replace earlier releases."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VERSION = '0.2.0-alpha.1'


def sha(data): return hashlib.sha256(data).hexdigest()


def build(destination):
    destination = Path(destination)
    if destination.exists(): raise FileExistsError('Use a new release filename')
    lock = json.loads((HERE/'runtime-lock.json').read_text())
    payload = {}
    for name in ('main.py','boot.py','ym2203_fw.py','ym2203_audio.py','ym2203_hw.py','ym2203_midi.py','ym2203_usb.py','ym2203_pitch.py'):
        target = 'target/'+name if name in ('main.py','boot.py') else 'target/lib/'+name
        payload[target] = (HERE/'src'/name).read_bytes()
    for name,expected in lock['sha256'].items():
        content = (HERE.parent/'diagnostics'/name).read_bytes()
        if sha(content) != expected: raise ValueError('Runtime dependency changed: '+name)
        payload['target/lib/'+name] = content
    for name in ('ym2203_revc.py','example.py','endurance.py','recovery.py','midi_handover.py'):
        payload['host/'+name] = (HERE/'host'/name).read_bytes()
    for name in ('README.txt','protocol-v1.md','runtime-lock.json','validation.json','commissioning-result.json','hardware-results.json','STREAM-3MIN-README.txt','RECOVERY-FINAL-README.txt','USB-MIDI-README.txt','USB-MIDI-SIX-HANDOVER-README.txt'):
        payload[name] = (HERE/name).read_bytes()
    payload['pc/usb-midi-test.html'] = (HERE/'pc/usb-midi-test.html').read_bytes()
    payload['LICENSE'] = (ROOT/'LICENSE').read_bytes()
    for file in sorted((HERE/'verification').iterdir()):
        if file.is_file(): payload['verification/'+file.name] = file.read_bytes()
    # Resolve every distributed import against its installation side or the
    # documented MicroPython standard/runtime modules. No hidden diagnostic deps.
    standard = {'sys','time','os','array','gc','math','struct','machine','micropython','rp2','uctypes'}
    for side in ('target','host'):
        sources = {Path(name).stem for name in payload if name.startswith(side+'/') and name.endswith('.py')}
        for name,data in payload.items():
            if not name.startswith(side+'/') or not name.endswith('.py'): continue
            for node in ast.walk(ast.parse(data)):
                imports = [alias.name.split('.')[0] for alias in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
                for module in imports:
                    if module not in standard | sources:
                        raise ValueError('Missing '+side+' dependency: '+module)
    validation = json.loads(payload['validation.json'])
    for name,expected in validation['source_sha256'].items():
        if sha((HERE/name).read_bytes()) != expected:
            raise ValueError('Validation is stale: '+name)
    manifest = {'version':VERSION,'format':'source-firmware-zip-v1',
                'physical_validation':json.loads(payload['hardware-results.json']),
                'files':{name:sha(data) for name,data in sorted(payload.items())}}
    payload['firmware-lock.json'] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(payload.items()):
            info=zipfile.ZipInfo(name,(2026,11,13,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,data)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: raise ValueError('ZIP CRC failure')
        for name,expected in manifest['files'].items():
            if sha(archive.read(name)) != expected: raise ValueError('ZIP hash mismatch: '+name)
    print('PASS: dependency closure,validation hashes,ZIP CRC and all payload SHA-256')
    print('files:',len(payload),'Python sources:',sum(n.endswith('.py') for n in payload))
    print('SHA-256:',sha(destination.read_bytes()))
    print(destination)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    build(parser.parse_args().destination)
