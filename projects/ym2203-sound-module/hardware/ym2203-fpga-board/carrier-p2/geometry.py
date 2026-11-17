#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original footprints from measured/official dimensional facts, no source CAD copper."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def generate(out):
 out=Path(out);lib=out/'P2C.pretty';lib.mkdir(parents=True,exist_ok=True)
 pins=json.loads((HERE/'pins.json').read_text());geo=json.loads((HERE/'header-geometry.json').read_text())['derived_board_header_facts']
 groups={}
 for r in geo:groups.setdefault(r['ref'],[]).append((str(r['pin']),r['x_mm'],r['y_mm']))
 groups['PGA2350_Socket_64']=[(r['module_pad'],(int(r['module_pad'][1:])-1)*2.54,('ABCDEFGHIJ'.index(r['module_pad'][0]))*2.54) for r in pins['gpio']]+[(pad,(int(pad[1:])-1)*2.54,('ABCDEFGHIJ'.index(pad[0]))*2.54) for pad in pins['module_fixed_pins']]
 for name,pp in groups.items():
  cx=sum(x for n,x,y in pp)/len(pp);cy=min(y for n,x,y in pp)-3
  if name in ['JUNO_A','JUNO_PWR']:cy=max(y for n,x,y in pp)+3
  ss=[f'(footprint "{name}" (version 20250114) (generator "pcbnew") (layer "F.Cu") (attr through_hole)',f'(property "Reference" "REF**" (at {cx:.3f} {cy:.3f}) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))',f'(property "Value" "{name}" (at {cx:.3f} {cy+1.5:.3f}) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))']
  for n,x,y in sorted(pp):
   shape='rect' if n in ['1','A1'] else 'circle'
   ss.append(f'(pad "{n}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))')
  if name=='PGA2350_Socket_64':
   ss.append('(fp_rect (start -1.27 -1.27) (end 24.13 24.13) (stroke (width .15) (type default)) (fill none) (layer "F.SilkS"))')
   ss.append('(fp_text user "A1 - TOP / VBUS A3" (at 11.43 -5) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))')
  else:
   x0=min(x for n,x,y in pp)-1.27;x1=max(x for n,x,y in pp)+1.27;y0=min(y for n,x,y in pp)-1.27;y1=max(y for n,x,y in pp)+1.27
   ss.append(f'(fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width .15) (type default)) (fill none) (layer "F.SilkS"))')
  ss.append(')');(lib/(name+'.kicad_mod')).write_text('\n'.join(ss)+'\n')
 (out/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "P2C") (type "KiCad") (uri "${KIPRJMOD}/P2C.pretty") (options "") (descr "Original P2 physical socket and UNO position facts")))\n')
 return groups
if __name__=='__main__':generate(HERE/'schematic')
