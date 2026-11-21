# SPDX-License-Identifier: MIT
"""Independent Gerbonara comparison of exported CAM to native KiCad geometry."""
import collections, hashlib, json, sys, warnings
from pathlib import Path
from gerbonara import GerberFile, ExcellonFile, LayerStack
from gerbonara.utils import MM

root=Path(sys.argv[1]); natives=json.loads((root/'native-geometry.json').read_text()); report={}
def rounded(row):return tuple(round(v,4) for v in row)
def match_holes(rows, expected):
 # KiCad metric Excellon uses three decimal places (Gerber uses six).
 # Match each native hole once, retaining a maximum 0.6 um rounding tolerance.
 assert len(rows)==len(expected),'Hole/slot count changed'
 remaining=list(expected);maximum=0
 for row in rows:
  matches=[(i,max(abs(a-b) for a,b in zip(row,w))) for i,w in enumerate(remaining) if max(abs(a-b) for a,b in zip(row,w))<=0.0006]
  assert len(matches)==1,('Non-unique or displaced hole',row)
  i,error=matches[0];maximum=max(maximum,error);remaining.pop(i)
 return round(maximum,6)
for key,native in natives.items():
 path=root/'artifacts'/key/'gerbers'; name=native['name']; images=root/'artifacts'/key/'preview';images.mkdir(exist_ok=True)
 warning_text=[]
 with warnings.catch_warnings(record=True) as ws:
  warnings.simplefilter('always')
  stack=LayerStack.open(path)
  outline=GerberFile.open(path/(name+'-Edge_Cuts.gm1'))
  edges=[]
  for ob in outline.objects:
   assert type(ob).__name__=='Line','Outline must contain only four straight edges'
   edges.append(sorted([[ob.x1,ob.y1],[ob.x2,ob.y2]]))
  assert sorted(edges)==sorted(native['edges'])
  assert len(edges)==4
  expected_layers={('top','copper'),('bottom','copper'),('top','mask'),('bottom','mask'),('top','silk'),('bottom','silk'),('mechanical','outline')}
  if native['copper_layers']==4:expected_layers|={('inner_1','copper'),('inner_2','copper')}
  assert set(stack.graphic_layers)==expected_layers
  counts={}
  for kind in ['PTH','NPTH']:
   dr=ExcellonFile.open(path/(name+'-'+kind+'.drl'),plated=(kind=='PTH'))
   rows=[]
   for ob in dr.objects:
    if type(ob).__name__=='Flash':ends=[[ob.x,ob.y],[ob.x,ob.y]]
    else:
     assert type(ob).__name__=='Line';ends=sorted([[ob.x1,ob.y1],[ob.x2,ob.y2]])
    rows.append([ob.aperture.diameter,*ends[0],*ends[1]])
   error=match_holes(rows,native['holes'][kind])
   counts[kind]={'holes_and_slots':len(rows),'slots':sum(r[1:3]!=r[3:5] for r in rows),'tools_mm':sorted(set(r[0] for r in rows)),'max_coordinate_rounding_mm':error}
  for side in ([] if '--no-previews' in sys.argv else ['top','bottom']):
   svg=stack.to_pretty_svg(side=side,margin=2)
   (images/(side+'.svg')).write_text(str(svg))
  warning_text=sorted(set('G90 header statement found after end of header' if 'G90 header statement found after end of header' in str(w.message) else str(w.message) for w in ws))
  allowed=['G90 header statement found after end of header','Aperture definition using macro RoundRect has more parameters than the macro uses.','Layer "top paste" not found.','Layer "bottom paste" not found.']
  assert all(any(t.startswith(a) for a in allowed) for t in warning_text),warning_text
 xs=[v[0] for e in edges for v in e];ys=[v[1] for e in edges for v in e]
 job=json.loads((path/(name+'-job.gbrjob')).read_text());assert job['GeneralSpecs']['LayerNumber']==native['copper_layers'];assert job['GeneralSpecs']['BoardThickness']==1.6
 assert 'MaterialStackup' not in job, 'Do not request the KiCad placeholder stackup'
 # KiCad job extents include the outline stroke; physical board follows centreline.
 size=[max(xs)-min(xs),max(ys)-min(ys)]
 assert all(abs(a-b-native['outline_stroke_mm'])<1e-5 for a,b in zip(job['GeneralSpecs']['Size'].values(),size))
 report[key]={'outline_mm':size,'outline_segments':4,'copper_layers':native['copper_layers'],'drills':counts,'min_track_mm':native['min_track_mm'],'via_drills_mm':native['via_drills_mm'],'erc':0,'drc':0,'unconnected':0,'parity':0,'cam_matches_native':True,'parser_notes':warning_text}
 for typ in ['erc','drc']:
  data=json.loads((path.parent/(typ+'.json')).read_text())
  if typ=='erc':assert not any(s['violations'] for s in data['sheets'])
  else:assert not any(data[k] for k in ['violations','unconnected_items','schematic_parity'])
(root/'cam-verification.json').write_text(json.dumps({'tools':{'kicad':'10.0.5','gerbonara':'1.6.3'},'boards':report},indent=2)+'\n')
print(json.dumps(report,indent=2))
