#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Readable flat schematics for N; native topology compared separately."""
from pathlib import Path
import argparse,collections,json,subprocess,sys
from drawing import G,grid,mm,q,uid,Router,segment_points
from layout import layout
H=Path(__file__).resolve().parents[1]
POWER={'GND','V3V3','V5_CARRIER','V3_AUX','AV3V3','MCU_3V3','V5_MODULE','MCU_5V','PANEL_3V3','PANEL_VSYS','UPLINK_3V3','HP_3V3','HP_VSS'}
def label(pos,net,d):
 x,y=map(mm,pos);j='right bottom' if d[0]<0 else 'left bottom' if d[0]>0 else 'bottom' if d[1]<0 else 'top'
 return f'(label {q(net)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (justify {j})) (uuid {uid("label:"+net+str(pos))}))'
def graphic_text(s,x,y,size=2,just='left'):
 return f'(text {q(s)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify {just})) (uuid {uid(s+str(x)+str(y))}))'
def sheet_line(points,key):
 return '(polyline (pts '+''.join(f'(xy {x} {y})' for x,y in points)+') (stroke (width .2) (type dash) (color 130 140 150 1)) (fill (type none)) (uuid '+uid(key)+'))'
def make(board):
 source=json.loads((H/'inputs'/(board+'.json')).read_text());parts={p['ref']:p for p in source['parts']};paper,blocks=layout(board,parts)
 allparts=[c for b in blocks for c in b.components];assert set(c.ref for c in allparts)==set(parts),(board,set(parts)-{c.ref for c in allparts});assert len(allparts)==len(parts)
 d=H/board;d.mkdir(exist_ok=True);name='p2-'+board+'-readable-t'
 libs=[];items=[];by_net=collections.defaultdict(set);routers=[];overlaps=[]
 for block in blocks:
  for c in block.components:
   for p in c.pins:
    if p['net'] is not None:by_net[p['net']].add(block.title)
   lib,item=c.render(board);libs.append(lib);items.append(item)
  x,y,z,w=map(mm,block.rect)
  # Section headings, not page-like boxes: the entire board is one drawing.
  items+=[sheet_line([(x,y+12),(z,y+12)],board+block.title),graphic_text(block.title,x+4,y+7,2)]
  for i,a in enumerate(block.components):
   for b in block.components[i+1:]:
    p0,p1=a.bbox,b.bbox
    if p0[0]<p1[2] and p0[2]>p1[0] and p0[1]<p1[3] and p0[3]>p1[1]:overlaps.append([a.ref,b.ref])
 cross={n for n,g in by_net.items() if len(g)>1}
 for block in blocks:
  print(board,block.title,'components',len(block.components),flush=True)
  router=Router(block).run(POWER,cross);routers.append(router)
  print('  wired branches',len(router.connected),'named fallback',len(router.failed),flush=True)
 # Exact electrical graph on the routing lattice. Native wire junctions are
 # emitted at same-net branches, never at crossings between different nets.
 edges=collections.defaultdict(lambda:collections.defaultdict(set));labels=[];pin_points={}
 for router in routers:
  labels.extend(router.labels)
  for a,b,net in router.segments:
   pts=segment_points(a,b)
   for u,v in zip(pts,pts[1:]):edges[net][u].add(v);edges[net][v].add(u)
 for c in allparts:
  for p in c.pins:
   if p['net'] is None:
    x,y=map(mm,p['end']);items.append(f'(no_connect (at {x} {y}) (uuid {uid(board+c.ref+p["num"]+"nc")}))')
   pin_points[p['end']]=p['net'] or 'NC'
 # A route can join a pin stub before its outer end. Remove that unused tail
 # instead of leaving a dangling, electrically redundant wire in the drawing.
 label_points={p for p,n,direction in labels}
 for net,graph in edges.items():
  pending=[p for p,v in graph.items() if len(v)==1 and p not in label_points and p not in pin_points]
  while pending:
   p=pending.pop()
   if p not in graph or len(graph[p])!=1 or p in label_points or p in pin_points:continue
   n=next(iter(graph[p]));del graph[p];graph[n].remove(p)
   if len(graph[n])==1:pending.append(n)
 all_points=collections.defaultdict(dict)
 for net,graph in edges.items():
  for p,neighbors in graph.items():all_points[p][net]={(n[0]-p[0],n[1]-p[1]) for n in neighbors}
 bad_crossings=[]
 for p,nets in all_points.items():
  if len(nets)>1:
   sets=list(nets.values())
   if len(sets)!=2 or set(map(frozenset,sets))!={frozenset({(-1,0),(1,0)}),frozenset({(0,-1),(0,1)})}:bad_crossings.append((p,list(nets)))
  if p in pin_points and any(n!=pin_points[p] for n in nets):bad_crossings.append((p,'foreign pin'))
  for point,n,direction in labels:
   if p==point and any(other!=n for other in nets):bad_crossings.append((p,'foreign named node'))
 label_nodes=collections.defaultdict(set)
 for p,n,direction in labels:label_nodes[n].add(p)
 wire_count=0;junctions=0
 for net,graph in edges.items():
  breaks=set(label_nodes[net])
  for p,neighbors in graph.items():
   if len(neighbors)!=2:breaks.add(p)
   elif len({n[0] for n in neighbors})>1 and len({n[1] for n in neighbors})>1:breaks.add(p)
   if p in pin_points:breaks.add(p)
   if len(neighbors)>=3:
    x,y=map(mm,p);items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {uid(board+net+str(p)+"junction")}))');junctions+=1
  seen=set()
  for start in breaks:
   for nextp in graph[start]:
    e=tuple(sorted((start,nextp)))
    if e in seen:continue
    seen.add(e);prev=start;end=nextp
    while end not in breaks:
     nxt=next(n for n in graph[end] if n!=prev);seen.add(tuple(sorted((end,nxt))));prev,end=end,nxt
    a,b=map(mm,start),map(mm,end);x,y=a;z,w=b
    items.append(f'(wire (pts (xy {x} {y}) (xy {z} {w})) (stroke (width 0) (type default)) (uuid {uid(board+net+str(start)+str(end))}))');wire_count+=1
 for pos,net,direction in labels:items.append(label(pos,net,direction))
 # The same external power-source models as N, visible together at the footer.
 flags=['GND','V5_CARRIER','AV3V3','HP_3V3'] if board=='base' else ['GND','UPLINK_3V3','PANEL_VSYS'] if board=='panel' else ['MCU_5V']
 h=1080 if board=='base' else 940
 for i,net in enumerate(flags):
  ref='#FLG'+str(i);key='P2R:'+ref;x=mm(grid(35+i*70));y=mm(grid(h-24))
  libs.append(f'(symbol {q(key)} (pin_names hide) (in_bom no) (on_board no) (property "Reference" "#FLG" (at 0 0 0) (effects (font (size 1 1)) hide)) (property "Value" "PWR_FLAG" (at 0 0 0) (effects (font (size 1 1)) hide)) (symbol {q(ref+"_1_1")} (pin power_out line (at 0 0 90) (length 0) (name "PWR" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))')
  items.append(f'(symbol (lib_id {q(key)}) (at {x} {y} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {uid(board+ref)}) (property "Reference" {q(ref)} (at {x} {y} 0) (effects (font (size 1 1)) hide)) (property "Value" "PWR_FLAG" (at {x} {y} 0) (effects (font (size 1 1)) hide)) (instances (project {q(name)} (path "/{uid(board+":root")}" (reference {q(ref)}) (unit 1)))))')
  items.append(f'(label {q(net)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid {uid(board+ref+"label")}))')
  items.append(graphic_text('PWR source model',x,y+4,1))
 heading={'base':'ベース基板','module':'YM2203 音源基板','panel':'音色編集基板'}[board]
 items+=[graphic_text('P2 / '+heading+' / 全体回路図',20,22,3),graphic_text('PCB Tと同じ接続 / 図面T。基板ごとに1枚。同名ネットは接続、ドットのない交差は非接続。',20,33,1.7)]
 paper_decl='(paper "User" '+('1190 1080' if board=='base' else '850 940')+')' if paper=='User' else '(paper '+q(paper)+')'
 text='(kicad_sch (version 20250114) (generator "eeschema") (uuid '+uid(board+':root')+') '+paper_decl+' (title_block (title '+q('P2 '+board+' / complete schematic')+') (date "2026-11-20") (rev "PCB T / drawing T") (comment 1 "Logical redraw only - board connectivity unchanged")) (lib_symbols '+''.join(libs)+')\n'+'\n'.join(items)+f'\n(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n'
 if board=='panel':text=text.replace('PCB T','PCB N')
 (d/(name+'.kicad_sch')).write_text(text);(d/(name+'.kicad_pro')).write_text('{}\n')
 (d/'P2R.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+''.join(l.replace('(symbol "P2R:', '(symbol "',1) for l in libs)+')\n')
 (d/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "P2R") (type "KiCad") (uri "${KIPRJMOD}/P2R.kicad_sym") (options "") (descr "Original MIT readable circuit symbols")))\n')
 (d/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "P2LC") (type "KiCad") (uri "${KIPRJMOD}/../P2LC.pretty") (options "") (descr "Preserved N footprints")))\n')
 report=dict(board=board,components=len(allparts),paper=paper,wire_segments=wire_count,junctions=junctions,named_connections=len(labels),local_wired_branches=sum(len(r.connected) for r in routers),fallback_named_connections=sum(len(r.failed) for r in routers),fallback_nets=sorted({n for r in routers for n in r.failed}),symbol_envelope_overlaps=overlaps,bad_crossings=bad_crossings,blocks=[dict(title=b.title,parts=[c.ref for c in b.components]) for b in blocks])
 (d/'drawing-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('SUMMARY',board,{k:v for k,v in report.items() if k!='blocks'},flush=True)
 return d/(name+'.kicad_sch')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('boards',nargs='*',default=['base']);args=p.parse_args()
 for b in args.boards:make(b)
