"""Audit the approved single-board circuit, native KiCad reports and PCB geometry."""
from pathlib import Path
from collections import defaultdict
import json, math, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'rev-c'


def main():
    d=json.loads((OUT/'design.json').read_text());assert d['gpio_approved']
    approved={**{n:f'D{n}' for n in range(8)},8:'A0',9:'RESET_RELEASE',10:'I2S_DATA',11:'I2S_BCLK',12:'I2S_LRCK',
      13:'CS_N',14:'WR_N',15:'RD_N',16:'FM_SD',17:'FM_CLK',18:'FM_SH',19:'LINE_ALLOW',20:'HOST_SDA',
      21:'HOST_SCL',22:'ARM',26:'DAC_ALLOW',28:'IRQ_N'}
    assert {p['gpio']:p['signal'] for p in d['gpio']}==approved
    assert len({p['pico_pin'] for p in d['gpio']})==25 and d['reserved_gpio']==[27]
    name='ym2203-single';folder=OUT/name;model=d['boards'][name];parts={p['ref']:p for p in model['parts']}
    pins={ref:{p['num']:p['net'] for p in part['pins']} for ref,part in parts.items()}
    expected=defaultdict(set)
    for ref,part in parts.items():
      for pin in part['pins']:
        if pin['net'] is not None:expected[pin['net']].add((ref,pin['num']))
    actual={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node') if not p.attrib['ref'].startswith('#')}
      for n in ET.parse(folder/'netlist.xml').findall('./nets/net')}
    actual={k:v for k,v in actual.items() if v and not k.startswith('unconnected-')}
    assert dict(expected)==actual,'schematic pin model mismatch'
    g=json.loads((folder/'geometry.json').read_text());copper=defaultdict(set)
    for pad in g['pads']:
      if pad['net'] and not pad['net'].startswith('unconnected-'):copper[pad['net'].lstrip('/')].add((pad['ref'],pad['num']))
    assert dict(copper)==dict(expected),'PCB pad net mismatch'
    erc=json.loads((folder/'erc.json').read_text());drc=json.loads((folder/'drc.json').read_text())
    ev=[v for sheet in erc['sheets'] for v in sheet['violations']]
    assert not ev,('ERC',ev)
    for key in ['violations','unconnected_items','schematic_parity']:assert not drc[key],(key,drc[key])
    assert len(g['tracks'])>0 and min(t['width'] for t in g['tracks'])>=.18-1e-5
    assert d['power_source']=='dedicated_usb_c_5v'
    assert pins['JPOWER']=={'1':'USB_VBUS','2':None,'3':None,'4':'GND','5':'USB_CC1','6':'USB_CC2','7':'GND'}
    assert pins['F1']=={'1':'USB_VBUS','2':'USB_FUSED'}
    assert pins['U11']=={'1':'USB_FUSED','2':'GND','3':'USB_FUSED','4':'USB_CT','5':None,'6':'+5V'}
    for net in ['USB_CC1','USB_CC2']:
      rd=[p for p in parts.values() if p['value']=='5.1k 1%' and {x['net'] for x in p['pins']}=={net,'GND'}]
      assert len(rd)==1
    assert any(p['value']=='1u 10V X7R' and {x['net'] for x in p['pins']}=={'USB_FUSED','GND'} for p in parts.values())
    assert any(p['value']=='10n 25V X7R' and {x['net'] for x in p['pins']}=={'USB_CT','GND'} for p in parts.values())
    usb=[p for p in g['pads'] if p['ref']=='JPOWER'];assert len(usb)==11
    for i in range(7):
      assert any(p['num']==str(i+1) and abs(p['x']-(40.62-i*2.54))<1e-5 and abs(p['y']-108.34)<1e-5 for p in usb)
    for n,x in [('1',40.62),('7',25.38)]:
      for y in [115.96,118.5]:assert any(p['num']==n and abs(p['x']-x)<1e-5 and abs(p['y']-y)<1e-5 for p in usb)
    sw={p['num']:p for p in g['pads'] if p['ref']=='U11'}
    assert sw['1']['x']<sw['6']['x'] and sw['1']['y']<sw['3']['y'] and sw['6']['y']<sw['4']['y']
    assert pins['D1']=={'1':'VSYS','2':'+5V'} and pins['A1']['39']=='VSYS' and pins['A1']['40'] is None
    assert pins['A1']['32'] is None and pins['A1']['36']=='+3V3'
    for item in d['gpio']:assert pins['A1'][str(item['pico_pin'])]==item['signal']
    assert [pins['U1'][str(p)] for p in [40,2,3,4,5,6,7,8]]==[f'Y_D{n}' for n in range(8)]
    assert {p:pins['U1'][p] for p in ['1','17','21','22','23','24','25','34','35','36','37','38','39']}=={
      '1':'GND','17':'GND','21':'+5V','22':'Y_SH','23':'Y_SD','24':'Y_RESET_N','25':'Y_IRQ',
      '34':'Y_CS_N','35':'Y_WR_N','36':'Y_RD_N','37':'Y_A0','38':'CLK4','39':'Y_CLK'}
    assert [pins['A2'][str(p)] for p in [1,3,6,7,8,9,13,14,15,17,19,20]]==[
      '+3V3','GND','DAC_L',None,'+3V3','GND','DAC_BCK','DAC_DIN','DAC_LRCK','DAC_XSMT','GND','+3V3']
    for ref in ['A3','A4']:
      assert {p:pins[ref][p] for p in ['1','2','3','12','13','22','23','24']}=={
        '1':'+3V3','2':'OE_WRITE_N' if ref=='A3' else 'GND','3':'+3V3','12':'GND','13':'GND','22':'GND','23':'+5V','24':'+3V3'}
    assert pins['U2']['19']=='OE_READ_N' and pins['U2']['20']=='+3V3'
    assert pins['U3']['19']=='GND' and pins['U3']['20']=='+3V3'
    assert [pins['U10'][str(p)] for p in [1,2,3,4,5,6,9,10,8]]==[
      'ARM','RESET_RELEASE','RESET_N','ARM','DAC_ALLOW','DAC_XSMT','ARM','LINE_ALLOW','LINE_RUN']
    assert pins['RN2']=={str(i+1):n for i,n in enumerate(['GND','ARM','A0','RESET_RELEASE','DAC_ALLOW','LINE_ALLOW','FM_SD','FM_CLK','FM_SH'])}
    assert pins['Q1']=={'1':'MUTE_BASE','2':'GND','3':'MUTE_5V'}
    assert {p:pins['U9'][p] for p in ['6','7','8','11','12','13','14','16']}=={
      '6':'GND','7':'GND','8':'GND','11':'MUTE_5V','12':'MIX_MONO','13':'VREF','14':'MUTED_MONO','16':'+5V'}
    assert pins['U8']=={'1':'VREF','2':'VREF','3':'REF_RAW','4':'GND','5':'VREF','6':'SUM_MONO','7':'MIX_MONO','8':'+5V'}
    assert pins['JLINE']=={'2':'LINE_R','3':'GND','4':'LINE_L'}
    assert 'JVOL' not in pins
    assert pins['RV1']=={'1':'GND','2':'VOL_L','3':'OUT_AC','4':'GND','5':'VOL_R','6':'OUT_AC'}
    for ch in ['L','R']:
      resistors=[p for p in parts.values() if p['value']=='100' and {x['net'] for x in p['pins']}=={'VOL_'+ch,'LINE_'+ch}]
      assert len(resistors)==1
    # Actual hole coordinates, contact chirality and duplicated TIP legs.
    rv={p['num']:p for p in g['pads'] if p['ref']=='RV1'}
    for n,(x,y) in enumerate([(93.5,113.5),(96,113.5),(98.5,113.5),(93.5,111),(96,111),(98.5,111)],1):
      assert abs(rv[str(n)]['x']-x)<1e-5 and abs(rv[str(n)]['y']-y)<1e-5
      assert rv[str(n)]['drill']==1.0
    jack=[p for p in g['pads'] if p['ref']=='JLINE']
    for num,x,y in [('4',142.1,116.5),('4',147.9,116.5),('2',142.75,109),('3',147.25,109),('',142.5,113),('',147.5,113)]:
      assert any(p['num']==num and abs(p['x']-x)<1e-5 and abs(p['y']-y)<1e-5 for p in jack)
    assert len(jack)==6
    assert [pins['RN5'][str(i)] for i in [1,2,3,4]]==['GND','SSG_A','SSG_B','SSG_C']
    assert len([p for p in parts.values() if p['value'].startswith('MCP6022')])==1
    assert not any(p['value'].startswith('MCP23017') for p in parts.values()) and 'JMOD' not in parts
    bypass=[]
    for part in parts.values():
      if not part.get('near'):continue
      ref,pn=part['near'];a=next(p for p in g['pads'] if p['ref']==ref and p['num']==str(pn));b=next(p for p in g['pads'] if p['ref']==part['ref'] and p['num']=='1')
      dist=math.hypot(a['x']-b['x'],a['y']-b['y']);assert dist<=8,(part['ref'],ref,pn,dist)
      bypass.append(dict(cap=part['ref'],supply=ref+'.'+str(pn),distance_mm=round(dist,2)))
    q={p['num']:p for p in g['pads'] if p['ref']=='Q1'}
    cross=(q['2']['x']-q['1']['x'])*(q['3']['y']-q['1']['y'])-(q['2']['y']-q['1']['y'])*(q['3']['x']-q['1']['x'])
    assert cross<0,'SOT23 top view mirrored'
    placement=json.loads((folder/'placement.json').read_text())
    assert len(placement)==len(parts)
    for i,a in enumerate(placement):
      x1,y1,x2,y2=a['courtyard'];limit=120.5 if a['ref']=='JLINE' else 119.5 if a['ref']=='JPOWER' else 119.2
      assert min(x1,y1)>=.8 and x2<=159.2 and y2<=limit
      for b in placement[i+1:]:
        u1,v1,u2,v2=b['courtyard'];assert not(x1<u2 and x2>u1 and y1<v2 and y2>v1),(a['ref'],b['ref'],'courtyard overlap')
    report=dict(revision='C',date='2026-10-18',result='pass',gpio_count=25,reserved_gpio=[27],board_size_mm=[160,120],
      physical_objects=len(parts),electrical_nets=len(expected),track_segments=len(g['tracks']),vias=len(g['vias']),
      erc_errors=0,erc_warnings=0,drc_errors=0,drc_warnings=0,unconnected=0,schematic_parity_issues=0,
      bypass_checks=bypass,checks=['Approved GPIO and Pico physical pin map','All schematic physical pin sets','All PCB pad nets',
      'YM2203C native pins','AE-LLCNV module pin numbering','PCM5102A native pins','Power path and diode polarity',
      'USB-C module CN2/support holes, separate Rd and unconnected data pins','TPS22918 pinout and soft-start passives',
      'Hardware ARM gate pins and startup pulldowns','Mono mixer and independent L/R output resistors','MCP6022 count and absence of expander',
      'SOT23 top-view chirality','RK097 mounting holes and CW pinout','ST-005-G contacts, duplicated TIP and locating holes',
      'Courtyards nonoverlapping; explicit edge-mounted jack exception','Supply bypass placement','KiCad ERC and DRC with schematic parity'],
      hardware_tested=False,firmware_implemented=False,remaining=['Physical module, socket and capacitor fit','Loaded supply voltage and current',
      'PIO FM capture and PCM sample-rate conversion','I2C slave and class-compliant USB-MIDI firmware','Real bus timing and buffer turnaround',
      'FM/SSG balance, clipping, noise and startup pops'])
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
