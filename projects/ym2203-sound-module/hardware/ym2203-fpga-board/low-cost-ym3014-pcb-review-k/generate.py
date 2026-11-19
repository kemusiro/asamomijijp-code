#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render connected KiCad split review schematics; export ERC/netlists with --check.
Symbol renderer adapted from this project's reviews B/C (MIT); historical inputs are read-only.
"""
import argparse,csv,json,math,subprocess,uuid,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from design import make,HERE,V3,V5,G
Q=lambda s:json.dumps(str(s),ensure_ascii=False)
NAME='';BOARD=''
def UID(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'asamomijijp-code:p2-ym3014-pcb-review-k:'+BOARD+':'+s))

def symbol(p,x,y,path):
 x=round(round(x/1.27)*1.27,5);y=round(round(y/1.27)*1.27,5)
 pins=p['pins'];passive=len(pins)==2;half=math.ceil(len(pins)/2);sides=[pins[:half],pins[half:]]
 if passive:sides=[[pins[0]],[pins[1]]]
 hx=2.54 if passive else 20.32;hy=3.81 if passive else max(5.08,(max(map(len,sides))+1)*1.27)
 key='P2LC:'+p['ref'];fx='(effects (font (size 0.95 0.95)))';items=[];ps=[]
 geom=f'(rectangle (start {-hx} {hy}) (end {hx} {-hy}) (stroke (width 0.2) (type default)) (fill (type background)))'
 if passive:
  if p['ref'].startswith('C'):
   geom=''.join('(polyline (pts '+''.join(f'(xy {a} {b})' for a,b in pts)+') (stroke (width .2) (type default)) (fill (type none)))' for pts in [[(-2.54,0),(-.762,0)],[(-.762,-2.54),(-.762,2.54)],[(.762,-2.54),(.762,2.54)],[(.762,0),(2.54,0)]])
  else:geom='(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width .2) (type default)) (fill (type none)))'
 if p['ref']=='CRB':
  geom+='(text "+" (at -1.8 3.6 0) (effects (font (size 1 1))))'
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


def generate(board,d):
 global NAME,BOARD
 BOARD=board;NAME={'base':'p2-base-lc-k','module':'p2-ym2203-lc-k','panel':'p2-panel-lc-k'}[board];rootid=UID('root')
 out=HERE/board;out.mkdir(exist_ok=True)
 (out/'circuit.json').write_text(json.dumps(d,indent=2)+'\n')
 pages=[]
 for group in sorted({p['sheet'] for p in d['parts']}):
  todo=[p for p in d['parts'] if p['sheet']==group];number=1
  while todo:
   heights=[35.56]*3;placed=[];remaining=[]
   for p in todo:
    h=3.81 if len(p['pins'])==2 else max(5.08,(math.ceil(len(p['pins'])/2)+1)*1.27)
    col=min(range(3),key=heights.__getitem__)
    if heights[col]+2*h+17.78>256:remaining.append(p);continue
    x=round((64.77+col*132.08)/1.27)*1.27;y=round((heights[col]+h)/1.27)*1.27
    placed.append((p,x,y));heights[col]+=2*h+17.78
   if not placed:raise ValueError('Component exceeds A3')
   pages.append((group+'-'+str(number),placed));todo=remaining;number+=1
 if True:
  for i,net in enumerate([G,V5,'AV3V3'] if board=='base' else [G,'UPLINK_3V3','PANEL_VSYS'] if board=='panel' else []):
   flag=dict(ref='#FLG'+str(i),value='PWR_FLAG',pins=[dict(num='1',name='PWR',net=net,type='power_out')],footprint='')
   pages[0][1].append((flag,45+i*100,263))
 libs_all=[];sheets=[]
 for ix,(name,placed) in enumerate(pages,2):
  sid=UID('sheet:'+name);path='/'+rootid+'/'+sid;libs=[];items=[]
  title='P2 YM3014 PCB review K | '+board+' | '+name+' | PROTOTYPE REVIEW'
  items.append(f'(text {Q(title)} (at 16.51 17.78 0) (effects (font (size 1.7 1.7)) (justify left)) (uuid {UID(name+"title")}))')
  items.append(f'(text "Global labels connect. Connector types model external sources. See ../COMPATIBILITY.md. No bench acceptance." (at 16.51 24.13 0) (effects (font (size 1 1)) (justify left)) (uuid {UID(name+"note")}))')
  for p,x,y in placed:
   lib,its,_=symbol(p,x,y,path);libs.append(lib);items+=its
  content='(kicad_sch (version 20250114) (generator "eeschema") (uuid '+UID(name)+') (paper "A3") (lib_symbols '+''.join(libs)+')\n'+'\n'.join(items)+'\n(embedded_fonts no))\n'
  (out/(name+'.kicad_sch')).write_text(content);libs_all+=libs
  x=15+(ix-2)%3*90;y=35+(ix-2)//3*40
  sheets.append(f'(sheet (at {x} {y}) (size 80 25) (stroke (width .2) (type default)) (fill (color 0 0 0 0)) (uuid {sid}) (property "Sheetname" {Q(name)} (at {x} {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" {Q(name+".kicad_sch")} (at {x} {y+26} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "{NAME}" (path "/{rootid}" (page "{ix}")))))')
 notes=['P2 YM3014B-F PCB review K /2026-11-20 / PROTOTYPE REVIEW', 'K: U13 Akizuki110679 25MHz0x60CL8pF;oldY1 removed;PROC J Q1/E4 logic;GPIO unchanged', 'Base Picossci2A; source Picossci2B + realYM2203 + YM3014B-F; panel PicoRP2040 + HC4051.', 'HOST I2C0 GPIO20/21 0x42/100kHz unchanged; panel serviceI2C1 GPIO26/27 0x30.', 'GPIO unchanged; G40 CH1=analog FM, CH2=analog SSG. I2S retained.', 'STOP GPIO23 -> direct gate permissions; source ENABLE -> RUN extra wire mandatory.', 'USB-B VBUS isolated from external5V. Panel3V3 input -> Schottky -> PicoVSYS; no USB while Grove attached.', 'RB buffer + output buffer MCP6002-E/P; ADC mix on base; native ERC is NOT sound acceptance.']
 root='(kicad_sch (version 20250114) (generator "eeschema") (uuid '+rootid+') (paper "A2") (lib_symbols)\n'+'\n'.join(sheets)
 for i,n in enumerate(notes):root+=f'\n(text {Q(n)} (at 15 {255+i*5} 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid {UID("note"+str(i))}))'
 root+='\n(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n'
 (out/(NAME+'.kicad_sch')).write_text(root)
 if not (out/(NAME+'.kicad_pro')).exists():(out/(NAME+'.kicad_pro')).write_text('{}\n')
 (out/'P2LC.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+''.join(l.replace('(symbol "P2LC:', '(symbol "',1) for l in libs_all)+')\n')
 (out/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "P2LC") (type "KiCad") (uri "${KIPRJMOD}/P2LC.kicad_sym") (options "") (descr "Original project MIT review symbols")))\n')
 (out/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name \"P2LC\") (type \"KiCad\") (uri \"${KIPRJMOD}/../P2LC.pretty\") (options \"\") (descr \"MIT encoder geometry from editorB; reviewF original module landings\")))\n')
 with (out/'bom.csv').open('w',newline='') as f:
  w=csv.writer(f,lineterminator="\n");w.writerow(['Reference','Value','Footprint','Sheet','Datasheet','Note'])
  for p in d['parts']:w.writerow([p[k] for k in ['ref','value','footprint','sheet','source','note']])
 return out/(NAME+'.kicad_sch'),len(pages)+1

def check_export(d,path):
 expected=defaultdict(set)
 for p in d['parts']:
  for pin in p['pins']:
   if pin['net'] is not None:expected[pin['net']].add((p['ref'],pin['num']))
 actual={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node') if not p.attrib['ref'].startswith('#')} for n in ET.parse(path).findall('./nets/net')}
 actual={n:v for n,v in actual.items() if v and not n.startswith('unconnected-')}
 if dict(expected)!=actual:raise ValueError('Native netlist differs from design')
 return len(actual)

def main():
 a=argparse.ArgumentParser();a.add_argument('--check',action='store_true');args=a.parse_args()
 report=dict(schema_version=1,date='2026-11-20',kicad_version=subprocess.check_output(['kicad-cli','version'],text=True).strip(),boards={},scope='native ERC and pin/net connectivity only; not PCB, firmware or hardware acceptance')
 for board,d in make().items():
  sch,pages=generate(board,d);stats=dict(components=len(d['parts']),pages=pages)
  if args.check:
   netlist=sch.parent/'netlist.xml';erc=sch.parent/'erc.json'
   subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(netlist),str(sch)],check=True,stdout=subprocess.DEVNULL)
   subprocess.run(['kicad-cli','sch','erc','--format','json','-o',str(erc),str(sch)],check=True,stdout=subprocess.DEVNULL)
   data=json.loads(erc.read_text());violations=[v for sheet in data['sheets'] for v in sheet['violations']]
   if violations:
    print(json.dumps(violations,indent=2));raise SystemExit('ERC violations')
   stats.update(erc_violations=len(violations),nets=check_export(d,netlist))
   for p in [erc,netlist]:p.write_text(p.read_text().replace(str(HERE)+'/',''))
  report['boards'][board]=stats
 if args.check:(HERE/'native-verification.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
