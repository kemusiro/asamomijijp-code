#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional source-bundle Yosys mapping sanity check; never a Diamond/STA result."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--yosys',default='yosys');a=p.parse_args();root=a.bundle.resolve();manifest=json.loads((root/'bundle-manifest.json').read_text())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for name,digest in manifest['files_sha256'].items():
 if sha(root/name)!=digest:raise ValueError('Bundle modified: '+name)
work=root/'oss-check'
if work.exists():raise FileExistsError('Keep previous evidence: use a fresh bundle')
work.mkdir();script=work/'synth.ys';mapped=work/'mapped.json';log=work/'synthesis.log'
script.write_text('read_verilog -sv '+' '.join(json.dumps(str(f)) for f in sorted((root/'src').glob('*.sv')))+'\nsynth_ecp5 -top revc_ulx3s_diamond_top -json '+json.dumps(str(mapped))+'\ncheck -assert\nstat\n')
subprocess.run([a.yosys,'-ql',str(log),str(script)],check=True)
m=json.loads(mapped.read_text())['modules']['revc_ulx3s_diamond_top'];assert sum(len(p['bits']) for p in m['ports'].values())==49
for name,constant in [('host_scl','0'),('host_sda','0'),('si_scl','0'),('si_sda','0'),('usb_dp_bias','1')]:
 b=[c for c in m['cells'].values() if c['type']=='$_TBUF_' and c['connections']['Y']==m['ports'][name]['bits']];assert len(b)==1 and b[0]['connections']['A']==[constant],name
b=[c for c in m['cells'].values() if c['type']=='TRELLIS_IO' and c['connections']['B']==m['ports']['usb_dn_bias']['bits']];assert len(b)==1 and b[0]['connections']['T']==['1']
pll=[c for c in m['cells'].values() if c['type']=='EHXPLLL'];assert len(pll)==1
for n,v in [('CLKI_DIV',1),('CLKFB_DIV',4),('CLKOP_DIV',12)]:assert int(pll[0]['parameters'][n],2)==v
r={'kind':'Additional Yosys source-bundle mapping; no Synplify, PAR or vendor STA','all_passed':True,'physical_pads':49,'open_drain_and_usb_bias_checked':True,'pll_ratio_checked':[1,4,12],'vendor_execution':False,'timing_closed':False,'bundle_manifest_sha256':sha(root/'bundle-manifest.json'),'mapped_sha256':sha(mapped),'log_sha256':sha(log),'yosys_version':subprocess.run([a.yosys,'-V'],check=True,capture_output=True,text=True).stdout.strip(),'warning_scope':'Yosys memory-to-register lowering and limited generic tri-state support; final mapped open-drain and native D-minus OBZ checked explicitly'}
(work/'summary.json').write_text(json.dumps(r,indent=2)+'\n');print('PASS OSS source mapping sanity only; no Diamond timing result')
