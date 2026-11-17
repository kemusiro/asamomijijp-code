#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate connected multi-sheet KiCad review schematic and BOM from design.py."""
import argparse,csv,json,math,uuid,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from design import make,V3,V5,G
HERE=Path(__file__).resolve().parent
Q=lambda s:json.dumps(str(s),ensure_ascii=False)
UID=lambda s:str(uuid.uuid5(uuid.NAMESPACE_URL,'asamomijijp-code:f1-carrier-a:'+s))
ROOTID=UID('root');NAME='f1-carrier'

def symbol(p,x,y,path):
 x=round(round(x/1.27)*1.27,5);y=round(round(y/1.27)*1.27,5)
 pins=p['pins'];passive=len(pins)==2;half=math.ceil(len(pins)/2);sides=[pins[:half],pins[half:]]
 if passive:sides=[[pins[0]],[pins[1]]]
 hx=2.54 if passive else 20.32;hy=3.81 if passive else max(5.08,(max(map(len,sides))+1)*1.27)
 key='F1C:'+p['ref'];fx='(effects (font (size 0.95 0.95)))';items=[];ps=[]
 geom=f'(rectangle (start {-hx} {hy}) (end {hx} {-hy}) (stroke (width 0.2) (type default)) (fill (type background)))'
 if passive:
  if p['ref'].startswith('C'):
   geom=''.join('(polyline (pts '+''.join(f'(xy {a} {b})' for a,b in pts)+') (stroke (width .2) (type default)) (fill (type none)))' for pts in [[(-2.54,0),(-.762,0)],[(-.762,-2.54),(-.762,2.54)],[(.762,-2.54),(.762,2.54)],[(.762,0),(2.54,0)]])
  else:geom='(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width .2) (type default)) (fill (type none)))'
 for side,seq in enumerate(sides):
  for i,pin in enumerate(seq):
   px=(-1 if side==0 else 1)*(hx+2.54);py=0 if passive else hy-2.54-i*2.54;angle=0 if side==0 else 180
   ps.append(f'(pin {pin["type"]} line (at {px} {py} {angle}) (length 2.54) (name {Q(pin["name"])} {fx}) (number {Q(pin["num"])} {fx}))')
   gx=round(x+px,5);gy=round(y-py,5);tag=p['ref']+':'+pin['num'];net=pin['net']
   if net is None:items.append(f'(no_connect (at {gx} {gy}) (uuid {UID(tag+"nc")}))')
   else:
    xx=round(gx+(-3.81 if side==0 else 3.81),5)
    items.append(f'(wire (pts (xy {gx} {gy}) (xy {xx} {gy})) (stroke (width 0) (type default)) (uuid {UID(tag+"wire")}))')
    # Global labels connect sheets. Numeric pinouts remain explicit, no hidden supplies.
    just='right' if side==0 else 'left';a=0 if side==0 else 180
    items.append(f'(global_label {Q(net)} (shape bidirectional) (at {xx} {gy} {a}) (effects (font (size 0.9 0.9)) (justify {just})) (uuid {UID(tag+"label")}))')
 lib=f'(symbol {Q(key)} (pin_names (offset 0.5)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) {fx}) (property "Value" {Q(p["value"])} (at 0 0 0) {fx}) (symbol {Q(p["ref"]+"_1_1")} {geom} '+''.join(ps)+'))'
 physical=not p['ref'].startswith('#')
 items.append(f'(symbol (lib_id {Q(key)}) (at {x} {y} 0) (unit 1) (in_bom {"yes" if physical else "no"}) (on_board {"yes" if physical else "no"}) (dnp no) (uuid {UID(p["ref"])})'
  f'(property "Reference" {Q(p["ref"])} (at {x} {round(y-hy-3.81,5)} 0) {fx})'
  f'(property "Value" {Q(p["value"])} (at {x} {round(y+hy+3.81,5)} 0) {fx})'
  f'(property "Footprint" {Q(p["footprint"])} (at {x} {y} 0) (effects (font (size 1 1)) hide))'
  f'(instances (project "{NAME}" (path "{path}" (reference {Q(p["ref"])}) (unit 1)))))')
 return lib,items,hy

def generate(output,pinfile):
 out=Path(output);out.mkdir(parents=True,exist_ok=True);design=make(Path(pinfile))
 (out/'circuit.json').write_text(json.dumps(design,indent=2)+'\n')
 parts=design['parts'];pages=[]
 for group in sorted({p['sheet'] for p in parts}):
  todo=[p for p in parts if p['sheet']==group];page=1
  while todo:
   name=group+'-'+str(page);ys=[35.56]*3;placed=[];remaining=[]
   for p in todo:
    h=3.81 if len(p['pins'])==2 else max(5.08,(math.ceil(len(p['pins'])/2)+1)*1.27)
    col=min(range(3),key=ys.__getitem__)
    if ys[col]+2*h+17.78>266:remaining.append(p);continue
    x=round((64.77+col*132.08)/1.27)*1.27;y=round((ys[col]+h)/1.27)*1.27;placed.append((p,x,y));ys[col]+=2*h+17.78
   if not placed:raise ValueError('Part exceeds A3 sheet')
   pages.append((name,placed));todo=remaining;page+=1
 # Explicit power flags where a passive fuse/ferrite separates the source rail.
 for i,net in enumerate([G,V5,'AV3V3']):
  flag=dict(ref='#FLG'+str(i),value='PWR_FLAG',pins=[dict(num='1',name='PWR',net=net,type='power_out')],footprint='')
  pages[0][1].append((flag,45+i*100,263))
 sheets=[];all_libs=[]
 for page_index,(name,placed) in enumerate(pages,2):
  sid=UID('sheet:'+name);path='/'+ROOTID+'/'+sid;libs=[];items=[]
  title=f'F1 carrier review A | {name} | NOT FOR FABRICATION'
  items.append(f'(text {Q(title)} (at 16.51 17.78 0) (effects (font (size 2 2)) (justify left)) (uuid {UID(name+"title")}))')
  items.append(f'(text "Global labels connect across sheets. Physical pins / no hidden supplies. See circuit.json and README." (at 16.51 24.13 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid {UID(name+"note")}))')
  for p,x,y in placed:l,it,_=symbol(p,x,y,path);libs.append(l);items+=it
  sch='(kicad_sch (version 20250114) (generator "eeschema") (uuid '+UID(name)+') (paper "A3") (lib_symbols '+''.join(libs)+')\n'+'\n'.join(items)+'\n(embedded_fonts no))\n'
  (out/(name+'.kicad_sch')).write_text(sch)
  all_libs+=libs
  x=15+(page_index-2)%3*90;y=35+(page_index-2)//3*40
  sheets.append(f'(sheet (at {x} {y}) (size 80 25) (stroke (width .2) (type default)) (fill (color 0 0 0 0)) (uuid {sid}) (property "Sheetname" {Q(name)} (at {x} {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" {Q(name+".kicad_sch")} (at {x} {y+26} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "{NAME}" (path "/{ROOTID}" (page "{page_index}")))))')
 root='(kicad_sch (version 20250114) (generator "eeschema") (uuid '+ROOTID+') (paper "A3") (lib_symbols)\n'
 root+='(text "F1 ULX3S 85F carrier / REVIEW A / NO PCB RELEASE" (at 15 15 0) (effects (font (size 2 2)) (justify left)) (uuid '+UID('title')+'))\n'+'\n'.join(sheets)+'\n(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n'
 notes=['MANDATORY ULX3S v3.0.8 MODIFICATIONS: D9 and D52 REMOVE / OPEN. D51: cut bridge and fit Schottky IN5V -> internal 5V.',
        'US2 VBUS tap is on USB side of removed D9: DETECTION ONLY. D8 must be a reverse-blocking diode, not a bridge.',
        'JULX1/2: vertical male numbering; verify GP/GN names and orientation against module before any power is applied.',
        'External NC stop / power supervisor / missing-heartbeat watchdog independently inhibit reset, translators, DAC and line.',
        'REVIEW A: no PCB, assembly approval or electrical timing signoff. See README for power-up and measurement gates.']
 for i,note in enumerate(notes):
  item=f'(text {Q(note)} (at 15 {210+i*8} 0) (effects (font (size 1.25 1.25)) (justify left)) (uuid {UID("root-note"+str(i))}))'
  root=root.replace('\n(sheet_instances', '\n'+item+'\n(sheet_instances')
 (out/'F1C.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator \"kicad_symbol_editor\") '+''.join(l.replace('(symbol \"F1C:', '(symbol \"',1) for l in all_libs)+')\n')
 (out/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name \"F1C\") (type \"KiCad\") (uri \"${KIPRJMOD}/F1C.kicad_sym\") (options \"\") (descr \"Original F1 review symbols\")))\n')
 (out/(NAME+'.kicad_sch')).write_text(root);(out/(NAME+'.kicad_pro')).write_text('{}\n')
 with (out/'bom.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['Reference','Value','Footprint','Sheet','Datasheet','Review note'])
  for p in parts:w.writerow([p[k] for k in ['ref','value','footprint','sheet','source','note']])
 with (out/'assembly-extras.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['Item','Quantity','Selection','Scope'])
  w.writerows([['FPGA assembly',1,'ULX3S 85F PCB v3.0.8','Module; not a bare ECP5 on carrier'],['YM IC socket',1,'DIP40 wide 15.24mm','Additional socket for U12; IC is already represented by U12'],['D51 module modification',1,'STPS2L30AF candidate','Cut IN5V bridge; verify footprint and diode orientation on module'],['D8 module inspection',0,'US1 reverse-blocking Schottky required','Reuse if populated; otherwise select and fit suitable module diode'],['D9 / D52 module modification',0,'OPEN / REMOVE','Never fit a bridge or a D9 power diode'],['External volume',1,'Dual A10k','Offboard; wiring shown at JPOT'],['NC stop loop',1,'Normally-closed switch or deliberate fitted loop','Offboard JESTOP; open loop inhibits']])
 return design,len(pages)

def check_export(design,netlist):
 expected=defaultdict(set)
 for p in design['parts']:
  for pin in p['pins']:
   if pin['net'] is not None:expected[pin['net']].add((p['ref'],pin['num']))
 actual={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node') if not p.attrib['ref'].startswith('#')} for n in ET.parse(netlist).findall('./nets/net')}
 actual={n:v for n,v in actual.items() if v and not n.startswith('unconnected-')}
 if dict(expected)!=actual:raise ValueError('Exported connectivity differs: '+str({n:sorted(expected[n]^actual.get(n,set())) for n in expected if expected[n]!=actual.get(n)}))
 return len(actual)

def main():
 p=argparse.ArgumentParser();p.add_argument('--pins',type=Path,default=HERE.parents[2]/'fpga-standalone/boards/ulx3s/pins.json');p.add_argument('--output',type=Path,default=HERE/'schematic');p.add_argument('--check',action='store_true');a=p.parse_args();d,n=generate(a.output,a.pins)
 if a.check:
  sch=a.output/(NAME+'.kicad_sch')
  subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(a.output/'netlist.xml'),str(sch)],check=True)
  subprocess.run(['kicad-cli','sch','erc','--format','json','-o',str(a.output/'erc.json'),str(sch)],check=True)
  erc=json.loads((a.output/'erc.json').read_text());assert not any(s['violations'] for s in erc['sheets']), 'ERC violations'
  tree=ET.parse(a.output/'netlist.xml');tree.find('./design/source').text=sch.name
  tree.write(a.output/'netlist.xml',encoding='utf-8',xml_declaration=True)
  count=check_export(d,a.output/'netlist.xml');print('PASS complete exported pin/net sets',len(d['parts']),count,'pages',n+1)
 print('Generated',len(d['parts']),'components',n+1,'sheets; not fabrication release')
if __name__=='__main__':main()
