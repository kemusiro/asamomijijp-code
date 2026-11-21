# SPDX-License-Identifier: MIT
"""Recreate the exact issued ZIPs from immutable accepted CAM, no cart/history deps."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
expected=json.loads((ROOT/'expected-archives.json').read_text());out=ROOT/'local-output/gerbers';out.mkdir(parents=True,exist_ok=True)
for b,a in expected.items():
 files={n:ROOT/'artifacts'/b/'gerbers'/n for n in a['contents']}
 for n,p in files.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==a['contents'][n],(b,n)
 dest=out/Path(a['path']).name
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,p in sorted(files.items()):
   i=zipfile.ZipInfo(n,(2026,11,20,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,p.read_bytes())
 with zipfile.ZipFile(dest) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(a['contents'])
 assert hashlib.sha256(dest.read_bytes()).hexdigest()==a['sha256'],b
 print('PASS issued Gerber ZIP',b,a['sha256'])
