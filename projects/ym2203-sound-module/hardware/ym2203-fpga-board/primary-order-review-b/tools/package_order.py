#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package only the selected L4/K2/B2 boards; never upload the combined archive to a fab."""
from pathlib import Path
import argparse,hashlib,json,zipfile,shutil
H=Path(__file__).resolve().parents[1]
def archive(path,items):
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,data in sorted(items):
   assert not name.startswith('/') and '..' not in Path(name).parts
   q=zipfile.ZipInfo(name,date_time=(2026,11,19,0,0,0));q.compress_type=zipfile.ZIP_DEFLATED;q.external_attr=0o100644<<16;z.writestr(q,data)
 with zipfile.ZipFile(path) as z:assert z.testzip() is None

def main():
 a=argparse.ArgumentParser();a.add_argument('--output',required=True,type=Path);a.add_argument('--workbook',type=Path);args=a.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True);p=json.loads((H/'order-plan.json').read_text());items=[]
 for b in p['boards']:
  src=H/b['gerbers'];files=[(f.name,f.read_bytes()) for f in src.iterdir() if f.is_file()];assert b['layers']==(4 if b['purchase_id']=='PCB1' else 2);archive(out/b['zip'],files);items.append((b['zip'],(out/b['zip']).read_bytes()))
 for name in ['README.md','purchase-bom.csv','akizuki-order.csv','other-suppliers.csv','reference-map.csv','assembly-vias.json','order-plan.json','CAPACITOR.md','FIT-CHECK.md','capacitor-screen.json','fit-record.json','source-records.json']:
  shutil.copy2(H/name,out/name);items.append((name,(H/name).read_bytes()))
 if args.workbook:
  name='p2-primary-l4-k2-order.xlsx';assert args.workbook.is_file()
  if args.workbook.resolve()!=(out/name).resolve():shutil.copy2(args.workbook,out/name)
  items.append((name,(out/name).read_bytes()))
 archive(out/'p2-primary-review-b-5pcb-1set.zip',items)
 digests={q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted(out.iterdir()) if q.is_file() and q.name!='SHA256SUMS.txt'};(out/'SHA256SUMS.txt').write_text(''.join(v+'  '+k+'\n' for k,v in digests.items()));print('PASS: selected three Gerber ZIPs and combined order archive;',len(digests),'output files')
if __name__=='__main__':main()
