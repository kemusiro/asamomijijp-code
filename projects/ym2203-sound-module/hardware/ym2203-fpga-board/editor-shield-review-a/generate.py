#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original project symbol renderer plus connected editor sheets; KiCad CLI checks."""
import csv,json,subprocess,xml.etree.ElementTree as ET
from collections import defaultdict
from design import HERE,make
from symbols import symbol,UID,Q,NAME

def main():
    d=make();out=HERE/'schematic';out.mkdir(exist_ok=True);root=UID('root');libsall=[];sheets=[]
    for ix,group in enumerate(sorted({p['sheet'] for p in d['parts']}),2):
        sid=UID(group);path='/'+root+'/'+sid;items=[];libs=[];heights=[35.56]*3
        todo=[p for p in d['parts'] if p['sheet']==group]
        for p in todo:
            import math
            h=3.81 if len(p['pins'])==2 else max(5.08,(math.ceil(len(p['pins'])/2)+1)*1.27)
            col=min(range(3),key=heights.__getitem__);x=64.77+col*132.08;y=heights[col]+h
            if y+h>260:raise ValueError('sheet overflow '+p['ref'])
            lib,its,_=symbol(p,x,y,path);libs.append(lib);items+=its;heights[col]+=2*h+17.78
        for i,n in enumerate(['P2 YM2203 editor shield A / '+group+' / 3.3V ONLY / NOT FOR FABRICATION','External-source connector models are for native ERC; PCB routing, firmware and bench acceptance pending.']):
            items.append(f'(text {Q(n)} (at 16.51 {17.78+i*6.35} 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid {UID(group+str(i))}))')
        (out/(group+'.kicad_sch')).write_text('(kicad_sch (version 20250114) (generator "eeschema") (uuid '+UID(group+'file')+') (paper "A3") (lib_symbols '+''.join(libs)+')\n'+'\n'.join(items)+'\n(embedded_fonts no))\n');libsall+=libs
        x=15+(ix-2)%2*140;y=35+(ix-2)//2*60
        sheets.append(f'(sheet (at {x} {y}) (size 120 35) (stroke (width .2) (type default)) (fill (color 0 0 0 0)) (uuid {sid}) (property "Sheetname" {Q(group)} (at {x} {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" {Q(group+".kicad_sch")} (at {x} {y+36} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "{NAME}" (path "/{root}" (page "{ix}")))))')
    sch=out/(NAME+'.kicad_sch');sch.write_text('(kicad_sch (version 20250114) (generator "eeschema") (uuid '+root+') (paper "A3") (lib_symbols)\n'+''.join(sheets)+'\n(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n')
    (out/(NAME+'.kicad_pro')).write_text('{}\n');(out/'ED1.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+''.join(l.replace('(symbol "ED1:','(symbol "',1) for l in libsall)+')\n')
    (out/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "ED1") (type "KiCad") (uri "${KIPRJMOD}/ED1.kicad_sym") (options "") (descr "Original project MIT symbols")))\n')
    (out/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "ED1") (type "KiCad") (uri "${KIPRJMOD}/../ED1.pretty") (options "") (descr "Original UNO contact geometry from H")))\n')
    (HERE/'circuit.json').write_text(json.dumps(d,indent=2)+'\n')
    with (HERE/'bom.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['Reference','Value','Footprint','Datasheet','Note'])
        for p in d['parts']:w.writerow([p[k] for k in ['ref','value','footprint','source','note']])
    for args in [['sch','export','netlist','--format','kicadxml','-o',str(out/'netlist.xml'),str(sch)],['sch','erc','--format','json','-o',str(out/'erc.json'),str(sch)]]:subprocess.run(['kicad-cli',*args],check=True)
    e=json.loads((out/'erc.json').read_text());vs=[v for s in e['sheets'] for v in s['violations']];assert not vs,vs
    expected=defaultdict(set)
    for p in d['parts']:
        for q in p['pins']:
            if q['net']:expected[q['net']].add((p['ref'],q['num']))
    actual={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node')} for n in ET.parse(out/'netlist.xml').findall('./nets/net') if not n.attrib['name'].startswith('unconnected-')}
    assert dict(expected)==actual,'native netlist mismatch'
    for p in [out/'netlist.xml',out/'erc.json']:p.write_text(p.read_text().replace(str(HERE)+'/',''))
    (HERE/'native-verification.json').write_text(json.dumps(dict(kicad=subprocess.check_output(['kicad-cli','version'],text=True).strip(),components=len(d['parts']),nets=len(actual),erc_violations=0,netlist_matches=True,pcb_routed=False,firmware_implemented=False,hardware_accepted=False),indent=2)+'\n')
    print('ERC/netlist PASS',len(d['parts']),len(actual))
if __name__=='__main__':main()
