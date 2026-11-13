"""Generate the dedicated YM2203C / Pico 2 single-board prototype.

GPIO allocation was explicitly approved on 2026-10-18. Original CAD helpers
are reused from the preceding two-board design and included for reproducibility.
"""
from pathlib import Path
import csv, json
from cad import Board, OUT, GND, V3, V5, powerpins, lcx, upmodule, export_schematic

GPIO=[(n,f'D{n}') for n in range(8)]+[
 (8,'A0'),(9,'RESET_RELEASE'),(10,'I2S_DATA'),(11,'I2S_BCLK'),(12,'I2S_LRCK'),
 (13,'CS_N'),(14,'WR_N'),(15,'RD_N'),(16,'FM_SD'),(17,'FM_CLK'),(18,'FM_SH'),
 (19,'LINE_ALLOW'),(20,'HOST_SDA'),(21,'HOST_SCL'),(22,'ARM'),(26,'DAC_ALLOW'),(28,'IRQ_N')]
PHYS=dict(zip(list(range(23))+[26,27,28],
 [1,2,4,5,6,7,9,10,11,12,14,15,16,17,19,20,21,22,24,25,26,27,29,31,32,34]))


def make_board():
    b=Board('ym2203-single',(160,120),'YM2203C SINGLE BOARD / Pico 2 / I2C + USB-MIDI / MONO LINE OUT')
    gp={PHYS[g]:(f'GP{g} / {s}',s,'bidirectional') for g,s in GPIO}
    for p in (3,8,13,18,23,28,33,38):gp[p]=('GND',GND,'power_in')
    gp.update({30:('RUN','PICO_RUN','input'),32:('GP27 / RESERVED',None,'bidirectional'),
      35:('ADC_VREF',None,'passive'),36:('3V3 OUT',V3,'power_out'),37:('3V3_EN',None,'input'),
      39:('VSYS','VSYS','power_in'),40:('USB VBUS',None,'power_out')})
    b.ic('A1','Raspberry Pi Pico 2',gp,40,17.78,(10,13),'controller',
      'https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf',body_extra=[21,51],
      role='USB-MIDI uses the onboard USB connector; requires C/C++ firmware.')
    b.header('JHOST','HOST 3.3V I2C',[GND,'HOST_SDA','HOST_SCL',GND],(8,68),'io',
      role='1=GND 2=SDA 3=SCL 4=GND. Host supply not connected.')
    b.header('JRUN','RESET SWITCH',['PICO_RUN',GND],(8,75),'io')
    b.part('JPOWER','AE-USB2.0-TYPE-C / 5V POWER ONLY',{
      1:('VBUS','USB_VBUS','passive'),2:('D-',None,'passive'),3:('D+',None,'passive'),
      4:('GND',GND,'passive'),5:('CC1','USB_CC1','passive'),6:('CC2','USB_CC2','passive'),7:('GND',GND,'passive')},
      dict(kind='usb_c_module'),(33,108.34),'power',
      source='https://akizukidenshi.com/catalog/g/g113080/',fixed=True,
      role='Dedicated 5V input from USB AC adapter. Data pins NC. CC1/CC2 each have separate 5.1k Rd. Rear 7-pin header plus two 2-pin VBUS/GND support headers. Mouth toward bottom edge; no PD negotiation.')
    b.passive('F','PTC 0.5A hold','USB_VBUS','USB_FUSED',(36,102),'power')
    b.part('U11','TPS22918DBVR / soft-start',{
      1:('VIN','USB_FUSED','power_in'),2:('GND',GND,'power_in'),3:('ON','USB_FUSED','input'),
      4:('CT','USB_CT','passive'),5:('QOD',None,'passive'),6:('VOUT',V5,'power_out')},
      dict(kind='sot23_6'),(51,102),'power',source='https://www.ti.com/lit/ds/symlink/tps22918.pdf',
      role='Automatic startup: ON=VIN. CT=10nF/25V or higher, about 26.6ms typical 10-90% at 5V. QOD disabled. Slew control only; not a current limiter, reverse-current or overvoltage protector.')
    b.part('D1','SS14 / A=+5V K=VSYS',{1:('K','VSYS','passive'),2:('A',V5,'passive')},
      dict(kind='sma'),(40,111),'power',role='Blocks USB-to-main-supply backfeed through VSYS.')
    b.c('47u 10V',V5,GND,(48,113),'power',polar=True)
    b.c('10u 10V',V3,GND,(56,113),'power',polar=True)
    b.r('4.7k','HOST_SDA',V3,(19,69),'controller',role='Omit if host provides the bus pullup.')
    b.r('4.7k','HOST_SCL',V3,(19,75),'controller',role='Omit if host provides the bus pullup.')

    ym={i:(f'IO{i}',None,'bidirectional') for i in range(1,41)}
    for pin in (1,17):ym[pin]=('GND',GND,'power_in')
    ym[21]=('VDD',V5,'power_in')
    for i,pin in enumerate([40,2,3,4,5,6,7,8]):ym[pin]=(f'D{i}',f'Y_D{i}','bidirectional')
    for pin,n in [(37,'A0'),(36,'RD_N'),(35,'WR_N'),(34,'CS_N'),(24,'RESET_N')]:ym[pin]=(n,'Y_'+n,'input')
    for pin,n in [(23,'SD'),(39,'CLK'),(22,'SH')]:ym[pin]=(n,'Y_'+n,'output')
    ym[25]=('IRQ_N','Y_IRQ','open_collector')
    for pin,n in [(20,'SSG_A'),(19,'SSG_B'),(18,'SSG_C')]:ym[pin]=(n,n,'output')
    ym[38]=('PHI_M 4MHz','CLK4','input')
    for i in range(8):ym[16-i]=(f'IOA{i}',None,'bidirectional');ym[26+i]=(f'IOB{i}',None,'bidirectional')
    b.ic('U1','YM2203C / DIP40',ym,40,15.24,(110,13),'ym',
      'https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf')
    b.decouple(V5,(129,62),'ym',near=['U1',21]);b.c('10u 10V',V5,GND,(136,65),'ym',polar=True)
    upmodule(b,'A3',[f'D{i}' for i in range(8)],[f'Y_D{i}' for i in range(8)],(42,14),'OE_WRITE_N')
    upmodule(b,'A4',['A0','RESET_N','SAFE_CS_N','SAFE_WR_N','SAFE_RD_N'],
      ['Y_A0','Y_RESET_N','Y_CS_N','Y_WR_N','Y_RD_N'],(67,14))
    lcx(b,'U2',[f'Y_D{i}' for i in range(8)],[f'D{i}' for i in range(8)],(94,19),'bus','OE_READ_N')
    b.decouple(V3,(101,19),'bus',near=['U2',20])
    lcx(b,'U3',['Y_SD','Y_CLK','Y_SH','Y_IRQ'],['FM_SD','FM_CLK','FM_SH','IRQ_N'],(95,42),'fm')
    b.decouple(V3,(102,42),'fm',near=['U3',20])
    p=powerpins({1:('1A','ARM','input'),2:('1Y','NOT_ARM','output'),3:('2A','RD_N','input'),4:('2Y','NOT_RD_N','output'),
      5:('3A',GND,'input'),6:('3Y',None,'output'),8:('4Y',None,'output'),9:('4A',GND,'input'),
      10:('5Y',None,'output'),11:('5A',GND,'input'),12:('6Y',None,'output'),13:('6A',GND,'input')},14,14,7)
    b.ic('U4','TC74HC04AP / 3.3V',p,14,7.62,(40,61),'safety','https://akizukidenshi.com/catalog/g/g114058/')
    p=powerpins({1:('1A','ARM','input'),2:('1B','RD_N','input'),3:('1Y','OE_WRITE_N','output'),
      4:('2A','ARM','input'),5:('2B','NOT_RD_N','input'),6:('2Y','OE_READ_N','output'),
      8:('3Y',None,'output'),9:('3A',GND,'input'),10:('3B',GND,'input'),
      11:('4Y',None,'output'),12:('4A',GND,'input'),13:('4B',GND,'input')},14,14,7)
    b.ic('U5','TC74HC00AP / 3.3V',p,14,7.62,(57,61),'safety','https://akizukidenshi.com/catalog/g/g110856/')
    p=powerpins({},14,14,7)
    for (a,bb,y),n in zip([(1,2,3),(4,5,6),(9,10,8)],['CS_N','WR_N','RD_N']):
      p[a]=(n,n,'input');p[bb]=('NOT_ARM','NOT_ARM','input');p[y]=('SAFE_'+n,'SAFE_'+n,'output')
    p.update({11:('4Y',None,'output'),12:('4A',GND,'input'),13:('4B',GND,'input')})
    b.ic('U6','TC74HC32AP / 3.3V',p,14,7.62,(74,61),'safety','https://akizukidenshi.com/catalog/g/g112877/')
    p=powerpins({1:('1A','ARM','input'),2:('1B','RESET_RELEASE','input'),3:('1Y','RESET_N','output'),
      4:('2A','ARM','input'),5:('2B','DAC_ALLOW','input'),6:('2Y','DAC_XSMT','output'),
      8:('3Y','LINE_RUN','output'),9:('3A','ARM','input'),10:('3B','LINE_ALLOW','input'),
      11:('4Y',None,'output'),12:('4A',GND,'input'),13:('4B',GND,'input')},14,14,7)
    b.ic('U10','TC74HC08AP / 3.3V',p,14,7.62,(60,90),'safety','https://akizukidenshi.com/catalog/g/g114059/')
    for ref,xy in [('U4',(51,61)),('U5',(68,61)),('U6',(85,61)),('U10',(71,90))]:b.decouple(V3,xy,'safety',near=[ref,14])
    b.rn('RN1',8,'10k',GND,[f'D{i}' for i in range(8)],(35,51),'pulls')
    b.rn('RN2',8,'10k',GND,['ARM','A0','RESET_RELEASE','DAC_ALLOW','LINE_ALLOW','FM_SD','FM_CLK','FM_SH'],(37,45),'pulls')
    b.rn('RN3',4,'10k',V3,['CS_N','WR_N','RD_N','IRQ_N'],(72,105),'pulls')
    b.rn('RN4',4,'10k',V5,['Y_CS_N','Y_WR_N','Y_RD_N',None],(136,30),'pulls')
    b.rn('RN6',8,'10k',GND,[f'Y_D{i}' for i in range(8)],(65,51),'pulls')
    b.r('4.7k','Y_RESET_N',GND,(130,36),'pulls')
    b.r('10k','Y_IRQ',V3,(100,51),'pulls')
    b.r('10k','OE_READ_N',V3,(58,56),'pulls')
    b.r('10k','DAC_XSMT',GND,(38,83),'pulls')
    b.part('X1','8MHz 5V oscillator',{1:('NC',None,'passive'),4:('GND',GND,'power_in'),
      5:('OUT','OSC8','output'),8:('VCC',V5,'power_in')},dict(kind='dip8osc'),(136,14),'clock',
      source='https://akizukidenshi.com/goodsaffix/osc.pdf')
    b.decouple(V5,(149,14),'clock',near=['X1',8]);b.r('47','OSC8','CLK8',(136,35),'clock')
    p={1:('CLR1_N',V5,'input'),2:('D1','CLK_FB','input'),3:('CLK1','CLK8','input'),4:('PRE1_N',V5,'input'),
      5:('Q1','DIV4','output'),6:('Q1_N','CLK_FB','output'),7:('GND',GND,'power_in'),
      8:('Q2_N',None,'output'),9:('Q2',None,'output'),10:('PRE2_N',V5,'input'),11:('CLK2',GND,'input'),
      12:('D2',GND,'input'),13:('CLR2_N',V5,'input'),14:('VCC',V5,'power_in')}
    b.ic('U7','TC74HC74AP / 5V',p,14,7.62,(135,41),'clock','https://akizukidenshi.com/goodsaffix/TC74HC74AP_datasheet_ja_20140301.pdf')
    b.decouple(V5,(148,41),'clock',near=['U7',14]);b.r('47','DIV4','CLK4',(130,26),'clock')

    dn={1:('CPVDD',V3,'power_in'),2:('CAPP','CAPP','passive'),3:('CPGND',GND,'power_in'),
      4:('CAPM','CAPM','passive'),5:('VNEG','VNEG','power_out'),6:('OUTL','DAC_L','output'),7:('OUTR',None,'output'),
      8:('AVDD',V3,'power_in'),9:('AGND',GND,'power_in'),10:('DEMP',GND,'input'),11:('FLT',GND,'input'),
      12:('SCK',GND,'input'),13:('BCK','DAC_BCK','input'),14:('DIN','DAC_DIN','input'),15:('LRCK','DAC_LRCK','input'),
      16:('FMT',GND,'input'),17:('XSMT','DAC_XSMT','input'),18:('LDOO','LDOO','power_out'),
      19:('DGND',GND,'power_in'),20:('DVDD',V3,'power_in')}
    b.ic('A2','AE-PCM5102A / I2S 48kHz',dn,20,15.24,(10,82),'dac',
      'https://akizukidenshi.com/catalog/g/g111836/',body_extra=[17.5,25.5],role='OUTL used; OUTR intentionally unconnected. Not AE-DAC5102.')
    for i,(s,d) in enumerate([('I2S_DATA','DAC_DIN'),('I2S_BCLK','DAC_BCK'),('I2S_LRCK','DAC_LRCK')]):b.r('47',s,d,(30,96+i*6),'dac')
    pump=b.c('2.2u X7R 10V','CAPP','CAPM',(5,85.5),'dac');pump['footprint']['kind']='smd2v'
    b.c('2.2u X7R 10V','VNEG',GND,(5,93),'dac');b.c('1u X7R 10V','LDOO',GND,(30,88),'dac')
    for xy,pin in [((5,81),1),((5,100),8),((30,81),20)]:b.decouple(V3,xy,'dac',near=['A2',pin])
    for xy in [(6,74),(6,108),(30,94)]:b.c('10u 10V',V3,GND,xy,'dac',polar=True)
    b.r('470','DAC_L','FM_FILTER',(48,83),'analog');b.c('2.2n C0G','FM_FILTER',GND,(55,83),'analog')

    p={1:('OUTA','VREF','output'),2:('INA-','VREF','input'),3:('INA+','REF_RAW','input'),4:('VSS',GND,'power_in'),
      5:('INB+','VREF','input'),6:('INB-','SUM_MONO','input'),7:('OUTB','MIX_MONO','output'),8:('VDD',V5,'power_in')}
    b.ic('U8','MCP6022-I/P / reference + mono mixer',p,8,7.62,(104,86),'analog',
      'https://akizukidenshi.com/goodsaffix/MCP6022.pdf')
    b.decouple(V5,(116,86),'analog',near=['U8',8])
    b.r('10k 1%',V5,'REF_RAW',(91,94),'analog');b.r('10k 1%','REF_RAW',GND,(91,100),'analog')
    b.c('10u 10V','REF_RAW',GND,(104,101),'analog',polar=True)
    for i,s in enumerate(['SSG_A','SSG_B','SSG_C','FM_FILTER']):
      x=80+i*17
      b.c('4.7u BP 10V',s,s+'_AC',(x,74),'analog')
      b.r('100k 1%',s+'_AC','SUM_MONO',(x,80),'analog')
    b.rn('RN5',8,'1k',GND,['SSG_A','SSG_B','SSG_C']+[None]*5,(100,68),'analog')
    b.r('22k 1%','MIX_MONO','SUM_MONO',(117,96),'analog');b.c('47p','MIX_MONO','SUM_MONO',(124,96),'analog')
    p={1:('Y1',GND,'passive'),2:('Y0',GND,'passive'),3:('Z1',GND,'passive'),4:('Z',None,'passive'),
      5:('Z0',GND,'passive'),6:('INH',GND,'input'),7:('VEE',GND,'power_in'),8:('GND',GND,'power_in'),
      9:('C',GND,'input'),10:('B',GND,'input'),11:('A','MUTE_5V','input'),12:('X0','MIX_MONO','passive'),
      13:('X1','VREF','passive'),14:('X','MUTED_MONO','passive'),15:('Y',None,'passive'),16:('VCC',V5,'power_in')}
    b.ic('U9','CD74HC4053E / line mute',p,16,7.62,(130,86),'analog','https://akizukidenshi.com/catalog/g/g113266/')
    b.decouple(V5,(142,86),'analog',near=['U9',16])
    b.part('Q1','MMBT3904 / B1 E2 C3',{1:('B','MUTE_BASE','input'),2:('E',GND,'passive'),3:('C','MUTE_5V','open_collector')},
      dict(kind='sot23'),(148,76),'safety',source='https://www.onsemi.com/pdf/datasheet/mmbt3904lt1-d.pdf')
    b.r('10k','LINE_RUN','MUTE_BASE',(148,67),'safety');b.r('100k','MUTE_BASE',GND,(148,62),'safety')
    b.r('10k',V5,'MUTE_5V',(148,81),'safety')
    b.c('4.7u BP 10V','MUTED_MONO','OUT_AC',(145,101),'analog')
    b.r('100k','OUT_AC',GND,(145,108),'analog')
    b.part('RV1','RK0971220-F15-C0-A103 / dual A10k',{
      1:('R1 CCW',GND,'passive'),2:('R1 WIPER','VOL_L','passive'),3:('R1 CW','OUT_AC','passive'),
      4:('R2 CCW',GND,'passive'),5:('R2 WIPER','VOL_R','passive'),6:('R2 CW','OUT_AC','passive')},
      dict(kind='rk097_dual'),(96,118.5),'io',
      source='https://akizukidenshi.com/catalog/g/g103604/',fixed=True,
      role='On-board dual A10k. Pins 1/2/3=R1 CCW/wiper/CW; 4/5/6=R2. Shaft toward bottom edge. Same mono input to both gangs; wipers remain separate.')
    for ch,y in [('L',108),('R',113)]:b.r('100','VOL_'+ch,'LINE_'+ch,(130,y),'analog')
    b.part('JLINE','ST-005-G / 3.5mm TRS LINE OUT',{
      2:('RING','LINE_R','passive'),3:('SLEEVE',GND,'passive'),4:('TIP','LINE_L','passive')},
      dict(kind='st005g'),(145,120),'io',
      source='https://akizukidenshi.com/catalog/g/g102460/',fixed=True,
      role='On-board TRS: maker terminal 2=RING 3=SLEEVE 4=TIP (two physical legs). No terminal 1: maker item 1 is the housing. Mouth toward bottom edge; line output only.')
    # Append new passives to preserve Rev B resistor/capacitor reference numbers.
    b.r('5.1k 1%','USB_CC1',GND,(27,102),'power',role='USB-C sink Rd; CC1 and CC2 must not be joined.')
    b.r('5.1k 1%','USB_CC2',GND,(20,102),'power',role='USB-C sink Rd; independent of CC1. No PD negotiation or source-current detection.')
    b.c('1u 10V X7R','USB_FUSED',GND,(47,98),'power',near=['U11',1])
    b.c('10n 25V X7R','USB_CT',GND,(57,102),'power',role='TPS22918 controlled-rise CT. Use 25V or higher voltage rating.')
    for i,(net,xy) in enumerate([(V5,(45,108)),(V3,(54,108)),(GND,(62,113)),('ARM',(70,83)),
      ('RESET_N',(84,83)),('Y_SD',(128,46)),('Y_CLK',(128,51)),('Y_SH',(128,56)),
      ('CLK4',(128,20)),('MIX_MONO',(116,102)),('VREF',(116,108)),('DAC_L',(38,94))],1):b.tp('TP'+str(i),net,xy)
    for i,xy in enumerate([(5,5),(155,5),(5,115),(155,115)],1):b.part('H'+str(i),'M3 / 3.2mm NPTH',{},dict(kind='hole'),xy,'test')
    return b


def main():
    b=make_board()
    d=dict(revision='C',date='2026-10-18',gpio_approved=True,power_source='dedicated_usb_c_5v',
      gpio=[dict(gpio=g,pico_pin=PHYS[g],signal=s) for g,s in GPIO],reserved_gpio=[27],
      interfaces=['3.3V I2C slave','USB-MIDI 1.0 device (firmware required)'],
      audio='FM + SSG mono sum, same signal to line L/R',
      boards={b.name:dict(size_mm=b.size,parts=b.parts)})
    (OUT/'design.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'gpio.csv').open('w',newline='',encoding='utf-8-sig') as f:
      w=csv.DictWriter(f,fieldnames=['gpio','pico_pin','signal']);w.writeheader();w.writerows(d['gpio'])
    export_schematic(b)
    rows=[dict(reference=p['ref'],value=p['value'],footprint='SOUNDPCB:'+p['ref'],x_mm=p['xy'][0],y_mm=p['xy'][1],source=p['source'],role=p.get('role','')) for p in b.parts]
    with (b.dir/'bom.csv').open('w',newline='',encoding='utf-8-sig') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(b.name,len(b.parts),'physical objects;',b.nets,'nets')

if __name__=='__main__':main()
