#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Archive hashes of vendor reports without claiming that timing passed."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--diamond-version',required=True);p.add_argument('--synplify-version',required=True);a=p.parse_args()
root=a.root.resolve();build=root/'build';reports={}
for f in sorted(build.rglob('*')):
 if f.is_file() and f.suffix.lower() in {'.twr','.par','.mrp','.srr','.ior','.log','.sdc','.lpf','.prf','.srf'}:reports[str(f.relative_to(root))]=hashlib.sha256(f.read_bytes()).hexdigest()
if not reports:raise SystemExit('No vendor reports found. Do not mark vendor execution or timing as passed.')
result={'kind':'Report inventory only; manual timing-review.json still required','diamond_version':a.diamond_version,'synplify_version':a.synplify_version,'files_sha256':reports,'timing_closed':False}
(root/'vendor-report-inventory.json').write_text(json.dumps(result,indent=2)+'\n');print('Collected',len(reports),'report hashes; no PASS inferred')
