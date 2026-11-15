"""Original, reproducible schematics and PCB input for the socketed sound platform.

No third-party symbol or footprint artwork is embedded. Manufacturer documents
are referenced in README.md. This program does not claim hardware verification.
"""
from pathlib import Path
from collections import defaultdict, Counter
import csv
import json
import math
import subprocess
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "rev-a"
OUT.mkdir(exist_ok=True)
Q = lambda v: json.dumps(str(v), ensure_ascii=False)
UID = lambda v: str(uuid.uuid5(uuid.NAMESPACE_URL, "weblab-sound-pcb-rev-a:" + v))
GND, V3, V5 = "GND", "+3V3", "+5V"
GPIO = [(n, f"D{n}") for n in range(8)] + [
    (8, "A0"), (9, "A1"), (10, "I2S_DATA"), (11, "I2S_BCLK"),
    (12, "I2S_LRCK"), (13, "CS_N"), (14, "WR_N"), (15, "RD_N"),
    (16, "FM_SD"), (17, "FM_CLK"), (18, "FM_SH1"), (19, "FM_SH2"),
    (20, "HOST_SDA"), (21, "HOST_SCL"), (22, "ARM"),
    (26, "AUX_SDA"), (27, "AUX_SCL"), (28, "STATUS")]
PHYS = dict(zip(list(range(23)) + [26, 27, 28],
                [1, 2, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 19, 20,
                 21, 22, 24, 25, 26, 27, 29, 31, 32, 34]))
CONNECTOR = [V5,GND,V5,GND,V3,GND] + [f"D{i}" for i in range(8)] + [
    "A0",GND,"A1",GND,"CS_N","WR_N","RD_N",GND,"RESET_N","ARM",
    "STATUS",GND,"FM_SD","FM_CLK","FM_SH1","FM_SH2",GND,
    "AUX_SDA","AUX_SCL",GND,"ID0","ID1","ID2","PRESENT_N",
    "AUX0","AUX1",GND,"ANALOG_L",GND,"ANALOG_R",GND,None,None,GND,GND,None]
assert len(CONNECTOR) == 50
BOARDS = {}


class Board:
    def __init__(self, name, size, title):
        self.name, self.size, self.title = name, size, title
        self.parts = []
        self.counters = Counter()
        self.dir = OUT / name
        self.dir.mkdir(exist_ok=True)
        BOARDS[name] = self

    def part(self, ref, value, pins, footprint, xy, group, source="", **extra):
        # pins: physical pin -> (name, net, electrical type)
        p = dict(ref=ref, value=value,
                 pins=[dict(num=str(n), name=t[0], net=t[1], type=t[2]) for n,t in pins.items()],
                 footprint=footprint, xy=list(xy), group=group, source=source, **extra)
        assert ref not in {a['ref'] for a in self.parts}
        self.parts.append(p)
        return p

    def passive(self, prefix, value, a, b, xy, group, **extra):
        self.counters[prefix] += 1
        ref = prefix + str(self.counters[prefix])
        fp = dict(kind="smd2",pitch=3.2,body=[3.2,1.6])
        if prefix=='F':fp=dict(kind='axial',pitch=7.62,body=[6,3])
        if prefix=='C' and ('BP' in value or extra.get('polar')):
            fp=dict(kind='radial',pitch=2,body=[5,5])
        return self.part(ref,value,{1:('1',a,'passive'),2:('2',b,'passive')},fp,xy,group,**extra)

    def r(self, value,a,b,xy,g,**kw): return self.passive('R',value,a,b,xy,g,**kw)
    def c(self, value,a,b,xy,g,**kw): return self.passive('C',value,a,b,xy,g,**kw)
    def rn(self,ref,n,value,common,signals,xy,g):
        assert len(signals)==n
        pins={1:('COM',common,'passive')}
        pins.update({i+2:(f'R{i+1}',s,'passive') for i,s in enumerate(signals)})
        code={'10k':'103J','4.7k':'472J','1k':'102J'}[value]
        return self.part(ref,f'RKC{n}BD'+code,pins,
                         dict(kind='sip',n=n+1,pitch=2.54),xy,g,
                         source='https://akizukidenshi.com/catalog/g/g113722/' if value=='1k' else 'https://akizukidenshi.com/catalog/g/g111910/' if n==8 else 'https://akizukidenshi.com/catalog/g/g111909/')

    def ic(self,ref,value,pinmap,n,width,xy,g,source='',**kw):
        assert set(pinmap)==set(range(1,n+1)),(ref,set(range(1,n+1))-set(pinmap))
        return self.part(ref,value,pinmap,dict(kind='dip',n=n,width=width),xy,g,source,**kw)

    def tp(self,ref,net,xy,g='test'):
        return self.part(ref,net,{1:(net,net,'passive')},dict(kind='tp'),xy,g)

    def header(self,ref,value,nets,xy,g='io',rows=1,**kw):
        return self.part(ref,value,{i+1:(n or 'NC',n,'passive') for i,n in enumerate(nets)},
                         dict(kind='header',n=len(nets),rows=rows,pitch=2.54),xy,g,**kw)

    def decouple(self,net,xy,g='decoupling',near=None):
        return self.c('100n',net,GND,xy,g,role='Place immediately beside supply pin',near=near)


def powerpins(mapping,n,vcc,gnd):
    p={i:(f'NC{i}',None,'passive') for i in range(1,n+1)}
    p.update(mapping)
    p[vcc]=('VCC',V3,'power_in');p[gnd]=('GND',GND,'power_in')
    return p


def make_base():
    b=Board('base',(180,160),'COMMON BASE / Pico 2 + stereo DAC + line mixer')
    gp={PHYS[g]:(f'GP{g} / {s}',s,'bidirectional') for g,s in GPIO}
    for p in (3,8,13,18,23,28,33,38):gp[p]=('GND',GND,'power_in')
    gp.update({30:('RUN','PICO_RUN','input'),35:('ADC_VREF',None,'passive'),
               36:('3V3 OUT',V3,'power_out'),37:('3V3_EN',None,'input'),
               39:('VSYS','VSYS','power_in'),40:('USB VBUS',None,'power_out')})
    b.ic('A1','Raspberry Pi Pico 2',gp,40,17.78,(10,14),'controller',
         'https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf',body_extra=[21,51])
    b.header('JMOD','ESQ-125-58-L-D / socket',CONNECTOR,(170,15),'module',rows=2,
             source='https://suddendocs.samtec.com/catalog_english/esq_th.pdf',
             role='Top-side 16.13mm female. Block contact 50 with an insulating key.')
    b.header('JHOST','HOST 3.3V I2C',[GND,'HOST_SDA','HOST_SCL',GND],(8,82))
    b.header('JPOWER','MAIN INPUT / REGULATED DC 5V',['EXT_5V',GND],(8,148),'power',
             role='Required main supply: pin 1 = regulated +5V, pin 2 = GND. No reverse-polarity or overvoltage protection.')
    b.passive('F','PTC 0.5A hold','EXT_5V',V5,(8,137),'power')
    b.part('D1','SS14 / A=+5V K=VSYS',
           {1:('K','VSYS','passive'),2:('A',V5,'passive')},
           dict(kind='sma'),(32,143),'power',
           role='Prevents Pico USB from feeding the external supply through VSYS')
    b.c('47u 10V',V5,GND,(37,151),'power',polar=True)
    b.c('10u 10V',V3,GND,(44,151),'power',polar=True)
    b.header('JRUN','RESET SWITCH',['PICO_RUN',GND],(8,75),'controller')
    for signal,xy in [('HOST_SDA',(8,91)),('HOST_SCL',(8,97)),
                      ('AUX_SDA',(45,55)),('AUX_SCL',(45,61))]:
        b.r('4.7k',signal,V3,xy,'pulls',role='Host pullups removable if already supplied externally')
    # MCP23017 SPDIP physical numbering, DS20001952D page 1.
    e={i:(f'GPB{i-1}',s,'bidirectional') for i,s in enumerate(
       ['ID0','ID1','ID2','PRESENT_N',GND,GND,GND,None],1)}
    for i in (5,6,7):e[i]=(f'GPB{i-1}',GND,'input')
    e[8]=('GPB7',None,'output')
    e.update({9:('VDD',V3,'power_in'),10:('VSS',GND,'power_in'),
              11:('NC',None,'passive'),12:('SCL','AUX_SCL','input'),
              13:('SDA','AUX_SDA','bidirectional'),14:('NC',None,'passive'),
              15:('A0',GND,'input'),16:('A1',GND,'input'),17:('A2',GND,'input'),
              18:('RESET_N','PICO_RUN','input'),19:('INTB',None,'open_collector'),
              20:('INTA',None,'open_collector')})
    aux=['RESET_RELEASE','LINE_ALLOW',None,'DAC_ALLOW','AUX0','AUX1',None,None]
    for i,s in enumerate(aux):e[21+i]=(f'GPA{i}',s,'output' if i==7 else 'bidirectional')
    b.ic('U1','MCP23017-E/SP / 0x20',e,28,7.62,(43,15),'controller',
         'https://akizukidenshi.com/catalog/g/g109486/')
    b.decouple(V3,(55,16))
    # Three hardware AND functions; state held by expander is gated off by ARM.
    gate={1:('1A','ARM','input'),2:('1B','RESET_RELEASE','input'),3:('1Y','RESET_N','output'),
          4:('2A','ARM','input'),5:('2B','DAC_ALLOW','input'),6:('2Y','DAC_XSMT','output'),
          7:('GND',GND,'power_in'),8:('3Y','LINE_RUN','output'),
          9:('3A','ARM','input'),10:('3B','LINE_ALLOW','input'),
          11:('4Y',None,'output'),12:('4A',GND,'input'),13:('4B',GND,'input'),14:('VCC',V3,'power_in')}
    b.ic('U2','TC74HC08AP / 3.3V',gate,14,7.62,(72,15),'safety',
         'https://akizukidenshi.com/catalog/g/g114059/')
    b.decouple(V3,(84,15))
    b.rn('RN1',8,'10k',GND,[f'D{i}' for i in range(8)],(8,68),'pulls')
    b.rn('RN2',8,'10k',GND,['ARM','A0','A1','RESET_RELEASE','DAC_ALLOW','LINE_ALLOW','AUX0','AUX1'],(43,68),'pulls')
    b.rn('RN3',4,'10k',V3,['ID0','ID1','ID2','PRESENT_N'],(91,18),'pulls')
    b.rn('RN4',4,'10k',V3,['CS_N','WR_N','RD_N','STATUS'],(91,26),'pulls')
    b.rn('RN5',4,'10k',GND,['FM_SD','FM_CLK','FM_SH1','FM_SH2'],(125,60),'pulls')
    b.r('10k','DAC_XSMT',GND,(72,40),'safety')
    # AE-PCM5102A has the same physical pin numbering as the DAC.
    dn={1:('CPVDD',V3,'power_in'),2:('CAPP','CAPP','passive'),3:('CPGND',GND,'power_in'),
        4:('CAPM','CAPM','passive'),5:('VNEG','VNEG','power_out'),6:('OUTL','DAC_L','output'),
        7:('OUTR','DAC_R','output'),8:('AVDD',V3,'power_in'),9:('AGND',GND,'power_in'),
        10:('DEMP',GND,'input'),11:('FLT',GND,'input'),12:('SCK',GND,'input'),
        13:('BCK','DAC_BCK','input'),14:('DIN','DAC_DIN','input'),15:('LRCK','DAC_LRCK','input'),
        16:('FMT',GND,'input'),17:('XSMT','DAC_XSMT','input'),18:('LDOO','LDOO','power_out'),
        19:('DGND',GND,'power_in'),20:('DVDD',V3,'power_in')}
    b.ic('A2','AE-PCM5102A / I2S 48kHz',dn,20,15.24,(12,106),'dac',
         'https://akizukidenshi.com/catalog/g/g111836/',body_extra=[17.5,25.5])
    for i,(s,d) in enumerate([('I2S_DATA','DAC_DIN'),('I2S_BCLK','DAC_BCK'),('I2S_LRCK','DAC_LRCK')]):
        b.r('47',s,d,(36,106+i*6),'dac')
    pump=b.c('2.2u X7R 10V','CAPP','CAPM',(8,109),'dac')
    pump['footprint']['kind']='smd2v'
    b.c('2.2u X7R 10V','VNEG',GND,(7,117),'dac')
    b.c('1u X7R 10V','LDOO',GND,(32,112),'dac')
    for xy,pin in [((7,105),1),((7,124),8),((32,105),20)]:b.decouple(V3,xy,'dac',near=['A2',pin])
    for xy in [(7,99),(7,130),(32,120)]:b.c('10u 10V',V3,GND,xy,'dac',polar=True)
    for ch,x in [('L',48),('R',48)]:
        yy=100 if ch=='L' else 115
        b.r('470',f'DAC_{ch}',f'FM_{ch}',(x,yy),'analog')
        b.c('2.2n C0G',f'FM_{ch}',GND,(x+11,yy),'analog')
    # Reference buffer + unused amplifier as a follower at VREF.
    p={1:('OUTA','VREF','output'),2:('INA-','VREF','input'),3:('INA+','REF_RAW','input'),
       4:('VSS',GND,'power_in'),5:('INB+','VREF','input'),6:('INB-','REF_SPARE','input'),
       7:('OUTB','REF_SPARE','output'),8:('VDD',V5,'power_in')}
    b.ic('U3','MCP6022-I/P / reference',p,8,7.62,(72,106),'analog')
    b.r('10k 1%',V5,'REF_RAW',(66,98),'analog')
    b.r('10k 1%','REF_RAW',GND,(66,93),'analog')
    b.c('10u 10V','REF_RAW',GND,(84,99),'analog',polar=True)
    b.decouple(V5,(84,106),'analog')
    # Independent stereo sums preserve stereo FM on later cards.
    p={1:('OUTA','MIX_L','output'),2:('INA-','SUM_L','input'),3:('INA+','VREF','input'),
       4:('VSS',GND,'power_in'),5:('INB+','VREF','input'),6:('INB-','SUM_R','input'),
       7:('OUTB','MIX_R','output'),8:('VDD',V5,'power_in')}
    b.ic('U4','MCP6022-I/P / stereo mixer',p,8,7.62,(101,106),'analog')
    b.decouple(V5,(113,106),'analog')
    for ch,yy in [('L',88),('R',124)]:
        b.c('4.7u BP 10V',f'FM_{ch}',f'FM_AC_{ch}',(67,yy),'analog')
        b.c('4.7u BP 10V',f'ANALOG_{ch}',f'MOD_AC_{ch}',(82,yy),'analog')
        b.r('100k 1%',f'FM_AC_{ch}',f'SUM_{ch}',(98,yy),'analog')
        b.r('100k 1%',f'MOD_AC_{ch}',f'SUM_{ch}',(113,yy),'analog')
        b.r('22k 1%',f'MIX_{ch}',f'SUM_{ch}',(98,yy+6),'analog')
        b.c('47p',f'MIX_{ch}',f'SUM_{ch}',(113,yy+6),'analog')
    # CD74HC4053 switch common at pins 14 and 15; S=0 signal, S=1 VREF mute.
    p={1:('Y1','VREF','passive'),2:('Y0','MIX_R','passive'),
       3:('Z1',GND,'passive'),4:('Z',None,'passive'),5:('Z0',GND,'passive'),
       6:('INH',GND,'input'),7:('VEE',GND,'power_in'),8:('GND',GND,'power_in'),
       9:('C',GND,'input'),10:('B','MUTE_5V','input'),11:('A','MUTE_5V','input'),
       12:('X0','MIX_L','passive'),13:('X1','VREF','passive'),
       14:('X','MUTED_L','passive'),15:('Y','MUTED_R','passive'),16:('VCC',V5,'power_in')}
    b.ic('U5','CD74HC4053E / line mute',p,16,7.62,(133,105),'analog',
         'https://akizukidenshi.com/catalog/g/g113266/')
    b.decouple(V5,(145,105),'analog')
    # Generic transistor is replaced by a SOT23 MMBT3904 with verified B/E/C mapping.
    b.part('Q1','MMBT3904 / B1 E2 C3',
           {1:('B','MUTE_BASE','input'),2:('E',GND,'passive'),3:('C','MUTE_5V','open_collector')},
           dict(kind='sot23'),(126,90),'safety',
           source='https://www.onsemi.com/pdf/datasheet/mmbt3904lt1-d.pdf')
    b.r('10k','LINE_RUN','MUTE_BASE',(121,81),'safety')
    b.r('100k','MUTE_BASE',GND,(121,76),'safety')
    b.r('10k',V5,'MUTE_5V',(139,81),'safety')
    for ch,x in [('L',128),('R',146)]:
        b.c('4.7u BP 10V',f'MUTED_{ch}',f'OUT_AC_{ch}',(x,133),'analog')
        b.r('100k',f'OUT_AC_{ch}',GND,(x,139),'analog')
        b.r('100',f'VOL_{ch}',f'LINE_{ch}',(x,151),'analog')
    b.header('JVOL','EXTERNAL DUAL 10k A POT',
             ['OUT_AC_L','VOL_L',GND,'OUT_AC_R','VOL_R',GND],(99,150),'analog',rows=2,
             role='Stereo 10k A pot: each channel HIGH/WIPER/LOW. Separate from mute.')
    b.header('JLINE','TRS JACK / AMS-22 LINE IN',['LINE_L','LINE_R',GND],(162,151),'analog',
             role='External 3.5mm jack module, L=tip R=ring GND=sleeve. Not headphone power output.')
    for i,(net,xy) in enumerate([(V5,(38,145)),(V3,(48,145)),(GND,(58,145)),
          ('ARM',(86,40)),('RESET_N',(94,40)),('AUX_SDA',(55,55)),('AUX_SCL',(55,61)),
          ('DAC_L',(40,130)),('DAC_R',(50,130)),('VREF',(87,115)),
          ('MIX_L',(121,116)),('MIX_R',(121,121))],1):b.tp('TP'+str(i),net,xy)
    return b


def lcx(b,ref,signals,outs,xy,g,oe=GND):
    p={1:('DIR A>B',V3,'input'),10:('GND',GND,'power_in'),19:('OE_N',oe,'input'),20:('VCC',V3,'power_in')}
    for i in range(8):
        p[2+i]=(f'A{i+1}',signals[i] if i<len(signals) else GND,'input')
        p[18-i]=(f'B{i+1}',outs[i] if i<len(outs) else None,'output')
    return b.part(ref,'74LCX245FT / 3.3V',p,dict(kind='tssop',n=20,pitch=.65,width=6.4),xy,g,
                  source='https://akizukidenshi.com/goodsaffix/74LCX245FT_datasheet_ja_20150130.pdf')


def upmodule(b,ref,ins,outs,xy,oe=GND):
    p={1:('VA',V3,'power_in'),24:('VA',V3,'power_in'),23:('VB',V5,'power_in'),
       2:('OE_N',oe,'input'),3:('DIR A>B',V3,'input'),12:('GND',GND,'power_in'),
       13:('GND',GND,'power_in'),22:('GND',GND,'power_in')}
    for i in range(8):
        p[4+i]=(f'A{i+1}',ins[i] if i<len(ins) else GND,'input')
        p[21-i]=(f'B{i+1}',outs[i] if i<len(outs) else None,'tri_state')
    return b.ic(ref,'AE-LLCNV-LVC8T245',p,24,15.24,xy,'bus',
         'https://akizukidenshi.com/catalog/g/g115778/',body_extra=[18,31])


def make_card():
    b=Board('ym2203',(130,120),'YM2203C CARD / 4MHz / ID=001')
    nets=CONNECTOR.copy()
    for n in [17,30,32,33,35,39,40]:nets[n-1]=None
    # Native 3.3V ID: bit0 open=1, bit1/2 strapped=0; present strapped=0.
    for n in [36,37,38]:nets[n-1]=GND
    b.header('JMOD','TSW-125-07-L-D / header',nets,(120,15),'module',rows=2,
             source='https://suddendocs.samtec.com/catalog_english/tsw_th.pdf',
             underside=True,role='Bottom male; remove contact 50. 19mm face-to-face spacing gives 5.51mm insertion.')
    ym={i:(f'IO{i}',None,'bidirectional') for i in range(1,41)}
    for p in (1,17):ym[p]=('GND',GND,'power_in')
    ym[21]=('VDD',V5,'power_in')
    for i,p in enumerate([40,2,3,4,5,6,7,8]):ym[p]=(f'D{i}',f'Y_D{i}','bidirectional')
    for p,n in [(37,'A0'),(36,'RD_N'),(35,'WR_N'),(34,'CS_N'),(24,'RESET_N')]:ym[p]=(n,'Y_'+n,'input')
    for p,n in [(23,'SD'),(39,'CLK'),(22,'SH')]:ym[p]=(n,'Y_'+n,'output')
    ym[25]=('IRQ_N','Y_IRQ','open_collector')
    for p,n in [(20,'SSG_A'),(19,'SSG_B'),(18,'SSG_C')]:ym[p]=(n,n,'output')
    ym[38]=('PHI_M 4MHz','CLK4','input')
    for i in range(8):ym[16-i]=(f'IOA{i}',None,'bidirectional');ym[26+i]=(f'IOB{i}',None,'bidirectional')
    b.ic('U1','YM2203C / DIP40',ym,40,15.24,(78,15),'ym',
         'https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf')
    b.decouple(V5,(98,63),near=['U1',21]);b.c('10u 10V',V5,GND,(99,69),'ym',polar=True)
    upmodule(b,'A1',[f'D{i}' for i in range(8)],[f'Y_D{i}' for i in range(8)],(12,13),'OE_WRITE_N')
    upmodule(b,'A2',['A0','RESET_N','SAFE_CS_N','SAFE_WR_N','SAFE_RD_N'],
             ['Y_A0','Y_RESET_N','Y_CS_N','Y_WR_N','Y_RD_N'],(12,50))
    lcx(b,'U2',[f'Y_D{i}' for i in range(8)],[f'D{i}' for i in range(8)],(48,18),'bus','OE_READ_N')
    b.decouple(V3,(55,17))
    lcx(b,'U3',['Y_SD','Y_CLK','Y_SH','Y_IRQ'],['FM_SD','FM_CLK','FM_SH1','STATUS'],(48,42),'fm')
    b.decouple(V3,(55,41))
    # 3.3V logic. A separately gated native CS prevents accesses while ARM=0.
    p=powerpins({1:('1A','ARM','input'),2:('1Y','NOT_ARM','output'),
       3:('2A','RD_N','input'),4:('2Y','NOT_RD_N','output'),
       5:('3A',GND,'input'),6:('3Y',None,'output'),8:('4Y',None,'output'),
       9:('4A',GND,'input'),10:('5Y',None,'output'),11:('5A',GND,'input'),
       12:('6Y',None,'output'),13:('6A',GND,'input')},14,14,7)
    b.ic('U4','TC74HC04AP / 3.3V',p,14,7.62,(43,72),'safety',
         'https://akizukidenshi.com/catalog/g/g114058/')
    p=powerpins({1:('1A','ARM','input'),2:('1B','RD_N','input'),3:('1Y','OE_WRITE_N','output'),
       4:('2A','ARM','input'),5:('2B','NOT_RD_N','input'),6:('2Y','OE_READ_N','output'),
       8:('3Y',None,'output'),9:('3A',GND,'input'),10:('3B',GND,'input'),
       11:('4Y',None,'output'),12:('4A',GND,'input'),13:('4B',GND,'input')},14,14,7)
    b.ic('U5','TC74HC00AP / 3.3V',p,14,7.62,(60,72),'safety',
         'https://akizukidenshi.com/catalog/g/g110856/')
    p=powerpins({},14,14,7)
    for (a,bb,y),n in zip([(1,2,3),(4,5,6),(9,10,8)],['CS_N','WR_N','RD_N']):
        p[a]=(n,n,'input');p[bb]=('NOT_ARM','NOT_ARM','input');p[y]=('SAFE_'+n,'SAFE_'+n,'output')
    p.update({11:('4Y',None,'output'),12:('4A',GND,'input'),13:('4B',GND,'input')})
    b.ic('U6','TC74HC32AP / 3.3V',p,14,7.62,(77,72),'safety',
         'https://akizukidenshi.com/catalog/g/g112877/')
    for xy in [(55,72),(72,72),(89,72)]:b.decouple(V3,xy)
    b.rn('RN1',8,'10k',GND,[f'Y_D{i}' for i in range(8)],(38,57),'pulls')
    b.rn('RN2',4,'10k',V5,['Y_CS_N','Y_WR_N','Y_RD_N',None],(99,31),'pulls')
    b.r('4.7k','Y_RESET_N',GND,(96,40),'pulls')
    b.r('10k','Y_IRQ',V3,(60,47),'pulls')
    b.r('10k','ARM',GND,(61,62),'pulls')
    b.r('10k','OE_READ_N',V3,(61,56),'pulls')
    # Known 8MHz DIL8 oscillator + divide-by-two maintains a 50% nominal 4MHz clock.
    b.part('X1','8MHz 5V oscillator',{
           1:('NC',None,'passive'),4:('GND',GND,'power_in'),
           5:('OUT','OSC8','output'),8:('VCC',V5,'power_in')},
           dict(kind='dip8osc'),(12,88),'clock',
           source='https://akizukidenshi.com/goodsaffix/osc.pdf')
    b.decouple(V5,(25,89),'clock')
    b.r('47','OSC8','CLK8',(12,103),'clock')
    p={1:('CLR1_N',V5,'input'),2:('D1','CLK_FB','input'),3:('CLK1','CLK8','input'),
       4:('PRE1_N',V5,'input'),5:('Q1','DIV4','output'),6:('Q1_N','CLK_FB','output'),
       7:('GND',GND,'power_in'),8:('Q2_N',None,'output'),9:('Q2',None,'output'),
       10:('PRE2_N',V5,'input'),11:('CLK2',GND,'input'),12:('D2',GND,'input'),
       13:('CLR2_N',V5,'input'),14:('VCC',V5,'power_in')}
    b.ic('U7','TC74HC74AP / 5V',p,14,7.62,(12,65),'clock',
         'https://akizukidenshi.com/goodsaffix/TC74HC74AP_datasheet_ja_20140301.pdf')
    b.decouple(V5,(25,65),'clock')
    b.r('47','DIV4','CLK4',(67,9),'clock')
    # Local SSG mix normalizes all three channels; two isolated AC outputs to base.
    p={1:('OUTA','VREF_CARD','output'),2:('INA-','VREF_CARD','input'),
       3:('INA+','REF_CARD_RAW','input'),4:('VSS',GND,'power_in'),
       5:('INB+','VREF_CARD','input'),6:('INB-','SSG_SUM','input'),
       7:('OUTB','SSG_MIX','output'),8:('VDD',V5,'power_in')}
    b.ic('U8','MCP6022-I/P / SSG mixer',p,8,7.62,(101,83),'analog')
    b.decouple(V5,(114,83),'analog')
    b.r('10k 1%',V5,'REF_CARD_RAW',(97,74),'analog')
    b.r('10k 1%','REF_CARD_RAW',GND,(109,74),'analog')
    b.c('10u 10V','REF_CARD_RAW',GND,(114,92),'analog',polar=True)
    for i,s in enumerate(['SSG_A','SSG_B','SSG_C']):
        b.c('4.7u BP 10V',s,s+'_AC',(44+i*16,97),'analog')
        b.r('100k 1%',s+'_AC','SSG_SUM',(44+i*16,104),'analog')
    # The SSG analog pins need a defined DC load before the AC coupling.
    # 1k is the initial evaluation load (YM2149 family reference condition).
    b.rn('RN3',8,'1k',GND,['SSG_A','SSG_B','SSG_C']+[None]*5,(38,112),'analog')
    # 100k feedback gives unity per source; base then contributes -0.22.
    b.r('100k 1%','SSG_SUM','SSG_MIX',(97,99),'analog')
    b.c('47p','SSG_SUM','SSG_MIX',(109,99),'analog')
    for s,xy in [('ANALOG_L',(97,108)),('ANALOG_R',(110,108))]:
        b.c('4.7u BP 10V','SSG_MIX',s,xy,'analog')
        b.r('100k',s,GND,(97 if s.endswith('L') else 110,115),'analog')
    for i,(n,xy) in enumerate([(V5,(99,9)),(V3,(60,9)),(GND,(110,9)),
          ('CLK4',(73,9)),('Y_SD',(98,48)),('Y_CLK',(98,54)),('Y_SH',(98,60)),
          ('Y_IRQ',(67,49)),('OE_WRITE_N',(62,84)),('OE_READ_N',(73,84)),
          ('SSG_MIX',(117,99))],1):b.tp('TP'+str(i),n,xy)
    return b


def symbol(p,x,y,boardname):
    """Single-unit, all physical pins, connected labels; no implicit power pins."""
    x=round(round(x/1.27)*1.27,5);y=round(round(y/1.27)*1.27,5)
    ref=p['ref']; pins=p['pins']; count=len(pins)
    kind=p['footprint']['kind']
    passive=count==2 and kind in ('cap','axial','sma','smd2','smd2v','radial')
    hx=25.4 if not passive else 2.54
    cols=[pins[:math.ceil(count/2)], pins[math.ceil(count/2):]]
    if passive: cols=[[pins[0]],[pins[1]]]
    hy=max(5.08,(max(map(len,cols))+1)*2.54/2)
    g=f'(rectangle (start {-hx} {hy}) (end {hx} {-hy}) (stroke (width .25) (type default)) (fill (type background)))'
    def poly(points):
        return '(polyline (pts '+''.join(f'(xy {a} {b})' for a,b in points)+') (stroke (width .25) (type default)) (fill (type none)))'
    if passive and ref.startswith('C'):
        g=poly([(-2.54,0),(-.762,0)])+poly([(.762,0),(2.54,0)])
        g+=poly([(-.762,-2.54),(-.762,2.54)])+poly([(.762,-2.54),(.762,2.54)])
        if p.get('polar'):g+='(text "+" (at -2.54 3.81 0) (effects (font (size 1.27 1.27))))'
    elif passive and ref.startswith('R'):
        g='(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width .25) (type default)) (fill (type none)))'
    elif passive and ref.startswith('D'):
        g=poly([(-2.54,0),(-1.27,0)])+poly([(-1.27,-2.54),(-1.27,2.54)])
        g+=poly([(-1.27,0),(2.54,2.54),(2.54,-2.54),(-1.27,0)])
    ps=[]; it=[]; fx='(effects (font (size 1.27 1.27)))'
    for side,pp in enumerate(cols):
        for i,pin in enumerate(pp):
            px=(-1 if side==0 else 1)*(hx+5.08)
            py=0 if passive else hy-3.81-i*2.54
            a=0 if side==0 else 180
            ps.append(f'(pin {pin["type"]} line (at {px} {py} {a}) (length 5.08) (name {Q(pin["name"])} {fx}) (number {Q(pin["num"])} {fx}))')
            gx,gy=round(x+px,5),round(y-py,5)
            tag=f'{boardname}:{ref}:{pin["num"]}'
            if pin['net'] is None:
                it.append(f'(no_connect (at {gx} {gy}) (uuid {UID(tag+"NC")}))')
            else:
                xx=round(gx+(-7.62 if side==0 else 7.62),5)
                it.append(f'(wire (pts (xy {gx} {gy}) (xy {xx} {gy})) (stroke (width 0) (type default)) (uuid {UID(tag+"W")}))')
                just='right bottom' if side==0 else 'left bottom'
                it.append(f'(label {Q(pin["net"])} (at {xx} {gy} {a}) (effects (font (size 1.27 1.27)) (justify {just})) (uuid {UID(tag+"L")}))')
    key='SOUNDPCB:'+ref; root=UID(boardname)
    lib=f'(symbol {Q(key)} (pin_names (offset .6)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) {fx}) (property "Value" {Q(p["value"])} (at 0 0 0) {fx}) (symbol {Q(ref+"_1_1")} {g} '+''.join(ps)+'))'
    sid=UID(boardname+':'+ref)
    fpname='SOUNDPCB:'+ref
    physical=not ref.startswith('#')
    it.append(f'(symbol (lib_id {Q(key)}) (at {x} {y} 0) (unit 1) (in_bom {"yes" if physical else "no"}) (on_board {"yes" if physical else "no"}) (dnp no) (uuid {sid})'
              f'(property "Reference" {Q(ref)} (at {x} {y-hy-3.81} 0) {fx})'
              f'(property "Value" {Q(p["value"])} (at {x} {y+hy+3.81} 0) {fx})'
              f'(property "Footprint" {Q(fpname if physical else "")} (at {x} {y} 0) (effects (font (size 1 1)) hide))'
              f'(instances (project {Q(boardname)} (path "/{root}" (reference {Q(ref)}) (unit 1)))))')
    return lib,it,hy


def export_schematic(b):
    # Six panels on A0: each group flows in a separate column, pin labels never overlap.
    groups=[['controller','io'],['power','safety'],['module'],['dac','clock'],['analog'],['pulls','decoupling','bus','ym','fm','test']]
    if b.name=='ym2203':groups=[['ym'],['bus'],['fm','safety'],['module'],['analog','clock'],['pulls','decoupling','test']]
    libs=[];items=[]
    def note(t,x,y,size=2):
        items.append(f'(text {Q(t)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {UID(b.name+t)}))')
    note(b.title,20,20,4)
    note('Rev A / GPIO approved 2026-10-18 / Prototype - hardware untested / See README before manufacture',20,30)
    note('Labels of the same name are connected. Pin numbers are physical pins. Stereo line output to AMS-22.',20,38)
    ys=[70]*len(groups)
    for col,gg in enumerate(groups):
        pp=[p for p in b.parts if p['group'] in gg]
        x=94+col*194
        note(' / '.join(gg).upper(),x-70,52,2.5)
        for p in pp:
            h=max(5.08,(math.ceil(len(p['pins'])/2)+1)*2.54/2)
            target=col if ys[col]+2*h+19.05<790 else min(range(len(groups)),key=lambda k:ys[k])
            if ys[target]+2*h+19.05>790:raise ValueError((b.name,col,p['ref'],ys))
            lib,it,_=symbol(p,94+target*194,round(ys[target]+h,5),b.name)
            libs.append(lib);items+=it;ys[target]+=2*h+19.05
    # Rail flags are explicit and excluded from the physical BOM.
    for i,n in enumerate([GND,V5,'VSYS'] if b.name=='base' else [GND,V5,V3]):
        flag=dict(ref=f'#FLG{i}',value='POWER FLAG',pins=[dict(num='1',name=n,net=n,type='power_out')],footprint=dict(kind='flag'))
        l,it,h=symbol(flag,700+i*100,817,b.name);libs.append(l);items+=it
    sch=b.dir/(b.name+'.kicad_sch')
    sch.write_text(f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {UID(b.name)}) (paper "A0") (lib_symbols '+''.join(libs)+')\n'+'\n'.join(items)+'\n(embedded_fonts no))\n')
    pro=dict(board=dict(design_settings=dict(rules=dict(min_clearance=.2,min_track_width=.18,
         min_via_diameter=.7,min_via_drill=.3,min_hole_clearance=.25,min_copper_edge_clearance=.5))),
         net_settings=dict(classes=[dict(name='Default',clearance=.2,track_width=.25,via_diameter=.7,via_drill=.3,
         diff_pair_width=.25,diff_pair_gap=.25,diff_pair_via_gap=.25,wire_width=6,bus_width=12,pcb_color='rgba(0, 0, 0, 0)',schematic_color='rgba(0, 0, 0, 0)')]))
    (b.dir/(b.name+'.kicad_pro')).write_text(json.dumps(pro,indent=2)+'\n')
    libtext=''.join(l.replace('(symbol "SOUNDPCB:','(symbol "',1) for l in libs)
    (b.dir/'SOUNDPCB.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+libtext+')\n')
    (b.dir/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "SOUNDPCB") (type "KiCad") (uri "${KIPRJMOD}/SOUNDPCB.kicad_sym") (options "") (descr "Original prototype symbols")))\n')
    for args in [
        ['netlist','--format','kicadxml','-o',str(b.dir/'netlist.xml')],
        ['erc','--format','json','-o',str(b.dir/'erc.json')],
        ['svg','--no-background-color','--exclude-drawing-sheet','--default-font','Arial Unicode MS','-o',str(b.dir)],
        ['pdf','--no-background-color','--exclude-drawing-sheet','--default-font','Arial Unicode MS','-o',str(b.dir/(b.name+'-schematic.pdf'))],
    ]:
        cmd=['kicad-cli','sch',args[0]] if args[0]=='erc' else ['kicad-cli','sch','export',args[0]]
        r=subprocess.run(cmd+args[1:]+[str(sch)],capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    # Compare complete physical pin sets, not just net counts.
    expected=defaultdict(set)
    for p in b.parts:
        for pin in p['pins']:
            if pin['net'] is not None:expected[pin['net']].add((p['ref'],pin['num']))
    actual={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node') if not p.attrib['ref'].startswith('#')}
            for n in ET.parse(b.dir/'netlist.xml').findall('./nets/net')}
    actual={n:v for n,v in actual.items() if v and not n.startswith('unconnected-')}
    assert dict(expected)==actual,(b.name,{n:expected[n]^actual.get(n,set()) for n in expected if expected[n]!=actual.get(n)})
    b.nets=len(expected)


def main():
    make_base();make_card()
    for b in BOARDS.values():
        holes=[(5,5),(125,5),(5,115),(125,108)] if b.name=='ym2203' else [(55,5),(175,5),(55,115),(175,108),(5,5),(5,155),(175,155)]
        for i,xy in enumerate(holes,1):
            b.part('H'+str(i),'M3 / 3.2mm NPTH',{},
                   dict(kind='hole'),xy,'test')
    # Approval is recorded in human-visible docs as well as the machine-readable design.
    design=dict(revision='A',date='2026-10-18',gpio_approved=True,
                power_source='external_regulated_5v',
                gpio=[dict(gpio=g,pico_pin=PHYS[g],signal=s) for g,s in GPIO],
                connector=[dict(pin=i+1,signal=s) for i,s in enumerate(CONNECTOR)],
                boards={n:dict(size_mm=b.size,parts=b.parts) for n,b in BOARDS.items()})
    (OUT/'design.json').write_text(json.dumps(design,ensure_ascii=False,indent=2)+'\n')
    for fn,rows in [('gpio.csv',design['gpio']),('connector.csv',design['connector'])]:
        with (OUT/fn).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for b in BOARDS.values():
        export_schematic(b)
        rows=[]
        for p in b.parts:
            rows.append(dict(reference=p['ref'],value=p['value'],footprint='SOUNDPCB:'+p['ref'],
                             x_mm=p['xy'][0],y_mm=p['xy'][1],source=p['source'],role=p.get('role','')))
        with (b.dir/'bom.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        print(b.name,len(b.parts),'parts',b.nets,'nets',flush=True)


if __name__=='__main__':main()
