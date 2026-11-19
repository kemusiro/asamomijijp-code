"""Export a fresh CAM candidate in a new work directory; never save historical CAD.

Run from project root, with KiCad 10.0.5 on PATH and explicit Python interpreters.
"""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--kicad-python',default='python3');ap.add_argument('--cam-python',default='python3');a=ap.parse_args()
 h=a.hardware_root.resolve();w=a.work.resolve();tools=Path(__file__).resolve().parent
 if w.exists():raise SystemExit('Use a new, empty --work directory; existing results will not be overwritten')
 subprocess.run(['kicad-cli','version'],check=True)
 w.mkdir(parents=True);cad=w/'cad';cad.mkdir()
 source={'base':h/'clean-sheet-pcb-review-j/base','module':h/'clean-sheet-pcb-review-j/module','shield':h/'editor-shield-review-b/pcb-review-b'}
 manifest={}
 for key,p in source.items():
  shutil.copytree(p,cad/key,ignore=shutil.ignore_patterns('*.kicad_prl','__pycache__','*.lck'))
  for q in p.rglob('*'):
   if q.is_file() and q.suffix in ['.kicad_pcb','.kicad_pro','.kicad_sch','.kicad_mod','.kicad_sym']:
    manifest[str(q.relative_to(h))]=hashlib.sha256(q.read_bytes()).hexdigest()
 shutil.copytree(h/'clean-sheet-pcb-review-j/P2H.pretty',cad/'P2H.pretty')
 # J preserves I's title metadata in its historical native PCB. Fix only the export copy.
 p=cad/'base/p2-base-j.kicad_pcb';s=p.read_text();s=s.replace('P2 revision3.6 / base / PCB review I','P2 revision3.7 / base / PCB review J').replace('(rev "3.6-I")','(rev "3.7-J")');p.write_text(s)
 (w/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 subprocess.run([sys.executable,str(tools/'cam_export.py'),str(w)],check=True)
 subprocess.run([a.kicad_python,str(tools/'native_geometry.py'),str(w)],check=True)
 subprocess.run([a.cam_python,str(tools/'verify_cam.py'),str(w)],check=True)
 for rel,digest in manifest.items():assert hashlib.sha256((h/rel).read_bytes()).hexdigest()==digest,'Historical CAD changed'
 print('PASS: fresh native/CAM checks; source files unchanged. Package separately after review.')

if __name__=='__main__':main()
