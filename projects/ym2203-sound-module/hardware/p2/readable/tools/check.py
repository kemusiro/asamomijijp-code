#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent native XML comparison against authoritative T input circuit."""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,subprocess,xml.etree.ElementTree as ET
H=Path(__file__).resolve().parents[1]
def expected(board):
 source=json.loads((H/'inputs'/(board+'.json')).read_text());parts={p['ref']:p for p in source['parts']};nets=defaultdict(set)
 for c in parts.values():
  for p in c['pins']:
   if p['net'] is not None:nets[p['net']].add((c['ref'],p['num']))
 return parts,nets
def topology(board,xml):
 parts,source=expected(board);tree=ET.parse(xml);components={c.get('ref'):c for c in tree.findall('./components/comp') if not c.get('ref').startswith('#')}
 assert set(components)==set(parts),'Missing / additional components'
 for ref,c in components.items():
  assert c.findtext('value')==parts[ref]['value'],(board,ref,'value')
  assert c.findtext('footprint')==parts[ref]['footprint'],(board,ref,'footprint')
 original_pins={(r,p['num']):p for r,c in parts.items() for p in c['pins']};actual_pins=set();nets={};allnodes={}
 for n in tree.findall('./nets/net'):
  nodes=set()
  for v in n.findall('node'):
   if v.get('ref').startswith('#'):continue
   key=(v.get('ref'),v.get('pin'));nodes.add(key);actual_pins.add(key);allnodes[key]=n.get('name')
   assert v.get('pintype').removesuffix('+no_connect')==original_pins[key]['type'],(key,'pin type')
   assert (v.get('pintype')=='no_connect' or v.get('pintype').endswith('+no_connect'))==(original_pins[key]['net'] is None),(key,'NC marker')
  if nodes and not n.get('name').startswith('unconnected-'):nets[n.get('name')]=nodes
 assert actual_pins==set(original_pins),'Pin inventory differs'
 for key,p in original_pins.items():
  if p['net'] is None:assert allnodes[key].startswith('unconnected-'),(key,'NC pin connected')
 assert {frozenset(v) for v in nets.values()}=={frozenset(v) for v in source.values()},dict(board=board,missing_source_nets=[k for k,v in source.items() if v not in nets.values()],extra_view_nets=[k for k,v in nets.items() if v not in source.values()])
 mapping={n:next(k for k,v in nets.items() if v==pins) for n,pins in source.items()}
 return dict(components=len(parts),pins=len(original_pins),source_nets=len(source),electrical_topology_equal=True,original_values_and_footprints=True,pin_types_equal=True,no_connects_preserved=True,net_name_mapping=mapping)
def main():
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,default=H.parent/'cad');a.add_argument('--boards',nargs='+',default=['base']);args=a.parse_args()
 report=dict(date='2026-11-20',kicad_version=subprocess.check_output(['kicad-cli','version'],text=True).strip(),boards={})
 out=H/'local-output';out.mkdir(exist_ok=True)
 for b in args.boards:
  d=H/b;name='p2-'+b+'-readable-t';sch=d/(name+'.kicad_sch')
  assert (H/'inputs'/(b+'.json')).read_bytes()==(args.source/b/'circuit.json').read_bytes()
  drawing=json.loads((d/'drawing-report.json').read_text());assert not drawing['bad_crossings'] and not drawing['symbol_envelope_overlaps'],(b,'drawing geometry')
  def run(command):
   p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   with (out/(b+'-native.log')).open('a') as f:f.write(p.stdout)
   if p.returncode:raise RuntimeError(command,p.returncode,p.stdout[-1500:])
  run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(d/'netlist.xml'),str(sch)])
  stats=topology(b,d/'netlist.xml')
  run(['kicad-cli','sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(d/'erc.json'),str(sch)])
  erc=json.loads((d/'erc.json').read_text());violations=[v for s in erc['sheets'] for v in s['violations']];assert not violations,(b,violations)
  stats['erc_violations']=0
  run(['kicad-cli','sch','export','pdf','--black-and-white','--exclude-pdf-property-popups','-o',str(out/(name+'.pdf')),str(sch)])
  svgdir=out/(b+'-svg');svgdir.mkdir(exist_ok=True)
  run(['kicad-cli','sch','export','svg','--black-and-white','-o',str(svgdir),str(sch)])
  svg=next(svgdir.glob('*.svg'));(d/'schematic.svg').write_text('\n'.join(l.rstrip() for l in svg.read_text().splitlines())+'\n')
  info=subprocess.check_output(['pdfinfo',str(out/(name+'.pdf'))],text=True);assert 'Pages:           1' in info,info
  for n in ['erc.json','netlist.xml']:
   f=d/n;f.write_text(f.read_text().replace(str(H)+'/',''))
  stats.update(pdf_pages=1,paper=drawing['paper'],wire_segments=drawing['wire_segments'],local_wired_branches=drawing['local_wired_branches'],fallback_named_connections=drawing['fallback_named_connections'],symbol_envelope_overlaps=0,unintended_wire_contacts=0)
  report['boards'][b]=stats;print(b,{k:v for k,v in stats.items() if k!='net_name_mapping'},flush=True)
 report.update(result='PASS',current_CAD_topology_verified=True,scope='Logical redraw only. This drawing adds no changes to the T circuit; no hardware acceptance.')
 (H/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
