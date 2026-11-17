#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run with KiCad's pcbnew Python. Pad identity/UNO positions, not mechanical-fit acceptance."""
import argparse,json,os,sys
from pathlib import Path
import pcbnew as P
from design import HERE,make

def run(library_root):
    parts=make()['parts'];checks=0;contacts=0
    geom=json.loads((HERE/'geometry/uno.json').read_text())['derived_board_header_facts']
    references={'J1':'JUNO_D0','J2':'JUNO_D8','J3':'JUNO_A','J4':'JUNO_PWR'}
    for p in parts:
        lib,name=p['footprint'].split(':');path=HERE/'ED2.pretty' if lib=='ED2' else library_root/(lib+'.pretty')
        f=P.FootprintLoad(str(path),name);assert f is not None,p['footprint']
        assert {q.GetNumber() for q in f.Pads() if q.GetNumber()}=={q['num'] for q in p['pins']},p['ref']
        checks+=len(list(f.Pads()))
        if p['ref'] in references:
            expect={str(x['pin']):[x['x_mm'],x['y_mm']] for x in geom if x['ref']==references[p['ref']]}
            for q in f.Pads():
                xy=[P.ToMM(q.GetPosition().x),P.ToMM(q.GetPosition().y)]
                assert max(abs(a-b) for a,b in zip(xy,expect[q.GetNumber()]))<.00001
                contacts+=1
    assert contacts==32
    result=dict(kicad=P.GetBuildVersion(),footprint_pin_sets=len(parts),physical_pads=checks,uno_contacts=contacts,scope='standard footprint identities and original UNO coordinates; no routing/height/purchased-part fit acceptance')
    (HERE/'footprint-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    fallback='/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints' if sys.platform=='darwin' else '/usr/share/kicad/footprints'
    p=argparse.ArgumentParser();p.add_argument('--library-root',type=Path,default=os.environ.get('KICAD10_FOOTPRINT_DIR',fallback));run(p.parse_args().library_root)
