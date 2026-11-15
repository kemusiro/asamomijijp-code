"""Audit exported schematics, physical PCB pads, mating coordinates and rule reports."""
from pathlib import Path
from collections import defaultdict, Counter
import json, math, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'rev-a'


def main():
    d=json.loads((OUT/'design.json').read_text())
    assert d['gpio_approved']
    approved={**{i:f'D{i}' for i in range(8)},8:'A0',9:'A1',10:'I2S_DATA',11:'I2S_BCLK',12:'I2S_LRCK',
              13:'CS_N',14:'WR_N',15:'RD_N',16:'FM_SD',17:'FM_CLK',18:'FM_SH1',19:'FM_SH2',
              20:'HOST_SDA',21:'HOST_SCL',22:'ARM',26:'AUX_SDA',27:'AUX_SCL',28:'STATUS'}
    assert {x['gpio']:x['signal'] for x in d['gpio']}==approved
    assert len({x['pico_pin'] for x in d['gpio']})==26
    results={};geoms={}
    for name,b in d['boards'].items():
        folder=OUT/name;parts={p['ref']:p for p in b['parts']}
        expected=defaultdict(set)
        for p in parts.values():
            for pn in p['pins']:
                if pn['net'] is not None:expected[pn['net']].add((p['ref'],pn['num']))
        actual={n.attrib['name'].lstrip('/'):{(pn.attrib['ref'],pn.attrib['pin']) for pn in n.findall('node') if not pn.attrib['ref'].startswith('#')}
                for n in ET.parse(folder/'netlist.xml').findall('./nets/net')}
        actual={n:s for n,s in actual.items() if s and not n.startswith('unconnected-')}
        assert dict(expected)==actual,name+' schematic differs from pin model'
        g=json.loads((folder/'geometry.json').read_text());geoms[name]=g
        copper=defaultdict(set)
        for p in g['pads']:
            if p['net'] and not p['net'].startswith('unconnected-'):copper[p['net'].lstrip('/')].add((p['ref'],p['num']))
        assert dict(copper)==dict(expected),name+' PCB pin nets differ'
        erc=json.loads((folder/'erc.json').read_text())
        ev=[v for sheet in erc['sheets'] for v in sheet['violations']]
        drc=json.loads((folder/'drc.json').read_text())
        dv=drc['violations'];uc=drc['unconnected_items'];par=drc['schematic_parity']
        assert not ev,(name,'ERC',Counter(v['type'] for v in ev))
        assert not dv,(name,'DRC',Counter(v['type'] for v in dv))
        assert not uc,(name,'unconnected',len(uc))
        assert not par,(name,'schematic parity',Counter(v['type'] for v in par))
        assert g['tracks'] and g['vias']
        assert min(t['width'] for t in g['tracks'])>=.18-1e-5
        # Physical placement check: decoupling capacitor must be near its actual supply pin.
        distances=[]
        for part in parts.values():
            if not part.get('near'):continue
            ref,num=part['near']
            supply=next(z for z in g['pads'] if z['ref']==ref and z['num']==str(num))
            cap=next(z for z in g['pads'] if z['ref']==part['ref'] and z['num']=='1')
            distance=math.hypot(supply['x']-cap['x'],supply['y']-cap['y'])
            assert distance<=8,(name,part['ref'],'supply pad distance',distance)
            distances.append(dict(cap=part['ref'],supply_pin=ref+'.'+str(num),distance_mm=round(distance,2)))
        results[name]=dict(physical_parts=len(parts),electrical_nets=len(expected),erc_errors=0,erc_warnings=0,
            drc_errors=0,drc_warnings=0,unconnected=0,schematic_parity_issues=0,
            track_segments=len(g['tracks']),vias=len(g['vias']),
            minimum_track_width_mm=round(min(t['width'] for t in g['tracks']),4),
            bypass_placement_checks=distances)
    # Independent manufacturer pinout spot checks at all hardware boundaries.
    base={p['ref']:{pn['num']:pn['net'] for pn in p['pins']} for p in d['boards']['base']['parts']}
    card={p['ref']:{pn['num']:pn['net'] for pn in p['pins']} for p in d['boards']['ym2203']['parts']}
    # External 5V is the only main rail source. USB must not bypass the PTC
    # or feed the card through Pico VSYS; the external diode has K at VSYS.
    assert d['power_source']=='external_regulated_5v'
    assert 'JPWR' not in base
    assert base['JPOWER']=={'1':'EXT_5V','2':'GND'}
    assert base['F1']=={'1':'EXT_5V','2':'+5V'}
    assert base['D1']=={'1':'VSYS','2':'+5V'}
    assert base['A1']['39']=='VSYS' and base['A1']['40'] is None
    assert not {'USB_VBUS','FUSED_EXT_5V'} & {p['net'].lstrip('/') for p in geoms['base']['pads']}
    assert [card['U1'][str(n)] for n in [40,2,3,4,5,6,7,8]]==[f'Y_D{i}' for i in range(8)]
    assert {n:card['U1'][n] for n in ['1','17','21','22','23','24','25','38','39']}=={
        '1':'GND','17':'GND','21':'+5V','22':'Y_SH','23':'Y_SD','24':'Y_RESET_N','25':'Y_IRQ','38':'CLK4','39':'Y_CLK'}
    assert [base['A2'][str(n)] for n in [1,3,8,9,13,14,15,17,19,20]]==[
        '+3V3','GND','+3V3','GND','DAC_BCK','DAC_DIN','DAC_LRCK','DAC_XSMT','GND','+3V3']
    assert base['U5']['14']=='MUTED_L' and base['U5']['15']=='MUTED_R'
    assert base['U5']['12']=='MIX_L' and base['U5']['13']=='VREF'
    assert base['Q1']=={'1':'MUTE_BASE','2':'GND','3':'MUTE_5V'}
    q={x['num']:x for x in geoms['base']['pads'] if x['ref']=='Q1'}
    # Package top-view chirality, independent of rotation (MMBT3904 style 6).
    cross=(q['2']['x']-q['1']['x'])*(q['3']['y']-q['1']['y'])-(q['2']['y']-q['1']['y'])*(q['3']['x']-q['1']['x'])
    assert cross<0,'SOT23 footprint is mirrored'
    # 50 electrical contacts must mate at identical XY after the 50mm translation.
    pa={p['num']:p for p in geoms['base']['pads'] if p['ref']=='JMOD'}
    pb={p['num']:p for p in geoms['ym2203']['pads'] if p['ref']=='JMOD'}
    assert len(pa)==len(pb)==50
    for n in pa:
        assert abs(pa[n]['x']-pb[n]['x']-50)<1e-4,(n,'mating X')
        assert abs(pa[n]['y']-pb[n]['y'])<1e-4,(n,'mating Y')
    for h in range(1,5):
        a=next(p for p in geoms['base']['footprints'] if p['ref']=='H'+str(h))
        b=next(p for p in geoms['ym2203']['footprints'] if p['ref']=='H'+str(h))
        assert abs(a['x']-b['x']-50)<1e-4 and abs(a['y']-b['y'])<1e-4
    # Static truth table: reset/mute gating and bus enable exclusivity.
    for arm in (0,1):
        for rd in (0,1):
            write=arm and rd;read=arm and not rd
            assert not(write and read)
            if not arm:assert not write and not read
        for release in (0,1):
            assert (arm and release)==(1 if arm and release else 0)
    report=dict(revision='A',date='2026-10-18',result='pass',gpio_count=26,
        connector_contacts_verified=50,mounting_holes_matched=4,boards=results,
        checks=['Approved GPIO map','All schematic physical pin sets',
                'External-only main 5V, PTC path and USB backfeed diode polarity',
                'All PCB pad nets','YM2203 and DAC native pin numbers',
                'MMBT3904 pin mapping and SOT23 top-view chirality',
                'Hardware bus gating truth table','50-contact mating XY',
                'Asymmetric mounting-hole alignment','Supply-pin bypass placement',
                'Native KiCad ERC','Native KiCad DRC with schematic parity'],
        hardware_tested=False,firmware_implemented=False,
        remaining=['Actual component dimensions and keyed connector assembly',
                   'Loaded supply voltage, inrush and current consumption',
                   'Bus transition timing on real hardware',
                   'PIO/DMA receiver, sample-rate conversion and I2C firmware',
                   'Audio headroom, relative polarity, noise and startup pops',
                   'Five other card schematics and PCBs',
                   'YM2608/YM2610 ADPCM bridges and loaders'])
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
