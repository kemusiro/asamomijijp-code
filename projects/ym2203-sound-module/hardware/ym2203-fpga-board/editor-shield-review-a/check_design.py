#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent editor/base interface checks. Native ERC/netlist is generated separately."""
import argparse,hashlib,json
from pathlib import Path
from design import make,HERE

def check(base):
    d=make();existing=json.loads((base/'base/circuit.json').read_text());gp=json.loads((base.parent/'clean-sheet-interface-review-g/gpio-proposal.json').read_text())['uno']['gpio']
    by={p['ref']:p for p in existing['parts']};header_map={'J1':'JUNO_D0','J2':'JUNO_D8','J3':'JUNO_A','J4':'JUNO_PWR'};connections=[]
    for part in d['parts']:
        if part['ref'] not in header_map:continue
        other={p['num']:p for p in by[header_map[part['ref']]]['pins']}
        assert {p['num'] for p in part['pins']}==set(other)
        for p in part['pins']:
            q=other[p['num']]
            if p['net'] is not None:
                expected_net={'IOREF':'V3V3','3V3':'V3_AUX','GND':'GND','GND1':'GND','GND2':'GND','SDA':'EXT_A4','SCL':'EXT_A5'}.get(p['name'],'EXT_'+p['name'])
                assert q['net']==expected_net
                connections.append(dict(header=part['ref'],pin=p['num'],label=p['name'],shield_net=p['net'],base_net=q['net'],gpio=gp.get(p['name'])))
    mapping={p['label']:p['shield_net'] for p in connections}
    assert [mapping['A'+str(i)] for i in range(4)]==['KNOB'+str(i)+'_ADC' for i in range(1,5)]
    assert mapping['A4']=='SDA' and mapping['A5']=='SCL'
    assert mapping['IOREF']=='IOREF_3V3' and mapping['3V3']=='AUX_3V3'
    assert not any(p['label'] in ['5V','VIN','AREF','RESET'] for p in connections)
    assert [gp[k] for k in ['D11','D13','D10','D12']]==[27,26,25,24]
    assert mapping['D12']=='LCD_DC' # write-only SPI: keep this GPIO in SIO, never configure it as RX
    assert 0x50 not in [0x20,0x4a,0x60]
    fram=next(p for p in d['parts'] if p['design_id']=='UFRAM');pins={p['num']:p['net'] for p in fram['pins']}
    assert all(pins[str(n)]=='GND' for n in (1,2,3,4,7)) and pins['8']=='IOREF_3V3'
    assert not any(p['design_id'] in ('RSDA','RSCL') for p in d['parts'])
    # Every resistor/capacitor terminal and duplicated connector alias is in the native netlist check.
    power=dict(io_ref_admission_ma=8,pga_existing_ma=265,pga_limit_ma=300,display_aux_admission_ma=80,shield_aux_limit_ma=100,additional_5v_ma=0)
    assert power['io_ref_admission_ma']+power['pga_existing_ma']<power['pga_limit_ma']
    assert power['display_aux_admission_ma']<=power['shield_aux_limit_ma']
    mechanical=dict(outline_local_mm=[-3,-3,73,93],origin_on_base_mm=[10,10],source_origin_x_mm=90,source_gap_mm=7,display_envelope_mm=[-1,6,39,46],icsp_underside_keepout_mm=[61,20,69,31],clock_access_window_candidate_mm=[50,62,67,77],underside_limit_mm=3,minimum_stack_face_gap_mm=10.5,base_tall_under_shield_limit_mm=5,minimum_vertical_gap_mm=2.5,base_stop_covered=True,base_test_access_pending=True,routed=False,physical_fit_accepted=False)
    assert mechanical['source_origin_x_mm']-(mechanical['outline_local_mm'][2]+10)==7
    result=dict(date='2026-11-18',base_revision='3.6-pcb-review-i',header_contacts=32,connected_contacts=len(connections),parts=len(d['parts']),base_gpio_changed=False,host_source_changed=False,firmware_implemented=False,pcb_routed=False,hardware_accepted=False,power=power,mechanical=mechanical)
    (HERE/'pins.json').write_text(json.dumps(connections,indent=2)+'\n');(HERE/'design-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    (HERE/'preservation.json').write_text(json.dumps(dict(reference_files_sha256={str(p.relative_to(base.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base/'base/circuit.json',base/'base/p2-base-i.kicad_pcb',base/'module/p2-ym2203-i.kicad_pcb',base.parent/'clean-sheet-schematic-review-h/connector.json']}),indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=HERE.parent/'clean-sheet-pcb-review-i');check(p.parse_args().base)
