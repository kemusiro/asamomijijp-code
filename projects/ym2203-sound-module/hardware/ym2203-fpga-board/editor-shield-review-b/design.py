#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""P2-specific 3.3V UNO editor shield electrical design, review B."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
G='GND';IO='IOREF_3V3';AUX='AUX_3V3';parts=[]
def pin(n,name,net,t='passive'):return dict(num=str(n),name=name,net=net,type=t)
def add(ref,value,footprint,group,pins,source='',note=''):
    parts.append(dict(ref=ref,value=value,footprint=footprint,sheet=group,pins=pins,source=source,note=note))
def two(ref,value,a,b,group='03-controls',source='',footprint=None):
    fp=footprint or ('Capacitor_SMD:C_0805_2012Metric' if ref.startswith('C') else 'Resistor_SMD:R_0805_2012Metric')
    add(ref,value,fp,group,[pin(1,'1',a),pin(2,'2',b)],source)
def make():
    parts.clear()
    geom=json.loads((HERE/'geometry/uno.json').read_text())['derived_board_header_facts']
    role={'D0':'STOP_N','D1':'LCD_RST_N','D2':'ENC_A','D3':'ENC_B','D4':'ENC_SW_N','D5':'OP1_N','D6':'OP2_N','D7':'OP3_N','D8':'OP4_N','D9':'NOTE_N','D10':'LCD_CS_N','D11':'LCD_MOSI','D12':'LCD_DC','D13':'LCD_SCK','A0':'KNOB1_ADC','A1':'KNOB2_ADC','A2':'KNOB3_ADC','A3':'KNOB4_ADC','A4':'SDA','A5':'SCL','SDA':'SDA','SCL':'SCL','GND':G,'GND1':G,'GND2':G,'IOREF':IO,'3V3':AUX,'5V':None,'RESET':None,'VIN':None,'AREF':None,'NC':None}
    inputs={'LCD_RST_N','LCD_CS_N','LCD_MOSI','LCD_DC','LCD_SCK','SCL'}
    for ref in ['JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR']:
        ps=[]
        for p in geom:
            if p['ref']!=ref:continue
            net=role[p['label']];t='power_out' if p['label'] in ['IOREF','3V3','GND','GND1','GND2'] else 'output' if net in inputs else 'bidirectional' if net=='SDA' else 'input' if net else 'passive'
            if net==G:t='power_out' if ref=='JUNO_PWR' and p['label']=='GND1' else 'passive'
            # SDA/SCL repeated header contacts are passive on D8 to avoid duplicate source models.
            if ref=='JUNO_D8' and p['label'] in ['SDA','SCL']:t='passive'
            ps.append(pin(p['pin'],p['label'],net,t))
        add(ref,ref+' P2 ONLY 3V3','ED2:'+ref,'01-host-power',ps,note='32 male contacts; same top-view coordinates as review I; ICSP not populated')
    two('CIO','1uF',IO,G,'01-host-power');two('CFR','100nF',IO,G,'02-eeprom')
    two('CLCD','10uF',AUX,G,'01-host-power');two('CLCDHF','100nF',AUX,G,'01-host-power')
    add('UMEM','24FC256-I/P','Package_DIP:DIP-8_W7.62mm','02-eeprom',
        [pin(1,'A0',G,'input'),pin(2,'A1',G,'input'),pin(3,'A2',G,'input'),pin(4,'VSS',G,'power_in'),pin(5,'SDA','SDA','bidirectional'),pin(6,'SCL','SCL','input'),pin(7,'WP',G,'input'),pin(8,'VDD',IO,'power_in')],
        'https://akizukidenshi.com/catalog/g/g103568/', '32KiB EEPROM,0x50;64byte pages; ACK polling <=10ms; explicit SAVE only; no extra pulls')
    for i in range(1,5):
        n='KNOB'+str(i);add('RV'+str(i),'B10K RK09D117000B','Potentiometer_THT:Potentiometer_Alps_RK09K_Single_Vertical','03-controls',[pin(1,'CCW',G),pin(2,'WIPER',n+'_RAW'),pin(3,'CW',IO)],'https://akizukidenshi.com/catalog/g/g114827/','center detent;6mm D shaft;S-42 16mm knob;RK09K vertical footprint electrical/mount pattern reference; collar/30mm shaft sample fit pending')
        two('RK'+str(i),'1k',n+'_RAW',n+'_ADC');two('CK'+str(i),'100nF',n+'_ADC',G)
    add('ENC1','ALPHA RE111F-4S1-152S4-15P-A','ED2:RE111F_4S1_ReviewB','03-controls',[pin('A','A','ENC_A_CONTACT'),pin('C','COM',G),pin('B','B','ENC_B_CONTACT'),pin('S1','SW','ENC_SW_N'),pin('S2','SW_COM',G)],'https://akizukidenshi.com/catalog/g/g114936/','30detents/15pulses;SMD;use supplied black shaft; ABC mapping/locator fit provisional; no 6mm knob')
    for c in ['A','B']:
        two('RE'+c+'P','2.7k',IO,'ENC_'+c+'_CONTACT');two('RE'+c+'S','1k','ENC_'+c+'_CONTACT','ENC_'+c);two('CE'+c,'10nF','ENC_'+c,G)
    two('RENSW','4.7k',IO,'ENC_SW_N')
    for ref,net in [('SWOP1','OP1_N'),('SWOP2','OP2_N'),('SWOP3','OP3_N'),('SWOP4','OP4_N'),('SWNOTE','NOTE_N'),('SWSTOP','STOP_N')]:
        add(ref,ref[2:]+' TVDP01-095BB1','Button_Switch_THT:SW_PUSH_6mm_H9.5mm','03-controls',[pin(1,'NO',net),pin(2,'COM',G)],source='https://akizukidenshi.com/catalog/g/g117166/',note='6x6mm/9.5mm;4.5mm row pitch;duplicate pins;sample fit pending')
        two('R'+ref[2:]+'P','10k',IO,net)
    for name in ['CS_N','RST_N']:two('RLCD'+name,'10k',IO,'LCD_'+name,'04-lcd')
    two('RLCDCLK','33','LCD_SCK','LCD_CLK_OUT','04-lcd');two('RLCDDATA','33','LCD_MOSI','LCD_DIN_OUT','04-lcd')
    add('JLCD','M154-240240-RGB 20261020 cable','Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical','04-lcd',
        [pin(1,'GND',G),pin(2,'VCC',AUX),pin(3,'SCL_SPI','LCD_CLK_OUT'),pin(4,'SDA_SPI','LCD_DIN_OUT'),pin(5,'RES','LCD_RST_N'),pin(6,'DC','LCD_DC'),pin(7,'CS','LCD_CS_N'),pin(8,'BLK',AUX)],
        'https://akizukidenshi.com/catalog/g/g131019/','8pin order fixed by20261020 datasheet;3.3V AUX;BLK logic high;not Waveshare PH cable;2.54mm short harness')
    for p in parts:
        if p['sheet']=='03-controls':
            p['sheet']='03-pots' if p['ref'].startswith(('RV','RK','CK')) else '04-encoder' if p['ref'].startswith(('ENC','RE','CE')) else '05-buttons'
        elif p['sheet']=='04-lcd':p['sheet']='06-lcd'
    for p in parts:
        if p['ref'].startswith('RV') or p['ref']=='ENC1':p['pins'].append(pin('MP','MOUNT',None))
    for p in parts:
        if p['ref'].startswith('R') and not p['ref'].startswith('RV'):p['footprint']='Resistor_THT:R_Axial_DIN0204_L3.6mm_D1.6mm_P7.62mm_Horizontal'
        if p['ref'].startswith('C') and p['value']=='100nF':p['footprint']='ED2:C_RDE_100n_P2_5'
        if p['ref'].startswith('C') and p['value']=='10nF':p['footprint']='ED2:C_RDE_10n_P5'
    counts={}
    for p in parts:
        p['design_id']=p['ref']
        if p['ref'].startswith('JUNO'):p['ref']={'JUNO_D0':'J1','JUNO_D8':'J2','JUNO_A':'J3','JUNO_PWR':'J4'}[p['ref']]
        elif p['ref']=='JLCD':p['ref']='J5'
        elif p['ref'].startswith(('R','C','SW','U')) and not p['ref'].startswith('RV'):
            prefix='SW' if p['ref'].startswith('SW') else p['ref'][0];counts[prefix]=counts.get(prefix,0)+1;p['ref']=prefix+str(counts[prefix])
    from catalog import code_for_part,PRODUCTS
    for p in parts:
        p["supplier_code"]=code_for_part(p);p["supplier_url"]=PRODUCTS[p["supplier_code"]]["url"]
    return dict(schema_version=1,revision='editor-B',date='2026-11-18',status='connected_schematic_and_panel_design_not_routed_or_firmware',parts=parts,roles=role,firmware_implemented=False,hardware_accepted=False)
if __name__=='__main__':print(json.dumps(make(),indent=2))
