# SPDX-License-Identifier: MIT
"""Current design contract; no comparison to a historical review tree."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load():return {b:json.loads((ROOT/'cad'/b/'circuit.json').read_text()) for b in ('base','module','panel')}
def normalized(d):return {p['ref']:{'value':p['value'],'footprint':p['footprint'],'pins':p['pins']} for p in d['parts']}
def verify(circuits):
 expected=json.loads((ROOT/'requirements/approved-topology.json').read_text())
 assert set(circuits)==set(expected)
 for b,d in circuits.items():assert normalized(d)==expected[b],b+' approved pins/values/footprints changed'
 return True
def verify_bom(circuits,rows=None):
 if rows is None:
  with (ROOT/'procurement/parts-1set.csv').open() as f:rows=list(csv.DictReader(f))
 expected={b+':'+p['ref'] for b,d in circuits.items() for p in d['parts']}
 seen=[]
 for row in rows:
  assert int(row['required_per_set'])>0 and int(row['sales_pack_size'])>0
  q,n=int(row['required_per_set']),int(row['sales_pack_size'])
  assert int(row['packages_for_one_set'])==(q+n-1)//n
  seen.extend(x for x in row['refs'].split(';') if x)
 assert len(rows)==len({r['id'] for r in rows})==88
 assert len(seen)==len(set(seen))==302 and set(seen)==expected
 return True
if __name__=='__main__':
 d=load();verify(d);verify_bom(d);print('PASS: 3 current topologies, HOST/G40/USB/STOP contract, 302 references and 88 general BOM rows')
