# SPDX-License-Identifier: MIT
# Adapted from the original project review H symbol renderer.
import json,math,uuid
Q=lambda s:json.dumps(str(s),ensure_ascii=False)
NAME="p2-editor-a"
def UID(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,"asamomijijp-code:p2-editor-a:"+s))
def symbol(p,x,y,path):
 x=round(round(x/1.27)*1.27,5);y=round(round(y/1.27)*1.27,5)
 pins=p['pins'];passive=len(pins)==2;half=math.ceil(len(pins)/2);sides=[pins[:half],pins[half:]]
 if passive:sides=[[pins[0]],[pins[1]]]
 hx=2.54 if passive else 20.32;hy=3.81 if passive else max(5.08,(max(map(len,sides))+1)*1.27)
 key='ED1:'+p['ref'];fx='(effects (font (size 0.95 0.95)))';items=[];ps=[]
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
