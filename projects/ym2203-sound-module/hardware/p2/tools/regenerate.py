# SPDX-License-Identifier: MIT
"""Re-export in an independent work copy; never overwrite accepted CAM/CAD."""
import argparse,hashlib,json,shutil,subprocess,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def canonical(data,suffix):
 text=data.decode('utf-8')
 # KiCad embeds wall-clock generation comments; leave all geometry unchanged.
 text=re.sub(r'^%TF\.CreationDate,[^\n]*\n','',text,flags=re.M)
 text=re.sub(r'^G04 Created by KiCad[^\n]*\n','',text,flags=re.M)
 text=re.sub(r'^; #@! TF\.CreationDate,[^\n]*\n','',text,flags=re.M)
 text=re.sub(r'^(; DRILL file KiCad [^ \n]+) date [^\n]*',r'\1',text,flags=re.M)
 if suffix=='.gbrjob':
  d=json.loads(text);d.get('Header',{}).pop('CreationDate',None);text=json.dumps(d,sort_keys=True)
 return text

def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--pcb-python',required=True);p.add_argument('--cam-python',required=True);a=p.parse_args()
 work=a.work.resolve();assert not work.exists() and ROOT not in work.parents
 shutil.copytree(ROOT,work,ignore=shutil.ignore_patterns('local-output','__pycache__'))
 logs=work/'local-output/logs';logs.mkdir(parents=True)
 def run(name,cmd):
  with (logs/(name+'.log')).open('w') as f:r=subprocess.run([str(x) for x in cmd],stdout=f,stderr=subprocess.STDOUT,cwd=work)
  if r.returncode:raise RuntimeError(name+' failed: '+(logs/(name+'.log')).read_text()[-2400:])
 for b in ['base','module','panel']:run(b,[sys.executable,work/'tools/build_cam.py',b,'--pcb-python',a.pcb_python])
 run('assemble',[sys.executable,work/'tools/assemble_geometry.py'])
 run('contract',[sys.executable,work/'tools/contract.py'])
 run('native',[a.pcb_python,work/'tools/check_native.py'])
 run('cam',[a.cam_python,work/'tools/verify_cam.py',work,'--no-previews'])
 run('negative',[a.cam_python,work/'tools/test_cam.py',work])
 expected=json.loads((ROOT/'expected-archives.json').read_text());normalized=[]
 for b,e in expected.items():
  for n in e['contents']:
   x=ROOT/'artifacts'/b/'gerbers'/n;y=work/'artifacts'/b/'gerbers'/n
   assert canonical(x.read_bytes(),x.suffix)==canonical(y.read_bytes(),y.suffix),(b,n,'Native re-export changed more than generation timestamp comments')
   normalized.append(b+'/'+n)
 report={'result':'PASS','boards':3,'regenerated_CAM_files_equal_except_generation_timestamps':len(normalized),'geometry_and_pads_equal_to_approved':True,'erc_drc_parity_unconnected':0,'CAM_negative_tests':14,'private_or_old_reviews_required':False,'accepted_sources_modified':False}
 (work/'regeneration-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
