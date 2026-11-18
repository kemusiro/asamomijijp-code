#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read native KiCad boards; never save, re-fill or alter design data."""
import argparse,collections,hashlib,json
from pathlib import Path
import pcbnew as P

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(hardware):
 boards={};inputs={}
 for key,rel in [('base','clean-sheet-pcb-review-j/base/p2-base-j'),('module','clean-sheet-pcb-review-j/module/p2-ym2203-i')]:
  pcb=hardware/(rel+'.kicad_pcb')
  for suffix in ['.kicad_pcb','.kicad_sch','.kicad_pro']:
   f=hardware/(rel+suffix);inputs[str(f.relative_to(hardware))]=digest(f)
  b=P.LoadBoard(str(pcb));layers={};nets={};vias=collections.Counter();zone_info=[]
  for t in b.GetTracks():
   if isinstance(t,P.PCB_VIA):vias[round(P.ToMM(t.GetDrillValue()),4)]+=1;continue
   layer=t.GetLayerName();name=t.GetNetname();length=P.ToMM(t.GetLength())
   z=layers.setdefault(layer,{'segments':0,'length_mm':0});z['segments']+=1;z['length_mm']+=length
   n=nets.setdefault(name,{'layers':set(),'segments':0,'length_mm':0});n['layers'].add(layer);n['segments']+=1;n['length_mm']+=length
  for z in layers.values():z['length_mm']=round(z['length_mm'],4)
  for z in b.Zones():zone_info.append({'net':z.GetNetname(),'layers':[b.GetLayerName(l) for l in z.GetLayerSet().Seq() if l in [P.F_Cu,P.In1_Cu,P.In2_Cu,P.B_Cu]]})
  sensitive={}
  names=['USB_DP','USB_DM','ADC_L','ADC_R','ADC_VREF','DAC_DIN','DAC_I2S_DATA','MOD_I2S_DATA','AUDIO_L','AUDIO_R','Y_SD','Y_SH','Y_CLK','Y_PHI_M','STOP_N','TEST_N']
  for name in names:
   if name in nets:
    z=nets[name];sensitive[name]={'layers':sorted(z['layers']),'length_mm':round(z['length_mm'],4),'segments':z['segments']}
  inner=sorted(n for n,z in nets.items() if 'In2.Cu' in z['layers'])
  inner_only=sorted(n for n,z in nets.items() if z['layers']=={'In2.Cu'})
  boards[key]={'source_pcb':rel+'.kicad_pcb','copper_layers':b.GetCopperLayerCount(),'track_layers':layers,'routed_nets':len(nets),'nets_using_inner2_including_power':inner,'nets_entirely_on_inner2':inner_only,'via_drills_mm_counts':{str(k):v for k,v in sorted(vias.items())},'zones':zone_info,'sensitive_net_routes':sensitive}
 for name,sha in inputs.items():assert digest(hardware/name)==sha,'Input changed during read'
 return {'schema_version':1,'checked':'2026-11-18','tool':'KiCad pcbnew '+P.GetBuildVersion(),'scope':'Existing review J/I native track inventory only. No two-layer placement, routing, DRC or electrical/thermal acceptance. Zone presence does not prove continuity.','inputs_sha256':inputs,'boards':boards,'cad_written':False}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 r=audit(a.hardware_root);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:{'layers':v['copper_layers'],'track_layers':v['track_layers'],'inner2_nets':len(v['nets_using_inner2_including_power']),'inner_only_nets':v['nets_entirely_on_inner2'],'vias':v['via_drills_mm_counts']} for k,v in r['boards'].items()},ensure_ascii=False))
if __name__=='__main__':main()
