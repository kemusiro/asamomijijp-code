# SPDX-License-Identifier: MIT
"""Check immutable extracted sources and runtime closure, not historical imports."""
import hashlib,json,re,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 m=json.loads((ROOT/'release-manifest.json').read_text())
 for n,digest in m['files'].items():
  assert not Path(n).is_absolute() and '..' not in Path(n).parts
  assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==digest,n
 assert not (ROOT/'hardware/ym2203-fpga-board').exists()
 for n in ['fpga-standalone','simulation-jt03','synthesis-jt03','fpga-jt03-minimal','publication-plan','.internal-preservation']:assert not (ROOT/n).exists(),n
 locks=json.loads((ROOT/'hardware/ym2203-single-board/firmware/runtime-lock.json').read_text())['sha256']
 for n,digest in locks.items():assert hashlib.sha256((ROOT/'hardware/ym2203-single-board/diagnostics'/n).read_bytes()).hexdigest()==digest
 for n in ['ym2203_fw.py','ym2203_pitch.py']:assert (ROOT/'hardware/ym2203-single-board/firmware/src'/n).is_file()
 needles=['ym2203-sound-module-'+'internal','.codex/'+'attachments','-----BEGIN '+'PRIVATE KEY-----']
 for n in m['files']:
  p=ROOT/n;s=p.read_text(encoding='utf-8')
  for needle in needles:assert needle not in s,(n,'nonpublic marker')
  assert not re.search(r'/Users/[A-Za-z0-9_.-]+/',s),(n,'personal absolute path')
 with (ROOT/'hardware/p2/procurement/parts-1set.csv').open() as f:rows=list(csv.DictReader(f))
 for row in rows:
  assert not any(x in row['suggested_supplier']+row['manufacturer_part_number']+row['purpose'] for x in ['User supplied','user supplied','ユーザー','手持','Rev Cから流用']),row['id']
 print('PASS: export hashes',len(m['files']),'runtime closure, excluded research/private trees and privacy markers')
if __name__=='__main__':main()
