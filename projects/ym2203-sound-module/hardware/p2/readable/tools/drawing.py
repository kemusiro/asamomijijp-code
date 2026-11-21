# SPDX-License-Identifier: MIT
"""Single-sheet KiCad symbols and orthogonal local wiring; original project code."""
import collections,heapq,itertools,json,math,uuid
G=1.27
def grid(x):return round(x/G)
def mm(x):return round(x*G,4)
def q(x):return json.dumps(str(x),ensure_ascii=False)
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'p2-readable-R:'+s))
def poly(points,width=.25):return '(polyline (pts '+''.join(f'(xy {x} {-y})' for x,y in points)+f') (stroke (width {width}) (type default)) (fill (type none)))'
def text(t,x,y,size=1.4,just='center'):
 return f'(text {q(t)} (at {x} {-y} 0) (effects (font (size {size} {size})){"" if just=="center" else " (justify "+just+")"}))'
def display(p):
 v=p['value'];r=p['ref']
 aliases={'ENC1':'RE111F-4S1 encoder','UBASE':'Picossci 2 / RP2350A','USOURCE':'AE-RP2040','UPICO':'Raspberry Pi Pico','JUSB':'USB-C / 5077CR-16','JMOD':'G40 / KEY6','J5':'LCD / M154 socket','U13':'AE-Si5351A-B','RVOL':'A10k x2','JEDIT':'Grove / 3.3V only','JUPLINK':'Grove / 3.3V only','F1':'2A hold / PTC','FB1':'600R @ 100MHz','CMOD5':'22u / 16V X7R','CACL':'10u / 50V NP','CACR':'10u / 50V NP','CRB':'10u / 50V +'}
 if r in aliases:return aliases[r]
 if r.startswith('RV') and len(p['pins'])==3:return 'B10k'
 if r.startswith('C'):return v.split(' ')[0]+(' / C0G' if 'C0G' in v else '')
 if r.startswith('R'):return v.split(' ')[0]+(' / 1%' if '1%' in v else '')
 if r.startswith('U'):return v.split(' ')[0].replace('PWRQ1','').replace('DBVR','').replace('DBVRE4','')
 if r.startswith('SW'):return v.split(' ')[0]
 return v if len(v)<25 else v.split(' ')[0]

class Component:
 def __init__(self,p,x,y,orientation='h',sides=None):
  self.p=p;self.ref=p['ref'];self.x=grid(x);self.y=grid(y);self.pins=[];self.glyph=[];self.orientation=orientation
  n=len(p['pins']);r=self.ref;self.kind='box'
  if n==2:
   self.kind='passive';vertical=orientation.startswith('v');flipped=orientation.endswith('f')
   supplies={'V3V3','V5_CARRIER','V3_AUX','AV3V3','MCU_3V3','V5_MODULE','MCU_5V','PANEL_3V3','PANEL_VSYS','UPLINK_3V3'}
   if vertical and p['pins'][1]['net'] in supplies and p['pins'][0]['net'] not in supplies:flipped=True
   for i,pin in enumerate(p['pins']):
    pos=(0,(-6 if i==0 else 6)) if vertical else ((-6 if i==0 else 6),0)
    direction=(0,-1 if i==0 else 1) if vertical else (-1 if i==0 else 1,0)
    if flipped:pos=tuple(-v for v in pos);direction=tuple(-v for v in direction)
    self.pins.append(dict(pin,local=pos,direction=direction))
   if r.startswith('C'):
    pts=[[(-5.08,0),(-.9,0)],[(.9,0),(5.08,0)],[(-.9,-2.54),(-.9,2.54)],[(.9,-2.54),(.9,2.54)]]
   elif r.startswith('D'):
    pts=[[(-5.08,0),(-2,0)],[(2,0),(5.08,0)],[(-2,-2),(-2,2)],[(-2,0),(2,-2),(2,2),(-2,0)]]
    if '5819' in p['value']:pts += [[(-2,-2),(-1,-2)],[(-2,2),(-3,2)]]
    if r.startswith('DLED'):pts += [[(0,-3),(2,-5)],[(1,-2),(3,-4)],[(1,-5),(2,-5),(2,-4)],[(2,-4),(3,-4),(3,-3)]]
   elif r.startswith('SW'):
    pts=[[(-5.08,0),(-2.54,0)],[(-2.54,0),(2.54,-2.54)],[(2.54,0),(5.08,0)]]
   else:pts=[[(-5.08,0),(-2.54,0)],[(-2.54,-1.2),(2.54,-1.2),(2.54,1.2),(-2.54,1.2),(-2.54,-1.2)],[(2.54,0),(5.08,0)]]
   if vertical:pts=[[(y,-x) for x,y in row] for row in pts]
   if flipped:pts=[[(-x,-y) for x,y in row] for row in pts]
   self.glyph=[poly(t) for t in pts]
   if r.startswith('C') and ('polar' in p['value'] or 'CP_' in p['footprint']):self.glyph.append(text('+',3.8,-3.8,1.52))
   if vertical:
    self.fields=[(r,4,-2.54,'left'),(display(p),4,2.54,'left')];self.bounds=(-3,-7, max(10,4+grid(max(len(r),len(display(p)))*.78)),7)
   else:
    self.fields=[(r,0,-4.3,'center'),(display(p),0,4.8,'center')];self.bounds=(-max(7,grid(max(len(r),len(display(p)))*.42)),-5,max(7,grid(max(len(r),len(display(p)))*.42)),5)
  elif r=='RVOL':
   self.kind='dual_pot';ps={z['num']:z for z in p['pins']};self.pins=[];self.glyph=[]
   for off,flip,nums in [(0,-1,['1','2','3']),(24,1,['4','5','6'])]:
    for num,pos,direction in [(nums[0],(off,8),(0,1)),(nums[1],(off+flip*8,0),(flip,0)),(nums[2],(off,-8),(0,-1))]:self.pins.append(dict(ps[num],local=pos,direction=direction))
    self.glyph += [poly([(mm(off)+flip*x,y) for x,y in row]) for row in [[(0,-7.62),(0,-5.08)],[(-1.5,-5.08),(1.5,-5.08),(1.5,5.08),(-1.5,5.08),(-1.5,-5.08)],[(0,5.08),(0,7.62)],[(7.62,0),(1.5,0)],[(3,-1),(1.5,0),(3,1)]]]
   self.fields=[(r,15,-17,'center'),(display(p),15,17,'center')];self.bounds=(-9,-15,33,15)
  elif r.startswith('RV'):
   self.kind='pot';ps={z['num']:z for z in p['pins']}
   self.pins=[dict(ps['1'],local=(0,8),direction=(0,1)),dict(ps['3'],local=(0,-8),direction=(0,-1)),dict(ps['2'],local=(8,0),direction=(1,0))]
   self.glyph=[poly(t) for t in [[(0,-7.62),(0,-5.08)],[(-1.5,-5.08),(1.5,-5.08),(1.5,5.08),(-1.5,5.08),(-1.5,-5.08)],[(0,5.08),(0,7.62)],[(7.62,0),(1.5,0)],[(3,-1),(1.5,0),(3,1)]]]
   self.fields=[(r,-5,-3,'right'),(display(p),-5,3,'right')];self.bounds=(-14,-9,9,9)
  elif r=='UAF':
   self.kind='opamp';positions={'1':((16,-12),(1,0)),'2':((-16,-8),(-1,0)),'3':((-16,-16),(-1,0)),'4':((0,28),(0,1)),'5':((-16,8),(-1,0)),'6':((-16,16),(-1,0)),'7':((16,12),(1,0)),'8':((0,-28),(0,-1))}
   self.pins=[dict(z,local=positions[z['num']][0],direction=positions[z['num']][1]) for z in p['pins']]
   for cy in [-15.24,15.24]:
    self.glyph += [poly([(-12.7,cy-10.16),(-12.7,cy+10.16),(12.7,cy),(-12.7,cy-10.16)]),text('+',-10,cy-5),text('-',-10,cy+5)]
    self.glyph += [poly([(-15.24,cy-5.08),(-12.7,cy-5.08)]),poly([(-15.24,cy+5.08),(-12.7,cy+5.08)]),poly([(12.7,cy),(15.24,cy)])]
   self.glyph += [poly([(0,-30.48),(0,-20.32)]),poly([(0,20.32),(0,30.48)])]
   self.fields=[(r,0,-2,'center'),('MCP6002',0,2,'center')];self.bounds=(-17,-29,17,29)
  else:
   if sides is None:
    if r=='U8' or (r=='U9' and '245' in p['value']):left=[z for z in p['pins'] if not z['name'].startswith('B') and z['name']!='VCCB'];right=[z for z in p['pins'] if z not in left]
    elif r=='U12':left=[z for z in p['pins'] if z['name'].startswith('D') or z['name'] in ['CS_N','WR_N','RD_N','A0','PHI_M','CLK','RESET_N','VDD','GND','AGND']];right=[z for z in p['pins'] if z not in left]
    elif r in ['UBASE','UPICO','USOURCE']:
     # Keep GPIOs grouped; exact physical pad numbers remain printed.
     signals=[z for z in p['pins'] if z['name'].startswith('GP')];other=[z for z in p['pins'] if z not in signals];k=(len(signals)+1)//2;left=signals[:k]+other[:(len(other)+1)//2];right=signals[k:]+other[(len(other)+1)//2:]
    elif r=='JMOD':left=[z for z in p['pins'] if int(z['num'])%2];right=[z for z in p['pins'] if z not in left]
    elif r.startswith('J'):left=[];right=p['pins']
    else:
     k=(n+1)//2;left=p['pins'][:k];right=p['pins'][k:]
   else:
    a,b=sides;lookup={z['num']:z for z in p['pins']};left=[lookup[str(v)] for v in a];right=[lookup[str(v)] for v in b];assert len(left)+len(right)==n
   half=max(len(left),len(right));hx=grid(40 if r=='JMOD' else 34 if r in ['UBASE','USOURCE','UPICO'] else 28 if n>=14 else 19);hy=(half+1)*2
   self.bounds=(-hx-2,-hy-9,hx+2,hy+10)
   self.glyph=[f'(rectangle (start {-mm(hx)} {mm(hy)}) (end {mm(hx)} {-mm(hy)}) (stroke (width .25) (type default)) (fill (type background)))']
   for side,seq in [('L',left),('R',right)]:
    for i,z in enumerate(seq):self.pins.append(dict(z,local=((-1 if side=='L' else 1)*(hx+4),-hy+4+i*4),direction=(-1 if side=='L' else 1,0)))
   self.fields=[(r,0,-mm(hy)-7,'center'),(display(p),0,mm(hy)+7,'center')]
  self.bbox=(self.x+self.bounds[0],self.y+self.bounds[1],self.x+self.bounds[2],self.y+self.bounds[3])
  for pin in self.pins:
   lx,ly=pin['local'];pin['end']=(self.x+lx,self.y+ly)
   dx,dy=pin['direction'];anchor=(pin['end'][0]+dx*5,pin['end'][1]+dy*5)
   # Route outside the field envelope of vertical passive symbols.
   while self.bbox[0]<=anchor[0]<=self.bbox[2] and self.bbox[1]<=anchor[1]<=self.bbox[3]:anchor=(anchor[0]+dx,anchor[1]+dy)
   pin['anchor']=anchor

 def render(self,board):
  key='P2R:'+self.ref;geom=' '.join(self.glyph);pins=[]
  hide=self.kind in ['passive','pot','dual_pot','opamp']
  for pin in self.pins:
   x,y=pin['local'];dx,dy=pin['direction'];a=0 if dx<0 else 180 if dx>0 else 270 if dy<0 else 90
   pins.append(f'(pin {pin["type"]} line (at {mm(x)} {-mm(y)} {a}) (length {2.54 if self.kind in ["passive","pot","dual_pot"] else 5.08}) (name {q(pin["name"])} (effects (font (size 1.27 1.27)))) (number {q(pin["num"])} (effects (font (size 1.05 1.05)))))')
  lib=f'(symbol {q(key)} (pin_names (offset .8){" hide" if hide else ""})'+(' (pin_numbers hide)' if self.kind=='passive' else '')+f' (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) (effects (font (size 1.52 1.52)))) (property "Value" "" (at 0 0 0) (effects (font (size 1.27 1.27)))) (symbol {q(self.ref+"_1_1")} {geom} '+''.join(pins)+'))'
  props=''
  for name,val in [('Reference',self.ref),('Value',self.p['value']),('Footprint',self.p['footprint'])]:props+=f'(property {q(name)} {q(val)} (at {mm(self.x)} {mm(self.y)} 0) (effects (font (size 1.27 1.27)) hide))'
  for i,(val,x,y,just) in enumerate(self.fields):props+=f'(property {q("View"+str(i))} {q(val)} (at {round(mm(self.x)+x,4)} {round(mm(self.y)+y,4)} 0) (effects (font (size {1.52 if i==0 else 1.27} {1.52 if i==0 else 1.27})){"" if just=="center" else " (justify "+just+")"}))'
  root=uid(board+':root');item=f'(symbol (lib_id {q(key)}) (at {mm(self.x)} {mm(self.y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(board+":"+self.ref)}) {props} (instances (project {q("p2-"+board+"-readable-r")} (path "/{root}" (reference {q(self.ref)}) (unit 1)))))'
  return lib,item

class Block:
 def __init__(self,title,x,y,w,h,parts):self.title=title;self.rect=tuple(map(grid,[x,y,x+w,y+h]));self.parts=parts;self.components=[]
 def add(self,ref,x,y,orientation='h',sides=None):
  assert ref in self.parts,ref
  assert not any(c.ref==ref for c in self.components),ref
  c=Component(self.parts[ref],x,y,orientation,sides);self.components.append(c);return c

def segment_points(a,b):
 dx=(b[0]>a[0])-(b[0]<a[0]);dy=(b[1]>a[1])-(b[1]<a[1]);assert not(dx and dy)
 return [(a[0]+dx*i,a[1]+dy*i) for i in range(max(abs(a[0]-b[0]),abs(a[1]-b[1]))+1)]

class Router:
 def __init__(self,block):
  self.block=block;self.occupied=collections.defaultdict(lambda:collections.defaultdict(set));self.segments=[];self.obstacles=set();self.labels=[];self.notes=[];self.failed=[];self.connected=[]
  for c in block.components:
   a,b,z,w=c.bbox
   for x in range(a,z+1):
    for y in range(b,w+1):self.obstacles.add((x,y))
  self.ports=collections.defaultdict(list);self.protected={}
  for c in block.components:
   for pin in c.pins:
    self.protected[pin['end']]=pin['net'] or 'NC'
    self.protected[pin['anchor']]=pin['net'] or 'NC'
    if pin['net'] is None:continue
    net=pin['net'];self.ports[net].append(pin)
    self.addseg(pin['end'],pin['anchor'],net,stub=True)
 def addseg(self,a,b,net,stub=False):
  if a==b:return
  self.segments.append((a,b,net))
  pts=segment_points(a,b)
  for i,v in enumerate(pts):
   if i:self.occupied[v][net].add((pts[i-1][0]-v[0],pts[i-1][1]-v[1]))
   if i<len(pts)-1:self.occupied[v][net].add((pts[i+1][0]-v[0],pts[i+1][1]-v[1]))
 def search(self,start,goals,net):
  bx,by,bz,bw=self.block.rect;bx+=3;by+=14;bz-=3;bw-=3
  distance=lambda n:min(abs(n[0]-a)+abs(n[1]-b) for a,b in goals)
  q0=[];counter=itertools.count();first=(*start,0,0);heapq.heappush(q0,(distance(start),next(counter),0,first));dist={first:0};previous={}
  while q0:
   _,_,cost,s=heapq.heappop(q0)
   if cost!=dist[s]:continue
   x,y,ix,iy=s
   if (x,y) in goals and not any(n!=net for n in self.occupied[(x,y)]):
    path=[s[:2]]
    while s in previous:s=previous[s];path.append(s[:2])
    return path[::-1]
   for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
    nx,ny=x+dx,y+dy;v=(nx,ny)
    if not(bx<=nx<=bz and by<=ny<=bw):continue
    if v in self.protected and self.protected[v]!=net:continue
    if v in self.obstacles and v!=start and v not in goals:continue
    if any(n!=net for n in self.occupied[(x,y)]) and (dx,dy)!=(ix,iy):continue
    foreign=[dirs for n,dirs in self.occupied[v].items() if n!=net]
    if foreign:
     if len(foreign)>1:continue
     expected={(0,-1),(0,1)} if dx else {(-1,0),(1,0)}
     if foreign[0]!=expected:continue
    new=(*v,dx,dy);nc=cost+1+(2.5 if (ix,iy)!=(0,0) and (dx,dy)!=(ix,iy) else 0)+(8 if foreign else 0)
    if nc<dist.get(new,float('inf')):
     dist[new]=nc;previous[new]=s;heapq.heappush(q0,(nc+distance(v),next(counter),nc,new))
  return None
 def run(self,power_nets,cross_nets):
  for net,pins in sorted(self.ports.items(),key=lambda z:(-len(z[1]),z[0])):
   anchors=[p['anchor'] for p in pins]
   if net in power_nets and (net=='GND' or len(pins)>5):
    # Explicit common rails for adjacent capacitor/pull-up banks; distant power
    # pins use conventional named rails rather than wires through every block.
    pending=list(pins)
    for direction in [(0,-1),(0,1)]:
     ys=collections.defaultdict(list)
     for p in pending:
      if p['direction']==direction:ys[p['anchor'][1]].append(p)
     for y,group in ys.items():
      group.sort(key=lambda p:p['anchor'][0]);runs=[];run=[]
      for p in group:
       if run:
        points=segment_points(run[-1]['anchor'],p['anchor'])
        if any(v in self.obstacles or any(n!=net for n in self.occupied[v]) for v in points):runs.append(run);run=[]
       run.append(p)
      if run:runs.append(run)
      for run in runs:
       if len(run)>1:
        self.addseg(run[0]['anchor'],run[-1]['anchor'],net)
        self.labels.append((run[0]['anchor'],net,direction))
        pending=[p for p in pending if p not in run]
    self.labels.extend((p['anchor'],net,p['direction']) for p in pending);continue
   connected={anchors[0]};remaining=set(anchors[1:]);all_ok=True
   while remaining:
    start=min(remaining,key=lambda p:min(abs(p[0]-a)+abs(p[1]-b) for a,b in connected));remaining.remove(start)
    route=self.search(start,connected,net)
    if route:
     # Convert straight runs to segments. Crossings remain segment interiors.
     end=route[0];last=end;delta=None
     for v in route[1:]:
      d=(v[0]-last[0],v[1]-last[1])
      if delta is not None and d!=delta:self.addseg(end,last,net);end=last
      delta=d;last=v
     self.addseg(end,last,net);connected.update(route)
     self.connected.append(net)
    else:
     self.failed.append(net);all_ok=False;self.labels.append((start,net,next(p['direction'] for p in pins if p['anchor']==start)))
   if net in cross_nets or net in power_nets or len(pins)==1 or not all_ok:self.labels.append((pins[0]['anchor'],net,pins[0]['direction']))
  return self
