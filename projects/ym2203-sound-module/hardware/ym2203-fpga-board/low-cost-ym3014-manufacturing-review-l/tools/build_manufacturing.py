# SPDX-License-Identifier: MIT
"""Export/check read-only review K copies; ZIP output stays outside source control."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, tempfile, zipfile

HERE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=HERE.parent / 'low-cost-ym3014-pcb-review-k')
parser.add_argument('--pcb-python', required=True)
parser.add_argument('--cam-python', required=True)
parser.add_argument('--zip-output', type=Path, default=HERE / 'local-output')
args = parser.parse_args()
source = args.source.resolve()
def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.kicad_prl'}
before = hashes(source)
with tempfile.TemporaryDirectory() as name:
    work = Path(name)
    for board in ['base', 'module', 'panel']:
        shutil.copytree(source / board, work / 'cad' / board)
    shutil.copytree(source / 'P2LC.pretty', work / 'cad' / 'P2LC.pretty')
    subprocess.run([sys.executable, str(HERE / 'tools/cam_export.py'), str(work)], check=True)
    subprocess.run([args.pcb_python, str(HERE / 'tools/native_geometry.py'), str(work)], check=True)
    shutil.copytree(work / 'artifacts', HERE / 'artifacts', dirs_exist_ok=True)
    shutil.copy2(work / 'native-geometry.json', HERE / 'native-geometry.json')
assert hashes(source) == before, 'Source K changed during export'
subprocess.run([args.cam_python, str(HERE / 'tools/verify_cam.py'), str(HERE)], check=True)
args.zip_output.mkdir(parents=True, exist_ok=True)
manifest = {'source_revision': 'LC-K', 'source_files_sha256': before, 'files': {}, 'archives': {}}
for board in ['base', 'module', 'panel']:
    folder = HERE / 'artifacts' / board / 'gerbers'
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in {'.gtl','.gbl','.g1','.g2','.gts','.gbs','.gto','.gbo','.gm1','.drl','.gbrjob'})
    expected = 12 if board == 'base' else 10
    assert len(files) == expected, (board, len(files))
    path = args.zip_output / ('p2-' + board + '-k-5pcs-gerber.zip')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            info = zipfile.ZipInfo(p.name, date_time=(2026,11,20,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, p.read_bytes())
            manifest['files'][str(p.relative_to(HERE))] = hashlib.sha256(p.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and len(z.namelist()) == expected
    manifest['archives'][path.name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'files': expected}
(HERE / 'manufacturing-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('PASS: read-only K, ERC/DRC, CAM geometry and three separately packaged board lots')
