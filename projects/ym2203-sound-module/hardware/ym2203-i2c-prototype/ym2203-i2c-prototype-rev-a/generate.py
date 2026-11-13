"""Generate the original review schematic and connection tables. Python stdlib only.

This is an unbuilt prototype design, not a production board or verified firmware.
Symbols are drawn here; no third-party symbol library is embedded.
"""
from pathlib import Path
from collections import defaultdict, Counter
import csv
import json
import math
import uuid

ROOT = Path(__file__).resolve().parent
PARTS = []

def add(ref, value, pins, group, kind='ic', note=''):
    # pin number, pin function, connected net (None means intentionally open), ERC type
    PARTS.append(dict(ref=ref, value=value, pins=pins, group=group, kind=kind, note=note))

def two(ref, value, a, b, group, kind='r', note=''):
    add(ref, value, [('1','1',a,'passive'),('2','2',b,'passive')],group,kind,note)

def pin(n, name, net, typ='input'):
    return (str(n), name, net, typ)

def design():
    data_gpio = [4,5,6,7,15,16,17,18]
    hdr = {4:'J1.4',5:'J1.5',6:'J1.6',7:'J1.7',15:'J1.8',16:'J1.9',17:'J1.10',18:'J1.11',
           8:'J1.12',9:'J1.15',10:'J1.16',11:'J1.17',12:'J1.18',13:'J1.19',14:'J1.20',
           2:'J3.5',42:'J3.6',41:'J3.7',40:'J3.8',39:'J3.9',47:'J3.17',21:'J3.18'}
    assignments = {**{g:f'MCU_D{i}' for i,g in enumerate(data_gpio)},8:'I2C_SDA',9:'I2C_SCL',
        10:'A0_3V3',11:'WR_3V3_N',12:'CS_3V3_N',13:'RD_3V3_N',14:'WRITE_OE_N',
        47:'RESET_3V3_N',39:'POT_SCK_3V3',40:'POT_MOSI_3V3',41:'POT_CS_3V3_N',
        21:'READ_OE_N',42:'HP_ENABLE',2:'SPK_ENABLE'}
    add('M1','ESP32-S3-DevKitC-1-N8R8',
        [pin('J1.21','5V','+5V','power_in'),pin('J1.1','3V3','+3V3','power_out'),
         pin('J1.22','GND','GND','power_in'),pin('J3.1','GND','GND','power_in')]+
        [pin(hdr[g],f'GPIO{g}',n,'bidirectional') for g,n in assignments.items()],1,
        note='v1.0 header numbering; 8 MiB PSRAM; unlisted board pins left open; no USB attached while externally powered')
    add('J1','USB 5V input (breakout/cable)',[pin(1,'VBUS','USB_5V','passive'),pin(2,'GND','GND','passive')],1,'connector',
        'Regulated USB 5 V / 2 A supply; no data connection; not a PC USB load specification')
    two('F1','1.5A hold PTC','USB_5V','+5V',1,'r','Select low resistance; confirm >=4.75 V at YM2203 under load')
    add('J2','I2C host 3.3V',[pin(1,'GND','GND','passive'),pin(2,'SDA','I2C_SDA','passive'),pin(3,'SCL','I2C_SCL','passive')],1,'connector')
    two('R1','2.2k','I2C_SDA','+3V3',1); two('R2','2.2k','I2C_SCL','+3V3',1)
    two('C1','470u/10V','+5V','GND',1,'c'); two('C2','100n','+5V','GND',1,'c')
    two('FB1','220R@100MHz / >=1A','+5V','+5VA',1,'r','Example BLM21PG221SN1L; verify DCR and current rating')
    two('C3','47u/10V','+5VA','GND',1,'c'); two('C4','100n','+5VA','GND',1,'c')
    for ref,net in [('PF1','USB_5V'),('PF2','+5V'),('PF3','+5VA'),('PF4','GND')]:
        add(ref,'SUPPLY FLAG',[pin(1,'SUPPLY',net,'power_out')],1,'flag','Electrical supply assertion, not a physical part')
    # 3.3 -> 5 V writes. AHCT (not HC) accepts 3.3 V logic at a 5 V supply.
    p=[pin(1,'OE1_N','WRITE_OE_N'),pin(19,'OE2_N','GND'),pin(20,'VCC','+5V','power_in'),pin(10,'GND','GND','power_in')]
    for i in range(8):p += [pin(i+2,f'A{i+1}',f'MCU_D{i}'),pin(18-i,f'Y{i+1}',f'YM_D{i}','tri_state')]
    add('U2','SN74AHCT541N',p,2)
    # 5 V-tolerant read path, always A (YM bus) -> B (MCU bus).
    p=[pin(1,'DIR=AtoB','+3V3'),pin(19,'OE_N','READ_OE_N'),pin(20,'VCC','+3V3','power_in'),pin(10,'GND','GND','power_in')]
    for i in range(8):p += [pin(i+2,f'A{i+1}',f'YM_D{i}','bidirectional'),pin(18-i,f'B{i+1}',f'MCU_D{i}','bidirectional')]
    add('U3','SN74LVC245AN',p,2,note='3.3 V supply; inputs 5.5 V tolerant; do not substitute HC245')
    controls=[('A0_3V3','YM_A0'),('WR_3V3_N','YM_WR_N'),('CS_3V3_N','YM_CS_N'),('RD_3V3_N','YM_RD_N'),
              ('RESET_3V3_N','YM_RESET_N'),('POT_SCK_3V3','POT_SCK'),('POT_MOSI_3V3','POT_MOSI'),('POT_CS_3V3_N','POT_CS_N')]
    p=[pin(1,'OE1_N','GND'),pin(19,'OE2_N','GND'),pin(20,'VCC','+5V','power_in'),pin(10,'GND','GND','power_in')]
    for i,(a,b) in enumerate(controls):p += [pin(i+2,f'A{i+1}',a),pin(18-i,f'Y{i+1}',b,'output')]
    add('U4','SN74AHCT541N',p,2)
    pulls = [('WRITE_OE_N','+3V3'),('READ_OE_N','+3V3'),('A0_3V3','GND'),('WR_3V3_N','+3V3'),
        ('CS_3V3_N','+3V3'),('RD_3V3_N','+3V3'),('RESET_3V3_N','GND'),('POT_SCK_3V3','GND'),
        ('POT_MOSI_3V3','GND'),('POT_CS_3V3_N','+3V3')]
    for i,(a,b) in enumerate(pulls):two(f'R{3+i}','10k',a,b,2)
    for i in range(8):two(f'R{13+i}','100k',f'MCU_D{i}','GND',2)
    for ref,rail in [('C5','+5V'),('C6','+3V3'),('C7','+5V')]:two(ref,'100n',rail,'GND',2,'c')
    # OPN / dedicated DAC. NC pins stay open.
    p=[pin(1,'GND','GND','power_in'),pin(17,'AGND','GND','power_in'),pin(21,'VDD','+5V','power_in'),
       pin(38,'PHI_M','YM_CLK'),pin(39,'PHI_S','DAC_CLK','output'),pin(22,'SH','DAC_LOAD','output'),pin(23,'OP_O','DAC_SD','output'),
       pin(37,'A0','YM_A0'),pin(36,'RD_N','YM_RD_N'),pin(35,'WR_N','YM_WR_N'),pin(34,'CS_N','YM_CS_N'),pin(24,'IC_N','YM_RESET_N'),
       pin(25,'IRQ_N',None,'open_collector'),pin(20,'SSG_A','SSG_A','output'),pin(19,'SSG_B','SSG_B','output'),pin(18,'SSG_C','SSG_C','output')]
    for i,n in enumerate([40,2,3,4,5,6,7,8]):p.append(pin(n,f'D{i}',f'YM_D{i}','bidirectional'))
    for i in range(8):p += [pin(16-i,f'IOA{i}',None,'bidirectional'),pin(26+i,f'IOB{i}',None,'bidirectional')]
    add('U1','YM2203C DIP-40',p,3)
    p=[pin(1,'VDD','+5VA','power_in'),pin(2,'TO_BUFF','DAC_RAW','output'),pin(4,'LOAD','DAC_LOAD'),pin(7,'SD','DAC_SD'),
       pin(10,'CLOCK','DAC_CLK'),pin(12,'GND','GND','power_in'),pin(14,'RB','DAC_RB','passive'),pin(16,'MP','VREF','passive')]
    p += [pin(n,'NC',None,'no_connect') for n in [3,5,6,8,9,11,13,15]]
    add('U5','YM3014B-F SOP-16',p,3,note='Use SOP-16 pin numbers, not DIP-8 pin numbers')
    add('X1','ECS-2100AX-040 4MHz/5V',[pin(1,'NC',None,'no_connect'),pin(4,'GND','GND','power_in'),
        pin(5,'OUT','CLK_RAW','output'),pin(8,'VDD','+5V','power_in')],3,note='Half-size DIP oscillator; pin1 NC per ECS-2100 series drawing')
    two('R21','33R','CLK_RAW','YM_CLK',3)
    two('C8','100n','+5V','GND',3,'c');two('C9','10u/10V','+5V','GND',3,'c')
    two('C10','100n','+5VA','GND',3,'c');two('C11','10u/10V','+5VA','GND',3,'c')
    two('C12','100n','+5V','GND',3,'c');two('C13','10u/10V','DAC_RB','GND',3,'c')
    # Quad op amp: A=RB reference follower; B=DAC output follower;
    # C=inverting AC mixer around VREF; D=volume wiper follower.
    add('U6','OPA4192ID SOIC-14',[
        pin(1,'OUT_A','VREF','output'),pin(2,'IN_A-','VREF'),pin(3,'IN_A+','DAC_RB'),pin(4,'V+','+5VA','power_in'),
        pin(5,'IN_B+','DAC_RAW'),pin(6,'IN_B-','FM_BUF'),pin(7,'OUT_B','FM_BUF','output'),
        pin(8,'OUT_C','MIX_OUT','output'),pin(9,'IN_C-','MIX_SUM'),pin(10,'IN_C+','VREF'),pin(11,'V-','GND','power_in'),
        pin(12,'IN_D+','POT_WIPER'),pin(13,'IN_D-','AUDIO_VOL'),pin(14,'OUT_D','AUDIO_VOL','output')],4)
    for i,(source,rval) in enumerate([('FM_BUF','22k'),('SSG_A','100k'),('SSG_B','100k'),('SSG_C','100k')]):
        two(f'C{14+i}','1u film',source,f'MIX_AC{i}',4,'c')
        two(f'R{22+i}',rval,f'MIX_AC{i}','MIX_SUM',4)
    two('R26','22k','MIX_SUM','MIX_OUT',4);two('C18','330p C0G','MIX_SUM','MIX_OUT',4,'c')
    add('U7','MCP41010-I/P DIP-8',[pin(1,'CS_N','POT_CS_N'),pin(2,'SCK','POT_SCK'),pin(3,'SI','POT_MOSI'),
        pin(4,'VSS','GND','power_in'),pin(5,'PA0','MIX_OUT','passive'),pin(6,'PW0','POT_WIPER','passive'),
        pin(7,'PB0','VREF','passive'),pin(8,'VDD','+5VA','power_in')],4,
        note='SPI 0x11 + wiper code; power-up midscale, so keep amplifiers muted until initialized')
    two('C19','100n','+5VA','GND',4,'c');two('C20','100n','+5VA','GND',4,'c')
    # Independent headphone channels, each fed the same mono source.
    add('U8','TPA6110A2DGN',[
        pin(1,'BYPASS','HP_BYPASS','passive'),pin(2,'GND','GND','power_in'),pin(3,'SHUTDOWN','HP_SHUTDOWN'),pin(4,'IN2-','HP_IN_R'),
        pin(5,'VO2','HP_OUT_R','output'),pin(6,'VDD','+5VA','power_in'),pin(7,'VO1','HP_OUT_L','output'),pin(8,'IN1-','HP_IN_L'),
        pin(9,'PAD','GND','passive')],5,note='PowerPAD must be soldered to grounded copper; output capacitors required')
    for i,ch in enumerate(['L','R']):
        two(f'C{21+i}','1u film','AUDIO_VOL',f'HP_AC_{ch}',5,'c')
        two(f'R{27+i}','22k',f'HP_AC_{ch}',f'HP_IN_{ch}',5)
        two(f'R{29+i}','22k',f'HP_IN_{ch}',f'HP_OUT_{ch}',5)
        two(f'C{23+i}','470u/10V (+ at amp)',f'HP_OUT_{ch}',f'HP_COUPLED_{ch}',5,'c')
        two(f'R{31+i}','22R',f'HP_COUPLED_{ch}',f'JACK_{ch}',5)
        two(f'R{33+i}','100k',f'JACK_{ch}','GND',5)
    two('C25','1u','HP_BYPASS','GND',5,'c');two('C26','100n','+5VA','GND',5,'c');two('C27','10u/10V','+5VA','GND',5,'c')
    two('R35','10k','HP_SHUTDOWN','+5VA',5)
    add('Q1','2N7002 SOT-23',[pin(1,'G','HP_GATE'),pin(2,'S','GND','passive'),pin(3,'D','HP_SHUTDOWN','open_collector')],5)
    two('R36','1k','HP_ENABLE','HP_GATE',5);two('R37','100k','HP_GATE','GND',5)
    add('J3','3.5mm TRS headphone',[pin(1,'TIP=L','JACK_L','passive'),pin(2,'RING=R','JACK_R','passive'),pin(3,'SLEEVE','GND','passive')],5,'connector',
        'Functional connector numbering; actual jack footprint/pins must be mapped before PCB layout; 32 ohm nominal')
    # Speaker BTL power amplifier; external input resistors lower gain to about 1.63.
    add('U9','PAM8302AAS SO-8',[pin(1,'SD_N','SPK_SD'),pin(2,'NC',None,'no_connect'),pin(3,'IN+','SPK_IN_P'),pin(4,'IN-','SPK_IN_N'),
        pin(5,'OUT+','SPK_P','output'),pin(6,'VDD','+5V','power_in'),pin(7,'GND','GND','power_in'),pin(8,'OUT-','SPK_N','output')],6)
    two('C28','1u film','AUDIO_VOL','SPK_AC_P',6,'c');two('R38','82k','SPK_AC_P','SPK_IN_P',6)
    two('C29','1u film','GND','SPK_AC_N',6,'c');two('R39','82k','SPK_AC_N','SPK_IN_N',6)
    two('C30','1u','+5V','GND',6,'c');two('C31','10u/10V','+5V','GND',6,'c');two('C32','220u/10V','+5V','GND',6,'c')
    add('S1','Speaker enable (ON connects)',[pin(1,'MCU','SPK_ENABLE','passive'),pin(2,'AMP','SPK_SD','passive')],6,'switch')
    two('R40','100k','SPK_SD','GND',6);two('R41','100k','SPK_ENABLE','GND',6)
    add('J4','8 ohm / >=1W speaker',[pin(1,'SPK+','SPK_P','passive'),pin(2,'SPK-','SPK_N','passive')],6,'connector',
        'BTL output: neither terminal is ground; do not connect headphones or grounded instruments here')
    return assignments

def ident(name):return str(uuid.uuid5(uuid.NAMESPACE_URL,'weblab:ym2203-hw:'+name))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def effects(size=1.0,justify=''):
    return f'(effects (font (size {size} {size}))'+(f' (justify {justify})' if justify else '')+')'

def generate_schematic():
    root=ident('root'); libs=[]; placed=[]; drawings=[]
    grid=lambda v: round(round(v/1.27)*1.27,6)
    # A0 sheet: top row active circuits; lower sections passive networks by group.
    active_positions={1:(95,95),2:(275,95),3:(455,95),4:(635,95),5:(815,95),6:(995,95)}
    grouped=defaultdict(list)
    for p in PARTS:grouped[p['group']].append(p)
    for group,parts in grouped.items():
        x0,y0=active_positions[group]; active=[p for p in parts if p['kind'] in ('ic','connector')]
        passive=[p for p in parts if p['kind'] not in ('ic','connector')]
        cursor=y0
        for p in active:
            rows=math.ceil(len(p['pins'])/2); height=max(20,(rows+1)*4)
            p['x'],p['y']=x0,cursor;cursor+=height+20
        for i,p in enumerate(passive):
            p['x']=x0-46+(i%2)*92;p['y']=max(360,cursor+10)+(i//2)*23
        titles={1:'1 POWER / I2C / MCU',2:'2 3.3V <-> 5V BUS',3:'3 OPN / DAC / CLOCK',4:'4 MIXER / VOLUME',5:'5 HEADPHONES (MONO x2)',6:'6 SPEAKER (BTL)'}
        drawings.append(f'(text {q(titles[group])} (at {x0-58} 35 0) {effects(2.0,"left")} (uuid {ident("title"+str(group))}))')
    for p in PARTS:
        ref=p['ref']; x=grid(p['x']); y=grid(p['y']); pts=p['pins']; n=math.ceil(len(pts)/2)
        height=max(12,(n+1)*4); half=height/2; name=ref+'_symbol'; lib='YM2203_HW:'+name
        pinparts=[]; coords=[]
        for i,(number,function,net,typ) in enumerate(pts):
            left=i<n; row=i if left else i-n; py=grid(half-4*(row+1)); px=-20.32 if left else 20.32; angle=0 if left else 180
            pinparts.append(f'(pin {typ} line (at {px} {py} {angle}) (length 3.81) (name {q(function)} {effects(.95)}) (number {q(number)} {effects(.9)}))')
            coords.append((number,net,grid(x+px),grid(y-py),left))
        # IC boxes / two-terminal parts are explicitly named and pin numbered.
        outline=f'(rectangle (start -16.51 {half}) (end 16.51 {-half}) (stroke (width 0.25) (type default)) (fill (type background)))'
        libs.append(f'(symbol {q(lib)} (pin_names (offset 0.7)) (in_bom yes) (on_board yes)'
            f'(property "Reference" {q(ref)} (at 0 {half+3} 0) {effects(1.2)})'
            f'(property "Value" {q(p["value"])} (at 0 {-half-3} 0) {effects(1.0)})'
            f'(symbol {q(name+"_0_1")} {outline}) (symbol {q(name+"_1_1")} '+''.join(pinparts)+'))')
        placed.append(f'(symbol (lib_id {q(lib)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no)'
            f'(uuid {ident(ref)}) (property "Reference" {q(ref)} (at {x} {y-half-3} 0) {effects(1.2)})'
            f'(property "Value" {q(p["value"])} (at {x} {y+half+3} 0) {effects(1.0)})'
            f'(instances (project "ym2203-i2c-prototype" (path "/{root}" (reference {q(ref)}) (unit 1)))))')
        for number,net,px,py,left in coords:
            uid=ref+':'+number
            if net is None:
                placed.append(f'(no_connect (at {px} {py}) (uuid {ident(uid+"nc")}))');continue
            end=grid(px+(-12.7 if left else 12.7))
            placed.append(f'(wire (pts (xy {px} {py}) (xy {end} {py})) (stroke (width 0) (type default)) (uuid {ident(uid+"wire")}))')
            # Text starts at the label endpoint; wire occupies the opposite side.
            placed.append(f'(label {q(net)} (at {end} {py} {0 if left else 180}) {effects(.95,"right bottom" if left else "left bottom")} (uuid {ident(uid+"label")}))')
    drawings.append(f'(text "DRAFT Rev A | 2026-10-14 | Unbuilt / no PCB / firmware not supplied | Matching net labels are connected" (at 25 18 0) {effects(2.0,"left")} (uuid {ident("warning")}))')
    result=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {root}) (paper "A0")\n(lib_symbols '+''.join(libs)+')\n'+ '\n'.join(placed+drawings)+'\n(embedded_fonts no))\n'
    (ROOT/'ym2203-i2c-prototype.kicad_sch').write_text(result)
    library='(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+''.join(l.replace('(symbol "YM2203_HW:', '(symbol "',1) for l in libs)+')\n'
    (ROOT/'YM2203_HW.kicad_sym').write_text(library)
    (ROOT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "YM2203_HW") (type "KiCad") (uri "${KIPRJMOD}/YM2203_HW.kicad_sym") (options "") (descr "Original prototype review symbols")))\n')

def main():
    assignments=design()
    # Every physical pin of the Yamaha ICs appears once; all NC pins are explicit.
    for ref,n in [('U1',40),('U5',16),('U2',20),('U3',20),('U4',20),('U6',14),('U7',8),('U8',9),('U9',8)]:
        p=next(p for p in PARTS if p['ref']==ref)
        assert sorted(int(x[0]) for x in p['pins'])==list(range(1,n+1)),ref
    nets=defaultdict(list)
    for p in PARTS:
        for number,function,net,typ in p['pins']:
            if net is not None:nets[net].append((p['ref'],number,function,typ))
    assert all(len(pins)>1 for pins in nets.values()),[(n,p) for n,p in nets.items() if len(p)<2]
    assert {'U1','U5'}<=set(r for r,_,_,_ in nets['DAC_SD'])
    assert not set(r for r,_,_,_ in nets['SPK_P']) & {'J3'}
    assert not set(r for r,_,_,_ in nets['SPK_N']) & {'J3'}
    assert not set(n for n in assignments.values()) & {'+5V','+5VA'}
    (ROOT/'design.json').write_text(json.dumps({'parts':PARTS,'mcu_gpio':assignments},ensure_ascii=False,indent=2)+'\n')
    with (ROOT/'connections.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['net','reference','pin','function','electrical_type'])
        for net,pins in sorted(nets.items()):
            for p in pins:w.writerow([net,*p])
    with (ROOT/'bom.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['reference','part_or_value','quantity','notes'])
        for p in PARTS:
            if p['kind']!='flag':w.writerow([p['ref'],p['value'],1,p['note']])
    calcs={'event_storage_bytes_packed':131071*6,'event_storage_bytes_8_byte_struct':131071*8,
        'mixer_fm_gain':-1,'mixer_each_ssg_gain':-.22,'mixer_feedback_pole_hz':1/(2*math.pi*22000*330e-12),
        'fm_input_highpass_hz':1/(2*math.pi*22000*1e-6),'ssg_input_highpass_hz':1/(2*math.pi*100000*1e-6),
        'headphone_input_highpass_hz':1/(2*math.pi*22000*1e-6),
        'headphone_output_highpass_32ohm_hz':1/(2*math.pi*(32+22)*470e-6),
        'headphone_load_attenuation_32ohm':32/(32+22), 'speaker_gain_nominal':150000/(10000+82000),
        'i2c_rise_100pf_ns':.8473*2200*100e-12*1e9,
        'validation_scope':'Pin completeness, named-net connectivity, voltage-domain intent and nominal calculations only; no SPICE or hardware validation.'}
    (ROOT/'calculations.json').write_text(json.dumps(calcs,indent=2)+'\n')
    generate_schematic()
    print(f'{len(PARTS)} symbols, {len(nets)} connected nets; pin/connectivity checks passed')

if __name__=='__main__':main()
