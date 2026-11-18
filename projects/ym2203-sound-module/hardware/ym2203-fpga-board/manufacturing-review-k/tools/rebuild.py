#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export/check four independent CAM sets in a new work tree; preserve all source CAD."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys

def main():
 p=argparse.ArgumentParser();p.add_argument('--hardware-root',required=True,type=Path);p.add_argument('--work',required=True,type=Path);p.add_argument('--kicad-cli',default='kicad-cli');p.add_argument('--kicad-python',default='python3');p.add_argument('--cam-python',default='python3');a=p.parse_args();h=a.hardware_root.resolve();w=a.work.resolve();here=Path(__file__).resolve().parent;cli=shutil.which(a.kicad_cli);assert cli,'kicad-cli not found';assert not w.exists(),'Use a new empty work directory'
 w.mkdir(parents=True);cfg=json.loads((here.parent/'boards.json').read_text());(w/'boards.json').write_text(json.dumps(cfg,indent=2)+'\n');manifest={}
 for key,b in cfg.items():
  src=h/b['dir'];shutil.copytree(src,w/'cad'/key,ignore=shutil.ignore_patterns('*.kicad_prl','*.lck','__pycache__'))
  for q in src.rglob('*'):
   if q.is_file() and q.suffix in ['.kicad_pcb','.kicad_pro','.kicad_sch','.kicad_sym','.kicad_mod']:manifest[str(q.relative_to(h))]=hashlib.sha256(q.read_bytes()).hexdigest()
 for src,name in [(h/'clean-sheet-pcb-review-j/P2H.pretty','P2H.pretty'),(h/'editor-shield-review-b/ED2.pretty','ED2.pretty')]:
  shutil.copytree(src,w/'cad'/name)
  for q in src.rglob('*'):
   if q.is_file():manifest[str(q.relative_to(h))]=hashlib.sha256(q.read_bytes()).hexdigest()
 q=w/'cad/base-j4/p2-base-j.kicad_pcb';s=q.read_text().replace('P2 revision3.6 / base / PCB review I','P2 revision3.7 / base / PCB review J').replace('(rev "3.6-I")','(rev "3.7-J")');q.write_text(s)
 (w/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');env=dict(os.environ,PATH=str(Path(cli).parent)+os.pathsep+os.environ.get('PATH',''),PYTHONDONTWRITEBYTECODE='1')
 subprocess.run([sys.executable,str(here/'cam_export.py'),str(w)],env=env,check=True)
 subprocess.run([a.kicad_python,str(here/'native_geometry.py'),str(w)],env=env,check=True)
 subprocess.run([a.cam_python,str(here/'verify_cam.py'),str(w)],env=env,check=True)
 subprocess.run([a.kicad_python,str(here/'source_equivalence.py'),'--hardware-root',str(h),'--work',str(w)],env=env,check=True)
 for rel,digest in manifest.items():assert hashlib.sha256((h/rel).read_bytes()).hexdigest()==digest,('Source changed',rel)
 print('PASS: fresh native/CAM checks on four variants; all source files unchanged')
if __name__=='__main__':main()
