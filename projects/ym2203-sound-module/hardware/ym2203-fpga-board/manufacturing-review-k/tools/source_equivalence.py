#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare physical electrical geometry of CAM work copies with preserved source boards."""
from pathlib import Path
import argparse,json,pcbnew as P

def sig(b):
 def xy(v):return [v.x,v.y]
 return {
  'layers':b.GetCopperLayerCount(),
  'pads':sorted((f.GetReference(),p.GetNumber(),p.GetNetname(),xy(p.GetPosition()),xy(p.GetSize()),xy(p.GetDrillSize()),p.GetOrientationDegrees(),p.GetLayerSet().FmtHex()) for f in b.GetFootprints() for p in f.Pads()),
  'tracks':sorted((t.GetNetname(),t.GetLayer(),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth(P.F_Cu) if isinstance(t,P.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,P.PCB_VIA) else 0) for t in b.GetTracks()),
  'zones':sorted((z.GetNetname(),z.GetLayerSet().FmtHex(),z.Outline().Format()) for z in b.Zones())
 }
def main():
 a=argparse.ArgumentParser();a.add_argument('--hardware-root',type=Path,required=True);a.add_argument('--work',type=Path,required=True);args=a.parse_args();cfg=json.loads((args.work/'boards.json').read_text());result={}
 for key,q in cfg.items():
  source=P.LoadBoard(str(args.hardware_root/q['dir']/(q['name']+'.kicad_pcb')));copy=P.LoadBoard(str(args.work/'cad'/key/(q['name']+'.kicad_pcb')))
  sa,ca=sig(source),sig(copy)
  for k in sa:assert sa[k]==ca[k],(key,k,'physical geometry changed')
  result[key]={'physical_pad_track_zone_geometry_unchanged':True,'pads':len(sa['pads']),'tracks_and_vias':len(sa['tracks']),'copper_layers':sa['layers']}
 (args.work/'source-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: original/CAM-copy physical geometry identical for',len(result),'variants; only export-copy metadata may differ')
if __name__=='__main__':main()
