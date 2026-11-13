"""A reading drawing of the manufactured Rev C netlist; never edits PCB files.

Every non-power net is drawn as a continuous wire tree. Standard repeated supply
and ground symbols denote the three shared rails. Pin membership and routed
connectivity are independently checked against design.json and the KiCad XML.
"""
from pathlib import Path
from collections import defaultdict
import json, math, heapq, hashlib, html, xml.etree.ElementTree as ET
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A0, A3, landscape
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
PDF = OUT / 'pdf'
OUT.mkdir(exist_ok=True); PDF.mkdir(exist_ok=True)
DESIGN = ROOT / 'rev-c/design.json'
NETLIST = ROOT / 'rev-c/ym2203-single/netlist.xml'
parts = json.loads(DESIGN.read_text())['boards']['ym2203-single']['parts']
P = {p['ref']: p for p in parts}
pins = {(p['ref'], v['num']): v for p in parts for v in p['pins']}
W, H, GRID = 4800, 3400, 4
INK, WIRE, MUTED = '#162c3c', '#087469', '#586a77'
POWER = {'GND', '+5V', '+3V3'}
shapes, labels, obstacles, ports, power_marks = [], [], [], {}, []


def line(points, color=INK, width=1.8, net=None, dash=None):
    shapes.append(('line', points, color, width, net, dash))


def rect(x, y, w, h, fill='#ffffff', stroke=INK, width=1.8):
    shapes.append(('rect', (x, y, w, h), fill, stroke, width))


def circle(x, y, r, fill='#ffffff', stroke=INK, width=1.8):
    shapes.append(('circle', (x, y, r), fill, stroke, width))


def text(s, x, y, size=16, color=INK, anchor='start'):
    labels.append((str(s), x, y, size, color, anchor))


def pin(ref, nums, x, y, side, name=None):
    nums = [str(n) for n in (nums if isinstance(nums, (list, tuple)) else [nums])]
    n = pins[ref, nums[0]]['net']
    assert all(pins[ref, num]['net'] == n for num in nums)
    dx, dy = {'L': (-24, 0), 'R': (24, 0), 'T': (0, -24), 'B': (0, 24)}[side]
    tip = (x+dx, y+dy)
    line([(x, y), tip], WIRE if n else MUTED, 1.8, n)
    for num in nums:
        assert (ref, num) not in ports, (ref, num)
        ports[ref, num] = dict(x=tip[0], y=tip[1], side=side, net=n)
    number = ','.join(nums)
    if side in 'LR':
        text(number, x + (-8 if side == 'L' else 8), y-5, 10, MUTED, 'end' if side == 'L' else 'start')
        if name:
            text(name, x + (10 if side == 'L' else -10), y+5, 14, INK, 'start' if side == 'L' else 'end')
    else:
        text(number, x+6, y + (-9 if side == 'T' else 16), 10, MUTED)
        if name: text(name, x, y + (18 if side == 'T' else -10), 12, INK, 'middle')
    if n is None:
        obstacles.append((tip[0]-8,tip[1]-8,tip[0]+8,tip[1]+8))
        line([(tip[0]-4, tip[1]-4), (tip[0]+4, tip[1]+4)], MUTED)
        line([(tip[0]-4, tip[1]+4), (tip[0]+4, tip[1]-4)], MUTED)
    elif n in POWER:
        power_marks.append((tip[0], tip[1], n, side))
    return tip


def box(ref, x, y, w, h, left=(), right=(), title=None, unit='', complete=True):
    # Port lists: (physical pin or list, offset from top, optional displayed name).
    if ref=='U8' and unit in ('A','B'):
        line([(x,y),(x,y+h),(x+w,y+80),(x,y)],INK,2.2)
    elif ref=='Q1':
        line([(x,y+48),(x+64,y+48),(x+64,y+16),(x+64,y+96)],INK,2.2)
        line([(x+64,y+40),(x+152,y+32),(x+w,y+32)],INK,2.2)
        line([(x+64,y+72),(x+152,y+96),(x+w,y+96)],INK,2.2)
        line([(x+132,y+80),(x+152,y+96),(x+126,y+98)],INK,2.2)
    else:
        rect(x, y, w, h, '#f6fafb')
    obstacles.append((x-8, y-8, x+w+8, y+h+8))
    text(ref+unit, x, y-28, 20)
    text(title or P[ref]['value'], x, y-8, 13, MUTED)
    for side, specs in [('L', left), ('R', right)]:
        for nums, yy, name in specs:
            if ref=='U8' and unit in ('A','B'): name='+' if '+' in name else '-' if '-' in name else ''
            pin(ref, nums, x if side == 'L' else x+w, y+yy, side, name)
    if complete:
        # Power and unused pins, explicitly numbered and never hidden.
        remain = [p for p in P[ref]['pins'] if (ref, p['num']) not in ports]
        grouped = defaultdict(list)
        for p in remain:
            if p['net'] in POWER: grouped[p['net']].append(p['num'])
            elif p['net'] is None: grouped[('NC', p['num'])].append(p['num'])
            else: raise AssertionError(('Unplaced signal pin', ref, p))
        # Separate power/unused-pin unit avoids cluttering the functional symbol.
        if grouped:
            rx, ry = x, y+h+80
            rw, rh = w, max(96, (len(grouped)+1)*24)
            rect(rx, ry, rw, rh, '#fcfcfc', '#a8b4bd', 1)
            obstacles.append((rx-8, ry-8, rx+rw+8, ry+rh+8))
            text(ref+' / power, unused', rx+8, ry+20, 12, MUTED)
            for i, (n, nums) in enumerate(grouped.items()):
                pin(ref, nums, rx, ry+48+i*24, 'L', n if isinstance(n, str) else pins[ref, nums[0]]['name'])


def passive(ref, x, y, vertical=False, label=None):
    value = label or P[ref]['value']
    # Terminal 1 is left/top; terminal 2 right/bottom, except a separately drawn D1.
    if vertical:
        line([(x,y-32),(x,y-12)]); line([(x,y+12),(x,y+32)])
        if ref.startswith('C'):
            line([(x-13,y-5),(x+13,y-5)]);line([(x-13,y+5),(x+13,y+5)])
        else: rect(x-7,y-12,14,24)
        endpoints=[(x,y-32,'T'),(x,y+32,'B')]
        text(ref,x+19,y-5,14);text(value,x+19,y+14,12,MUTED)
        obstacles.append((x-16,y-20,x+max(100,len(value)*7+22),y+22))
    else:
        line([(x-40,y),(x-14,y)]);line([(x+14,y),(x+40,y)])
        if ref.startswith('C'):
            line([(x-5,y-13),(x-5,y+13)]);line([(x+5,y-13),(x+5,y+13)])
        else: rect(x-14,y-7,28,14)
        endpoints=[(x-40,y,'L'),(x+40,y,'R')]
        text(ref,x,y-27,14,anchor='middle');text(value,x,y-11,12,MUTED,'middle')
        obstacles.append((x-24,y-44,x+24,y+20))
    for num,(xx,yy,side) in zip(['1','2'],endpoints):
        assert (ref,num) not in ports
        n=pins[ref,num]['net'];ports[ref,num]=dict(x=xx,y=yy,side=side,net=n)
        text(num,xx+5,yy-5,9,MUTED)
        if n in POWER:power_marks.append((xx,yy,n,side))
    if P[ref].get('polar'):
        text('+',x-20 if not vertical else x-17,y-16 if not vertical else y-9,15)


def rn(ref,x,y,vertical=False):
    p=P[ref];n=len(p['pins'])-1
    if vertical:
        rect(x+4,y-16,100,(n-1)*48+32,'#fcfcfc','#a8b4bd',1)
        obstacles.append((x,y-24,x+112,y+(n-1)*48+24))
        text(ref+' / '+p['value'],x,y-40,13)
        text('10k common-pin array',x,y-24,11,MUTED)
        line([(x+80,y),(x+80,y+(n-1)*48)])
        for i in range(n):
            yy=y+i*48;line([(x,yy),(x+24,yy)]);rect(x+24,yy-6,24,12);line([(x+48,yy),(x+80,yy)])
            pin(ref,i+2,x,yy,'L')
        pin(ref,1,x+80,y+(n-1)*48,'B','COM')
        return
    rect(x-16,y+4,(n-1)*64+32,76,'#fcfcfc','#a8b4bd',1)
    obstacles.append((x-24,y,(x+(n-1)*64+24),y+88))
    text(ref+' / '+p['value']+' / '+('1k' if ref=='RN5' else '10k')+' common-pin array',x,y-38,13)
    # COM is at the right and branches fan out upward; these are internal resistors.
    line([(x,y+56),(x+(n-1)*64,y+56)])
    for i in range(n):
        xx=x+i*64;line([(xx,y),(xx,y+16)]);rect(xx-6,y+16,12,24);line([(xx,y+40),(xx,y+56)])
        pin(ref,i+2,xx,y,'T',None)
    pin(ref,1,x+(n-1)*64,y+56,'R','COM')


def gate(ref,unit,x,y,nums,op):
    # IEC functional gate, with physical pin numbers; separate unused/power unit.
    rect(x,y,96,72,'#f6fafb')
    obstacles.append((x-8,y-8,x+104,y+80))
    text(ref+unit,x,y-16,15)
    text({'INV':'1','NAND':'&','AND':'&','OR':'>=1'}[op],x+48,y+43,23,anchor='middle')
    ins,out=nums[:-1],nums[-1]
    for k,num in enumerate(ins): pin(ref,num,x,y+(32 if len(ins)==1 else 24+k*24),'L')
    pin(ref,out,x+96,y+48 if len(ins)>1 else y+32,'R')
    text(pins[ref,str(out)]['net'],x+128,y+(60 if len(ins)>1 else 52),12,MUTED)
    if op in ('INV','NAND'):circle(x+100,y+(48 if len(ins)>1 else 32),4)


def testpoint(ref,x,y):
    circle(x,y,5);line([(x,y),(x,y+24)],WIRE,net=P[ref]['pins'][0]['net'])
    text(ref,x+10,y+4,13);text(P[ref]['value'],x+10,y+21,11,MUTED)
    n=pins[ref,'1']['net'];ports[ref,'1']=dict(x=x,y=y+24,side='B',net=n)
    if n in POWER:power_marks.append((x,y+24,n,'B'))


def section(title,x,y):
    text(title,x,y,27,'#1b536b')


# All coordinates on an 8-unit grid. This drawing has no implied PCB relocation.
text('YM2203C / Pico 2 - Rev C 全体接続回路図',96,80,38)
text('発注済み回路の読図用 / 回路・GPIO・部品番号は変更なし / 2026-10-27',96,120,19,MUTED)
text('線の交差：● のある箇所のみ接続。電源 +5V / +3V3 / GND は共通記号。× は未接続。数字は物理端子番号。',96,156,18)
text('モジュールは外部端子までを表示。抵抗・コンデンサは主基板の部品。Pico内蔵回路など既製モジュール内部は省略。',96,186,17,MUTED)

section('01  USB-C 主電源 / Pico 電源',96,256)
box('JPOWER',128,352,256,224,
    [],[(1,40,'VBUS'),(5,80,'CC1'),(6,120,'CC2'),([4,7],160,'GND')],
    'AE-USB2.0-TYPE-C / power only',complete=True)
passive('F1',576,392,label='PTC 0.5A hold')
box('U11',864,352,240,224,[(1,40,'VIN'),(3,80,'ON'),(4,160,'CT')],[(6,40,'VOUT'),(2,192,'GND'),(5,112,'QOD')],complete=False)
passive('R26',496,480,True);passive('R27',672,520,True)
passive('C32',752,480,True);passive('C33',752,648,True)
passive('C1',1232,480,True)
# D1 is oriented from +5V (A2) on the left to VSYS (K1) on the right.
rect(1360,368,112,64,'#ffffff');text('D1 / SS14',1416,350,15,anchor='middle')
line([(1360,400),(1384,400)]);line([(1448,400),(1472,400)])
line([(1384,380),(1384,420),(1424,400),(1384,380)])
line([(1424,380),(1424,420)]);text('A 2',1368,442,12);text('K 1',1432,442,12)
ports['D1','2']=dict(x=1360,y=400,side='L',net='+5V');power_marks.append((1360,400,'+5V','L'))
ports['D1','1']=dict(x=1472,y=400,side='R',net='VSYS')
obstacles.append((1376,360,1432,432))
box('A1',1648,352,336,368,[(39,48,'VSYS'),([3,8,13,18,23,28,33,38],96,'GND'),(32,192,'GP27 reserved'),(35,224,'ADC_VREF'),(37,256,'3V3_EN'),(40,288,'USB VBUS')],[(36,48,'3V3 OUT')],title='Pico 2 / power & unused',complete=False)
passive('C2',2128,480,True)
testpoint('TP1',2288,352);testpoint('TP2',2448,352);testpoint('TP3',2608,352)
text('Pico USB Micro-B: PC / USB-MIDI（ファームウェア必要）',1648,768,16)
text('5V系は電源専用USB-Cから給電。Pico USBだけでは音源側へ5Vを供給しない。',96,816,17,MUTED)

section('02  MCU / 3.3V I2C / 8-bit bus',96,896)
box('A1',448,1016,352,944,
    [(26,48,'GP20 SDA'),(27,80,'GP21 SCL'),(30,160,'RUN')],
    [(n,48+i*32,f'GP{i} D{i}') for i,n in enumerate([1,2,4,5,6,7,9,10])]+[
    (11,336,'GP8 A0'),(12,368,'GP9 RESET_RELEASE'),(17,416,'GP13 CS_N'),(19,448,'GP14 WR_N'),(20,480,'GP15 RD_N'),
    (14,544,'GP10 I2S DATA'),(15,576,'GP11 I2S BCLK'),(16,608,'GP12 I2S LRCK'),
    (21,672,'GP16 FM SD'),(22,704,'GP17 FM CLK'),(24,736,'GP18 FM SH'),(34,768,'GP28 IRQ_N'),
    (25,832,'GP19 LINE_ALLOW'),(31,864,'GP26 DAC_ALLOW'),(29,896,'GP22 ARM')],title='Raspberry Pi Pico 2 / GPIO',complete=False)
box('JHOST',128,1016,144,160,[],[(2,48,'SDA'),(3,80,'SCL'),([1,4],128,'GND')],title='3.3V I2C',complete=False)
box('JRUN',128,1256,144,96,[],[(1,32,'RUN'),(2,64,'GND')],title='external reset SW',complete=False)
passive('R1',336,960,True);passive('R2',176,960,True)
text('R1/R2: ホストにプルアップがあれば重複分を省略',96,1432,14,MUTED)
box('A3',1296,1016,288,320,
    [(4+i,48+i*32,f'A{i+1}') for i in range(8)],
    [(21-i,48+i*32,f'B{i+1}') for i in range(8)],complete=False)
box('U2',1296,1560,288,320,
    [(18-i,48+i*32,f'B{i+1}') for i in range(8)],
    [(2+i,48+i*32,f'A{i+1}') for i in range(8)],complete=False)
text('write: A3  3.3V -> 5V',1296,984,15)
text('read: U2  5V -> 3.3V',1296,1528,15)
box('A3',1296,1392,288,96,[(2,32,'/OE'),([1,24,3],64,'VA, DIR')],[(23,32,'VB'),([12,13,22],64,'GND')],title='A3 / supply & direction',complete=False)
box('U2',1296,1936,288,96,[(19,32,'/OE'),([1,20],64,'VCC, DIR')],[(10,64,'GND')],title='U2 / supply & direction',complete=False)

section('03  YM2203C / control translator / FM capture',1824,896)
box('U1',2256,1016,288,704,
    [(n,48+i*32,f'D{i}') for i,n in enumerate([40,2,3,4,5,6,7,8])]+[
    (37,336,'A0'),(24,384,'/RESET'),(34,432,'/CS'),(35,464,'/WR'),(36,496,'/RD'),(38,592,'PHI_M')],
    [(23,48,'SD'),(39,80,'CLK'),(22,112,'SH'),(25,176,'/IRQ'),(20,400,'SSG A'),(19,448,'SSG B'),(18,496,'SSG C')],complete=False)
box('U1',2256,1808,288,400,
    [(21,40,'VDD'),([1,17],80,'GND')],[],title='U1 / supply',complete=False)
# The 16 unused parallel I/O pins are shown individually in two compact columns.
for k,n in enumerate(range(9,17)): pin('U1',n,2256,2000+k*24,'L',None)
for k,n in enumerate(range(26,34)): pin('U1',n,2544,2000+k*24,'R',None)
text('IOA/IOB: NC 9-16, 26-33',2256,2240,13,MUTED)
box('A4',1760,2160,288,304,
    [(4,48,'A1 A0'),(5,96,'A2 RESET'),(6,144,'A3 /CS'),(7,176,'A4 /WR'),(8,208,'A5 /RD'),([9,10,11],256,'A6..8 GND')],
    [(21,48,'B1'),(20,96,'B2'),(19,144,'B3'),(18,176,'B4'),(17,208,'B5'),([12,13,22,2],256,'GND, /OE')],complete=False)
box('A4',1760,2536,288,144,[([1,24,3],48,'VA, DIR')],[(23,48,'VB'),(16,80,'B6 NC'),(15,104,'B7 NC'),(14,128,'B8 NC')],title='A4 / supply & unused',complete=False)
box('U3',2800,1016,272,256,
    [(2,48,'A1 SD'),(3,80,'A2 CLK'),(4,112,'A3 SH'),(5,176,'A4 IRQ')],
    [(18,48,'B1 SD'),(17,80,'B2 CLK'),(16,112,'B3 SH'),(15,176,'B4 IRQ')],complete=False)
box('U3',2800,1360,272,240,
    [([1,20],48,'VCC, DIR'),([6,7,8,9,10,19],96,'GND, /OE')],
    [(14,48,'B5 NC'),(13,96,'B6 NC'),(12,144,'B7 NC'),(11,192,'B8 NC')],title='U3 / supply & unused',complete=False)
for r,xx,yy in [('TP6',2640,960),('TP7',2688,912),('TP8',2736,864)]:testpoint(r,xx,yy)
passive('R4',3200,1200,True)
passive('R3',2160,2184,True)

section('04  8MHz / 2 -> YM 4MHz clock',2496,320)
box('X1',2816,416,224,160,[(8,32,'VCC'),(4,128,'GND')],[(5,80,'OUT'),(1,128,'NC')],complete=False)
passive('R7',3168,496)
box('U7',3376,416,256,176,[(2,48,'D'),(3,80,'CLK'),([1,4,14],128,'/CLR,/PRE,VCC')],[(5,80,'Q'),(6,48,'/Q'),(7,128,'GND')],title='TC74HC74AP / divider',complete=False)
passive('R8',3760,496)
testpoint('TP9',3920,496)
box('U7',3376,672,256,128,[([10,13],40,'/PRE2, /CLR2'),([11,12],88,'CLK2,D2')],[(8,40,'/Q2 NC'),(9,88,'Q2 NC')],title='U7B / unused',complete=False)
text('U7A: /Q feedback to D -> divide by 2',3376,848,14,MUTED)

section('05  PCM5102A / I2S DAC',2704,1776)
box('A2',2816,1904,288,512,
    [(14,48,'DIN'),(13,96,'BCK'),(15,144,'LRCK'),(17,208,'XSMT'),([1,8,20],288,'3V3'),([3,9,10,11,12,16,19],336,'GND / mode')],
    [(6,48,'OUTL'),(2,128,'CAPP'),(4,176,'CAPM'),(5,240,'VNEG'),(18,304,'LDOO'),(7,416,'OUTR NC')],complete=False)
for r,y in [('R9',1952),('R10',2000),('R11',2048)]:passive(r,2688,y)
passive('C13',3264,2056,True);passive('C14',3264,2208,True);passive('C15',3264,2360,True)
passive('R12',3328,1856);passive('C22',3456,1952,True);testpoint('TP12',3184,1832)

section('06  FM + SSG mono mixer / 2.5V reference',3520,896)
for i,(c,r) in enumerate([('C25','R15'),('C26','R16'),('C27','R17'),('C28','R18')]):
    y=1040+i*128;passive(c,3568,y);passive(r,3792,y)
box('U8',4112,1152,240,176,[(6,48,'INB -'),(5,128,'INB +')],[(7,80,'OUTB')],title='MCP6022 / summing amp',unit='B',complete=False)
passive('R19',4160,1024);passive('C29',4160,944)
passive('R13',3872,672,True);passive('R14',3872,816,True);passive('C24',4032,816,True)
box('U8',4320,656,224,160,[(3,48,'INA +'),(2,112,'INA -')],[(1,80,'OUTA')],title='MCP6022 / VREF buffer',unit='A',complete=False)
box('U8',4320,880,224,80,[(8,32,'VDD')],[(4,48,'VSS')],title='U8 / supply',complete=False)
testpoint('TP11',4624,736);testpoint('TP10',4464,1232)
rn('RN5',3568,1576)
text('RN5: 未使用の5抵抗の端子もNC。COM=GND。',3520,1736,14,MUTED)

section('07  line mute / volume / AMS-22 output',3520,1840)
box('U9',3840,1936,272,224,
    [(12,48,'X0 / audio'),(13,96,'X1 / VREF'),(11,160,'A / select')],[(14,48,'X')],title='CD74HC4053 / mute',complete=False)
box('U9',3840,2248,272,144,
    [(16,40,'VCC'),([1,2,3,5,6,7,8,9,10],88,'GND / unused')],[(4,40,'Z NC'),(15,88,'Y NC')],title='U9 / supply & unused',complete=False)
passive('C31',4240,1984);passive('R23',4384,2112,True)
# Two mechanically linked potentiometers, with CCW and CW explicitly numbered.
for nums,x in [((1,2,3),4352),((4,5,6),4544)]:
    a,b,c=nums
    rect(x-8,2248,16,112);line([(x,2224),(x,2248)]);line([(x,2360),(x,2384)])
    line([(x+48,2304),(x+8,2304),(x+20,2296)]);line([(x+8,2304),(x+20,2312)])
    text('RV1'+('A' if a==1 else 'B'),x-32,2200,16);text('A10k',x-32,2217,12)
    for num,xx,yy,side in [(a,x,2384,'B'),(b,x+48,2304,'R'),(c,x,2224,'T')]:
        n=pins['RV1',str(num)]['net'];ports['RV1',str(num)]=dict(x=xx,y=yy,side=side,net=n)
        text(str(num),xx+8,yy-8,11,MUTED)
        if n in POWER:power_marks.append((xx,yy,n,side))
    obstacles.append((x-16,2240,x+40,2368))
line([(4360,2264),(4536,2264)],MUTED,1,dash='6 5')
text('mechanically linked',4384,2248,11,MUTED)
passive('R24',4448,2496);passive('R25',4640,2608)
box('JLINE',4400,2768,288,144,[(4,40,'TIP L'),(2,80,'RING R'),(3,120,'SLEEVE')],[],title='ST-005-G / 3.5mm TRS',complete=False)
text('左右は同じモノラル信号 / AMS-22 LINE INへ',4224,2992,16,MUTED)
passive('R20',3520,2544);passive('R21',3680,2704,True);passive('R22',3808,2448,True)
box('Q1',3824,2640,224,128,[(1,48,'B')],[(3,32,'C'),(2,96,'E')],title='MMBT3904 / B1 E2 C3',complete=False)
text('LINE_RUN=H -> Q1 ON -> A=L -> X0(audio)',3520,2872,15,MUTED)
text('LINE_RUN=L -> Q1 OFF -> A=H -> X1(VREF)',3520,2900,15,MUTED)

section('08  ARM interlocks / gates / default bias',96,2152)
gate('U4','A',576,2256,[1,2],'INV');gate('U4','B',576,2400,[3,4],'INV')
gate('U5','A',1024,2256,[1,2,3],'NAND');gate('U5','B',1024,2400,[4,5,6],'NAND')
for unit,y,nums in [('A',2256,[1,2,3]),('B',2400,[4,5,6]),('C',2544,[9,10,8])]:gate('U6',unit,1376,y,nums,'OR')
for unit,y,nums in [('A',2800,[1,2,3]),('B',2928,[4,5,6]),('C',3056,[9,10,8])]:gate('U10',unit,1376,y,nums,'AND')
testpoint('TP4',880,2080);testpoint('TP5',1648,2784)
passive('R5',1184,2112,True);passive('R6',2496,2496,True)
rn('RN1',128,1536,True);rn('RN2',1008,1568,True);rn('RN3',128,2784);rn('RN4',1824,2832);rn('RN6',1760,3104)
text('RN1/2/3/4/6: 起動時のレベル保持 / 全端子を表示',128,2080,15,MUTED)
for ref,x,ns in [('U4',128,([5,9,11,13],[6,8,10,12])),('U5',448,([9,10,12,13],[8,11])),('U6',768,([12,13],[11])),('U10',1088,([12,13],[11]))]:
    box(ref,x,3008,224,160 if ref=='U4' else 128,[(ns[0],32,'unused inputs'),(14,72,'VCC'),(7,104,'GND')],[(n,32+i*32,'NC') for i,n in enumerate(ns[1])],title=ref+' / unused & supply',complete=False)

for i in range(8):text('Y_D'+str(i),1904,1056+i*32,12,MUTED)
for n,yy in [('Y_SD',1056),('Y_CLK',1088),('Y_SH',1120),('Y_IRQ',1184)]:text(n,2648,yy,12,MUTED)

# Supply bypasses are intentionally collected as a clearly identified bank;
# placement notes identify the actual device, not a physical PCB location change.
section('09  bypass / bulk capacitors (共通電源記号、基板配置は原設計のまま)',96,3240)
decaps=[3,4,5,6,7,8,9,10,11,12,16,17,18,19,20,21,23,30]
for i,n in enumerate(decaps):
    passive('C'+str(n),128+i*248,3312,False)
    near=P['C'+str(n)].get('near')
    if near:text('near '+('/'.join(map(str,near)) if isinstance(near,list) else near),128+i*248,3344,11,MUTED,'middle')
text('H1-H4: 3.2mm NPTH / 機械固定穴・電気接続なし',2752,3120,15,MUTED)
text('既存ネットリストとの全端子照合・信号配線の連続性を検査。ハードウェア動作や音質の保証ではありません。',2752,3152,15,MUTED)


def render_power():
    for x,y,n,side in power_marks:
        # Symbols deliberately extend outward from the pin, never across a body.
        dx,dy={'L':(-24,0),'R':(24,0),'T':(0,-24),'B':(0,24)}[side]
        xx,yy=x+dx,y+dy;line([(x,y),(xx,yy)],WIRE,1.8,n)
        obstacles.append((min(x,xx)-2,min(y,yy)-2,max(x,xx)+2,max(y,yy)+2))
        obstacles.append((xx-14,yy-14,xx+14,yy+26 if n=='GND' else yy+2))
        if n=='GND':
            line([(xx,yy),(xx,yy+12)],WIRE,1.8,n)
            for d,w in [(12,12),(18,8),(24,4)]:line([(xx-w,yy+d),(xx+w,yy+d)],WIRE,1.8,n)
        else:
            line([(xx,yy),(xx,yy-12)],'#a04428',1.8,n)
            line([(xx-7,yy-5),(xx,yy-12),(xx+7,yy-5)],'#a04428',1.8,n)
            text(n,xx,yy-18,12,'#a04428','middle')


def compress(path):
    if len(path)<3:return path
    result=[path[0]]
    for a,b,c in zip(path,path[1:],path[2:]):
        if (b[0]-a[0],b[1]-a[1]) != (c[0]-b[0],c[1]-b[1]):result.append(b)
    result.append(path[-1]);return result


def route():
    # Orthogonal multi-terminal trees, crossings allowed, coincident conductors
    # of different nets forbidden. Symbol bodies and text areas are obstacles.
    nx,ny=W//GRID,H//GRID
    blocked=set()
    for x1,y1,x2,y2 in obstacles:
        for x in range(math.ceil(x1/GRID),math.floor(x2/GRID)+1):
            for y in range(math.ceil(y1/GRID),math.floor(y2/GRID)+1):blocked.add((x,y))
    terminals=defaultdict(set)
    for p in ports.values():
        if p['net'] and p['net'] not in POWER:
            assert p['x']%GRID==0 and p['y']%GRID==0,p
            terminals[p['net']].add((p['x']//GRID,p['y']//GRID))
    # Pin lead stubs are reserved to their own net and cannot be used as a road
    # by another net. The 3V3/GND symbols themselves need not enter this router.
    reserved={}
    for p in ports.values():
        x,y=p['x']//GRID,p['y']//GRID
        n=p['net'] or '__NC__'
        dx,dy={'L':(1,0),'R':(-1,0),'T':(0,1),'B':(0,-1)}[p['side']]
        for k in range(-3 if p['net'] and p['net'] not in POWER else 0,7):
            a=(x+k*dx,y+k*dy)
            if a in reserved: assert reserved[a]==n,(a,n,reserved[a])
            reserved[a]=n
    edge_net={};node_nets=defaultdict(set);paths=[];audit={};fail=[]
    def edge(a,b):return tuple(sorted((a,b)))
    order=sorted(terminals,key=lambda n:(0 if n.startswith(('Y_D','D')) and n[-1:].isdigit() else 1,len(terminals[n]),n))
    for net in order:
        todo=set(terminals[net]);tree={min(todo)};todo-=tree
        used_edges=set()
        while todo:
            # Start with the terminal closest to the current tree bounding box.
            target=min(todo,key=lambda t:min(abs(t[0]-p[0])+abs(t[1]-p[1]) for p in tree))
            minx=min(p[0] for p in tree);maxx=max(p[0] for p in tree)
            miny=min(p[1] for p in tree);maxy=max(p[1] for p in tree)
            goal=min(tree,key=lambda p:abs(p[0]-target[0])+abs(p[1]-target[1]))
            def heuristic(p):return abs(goal[0]-p[0])+abs(goal[1]-p[1])
            initial=(target[0],target[1],-1);q=[(0,0,initial)];cost={initial:0};back={};last=None
            while q:
                _,g,s=heapq.heappop(q)
                if g!=cost[s]:continue
                x,y,prev=s;p=(x,y)
                if p in tree and not (node_nets[p]-{net}):last=s;break
                for d,(dx,dy) in enumerate([(1,0),(0,1),(-1,0),(0,-1)]):
                    b=(x+dx,y+dy)
                    if not(10<=b[0]<=nx-10 and 36<=b[1]<=ny-4):continue
                    if b in blocked and b not in terminals[net]:continue
                    if b in reserved and reserved[b]!=net:continue
                    e=edge(p,b)
                    if e in edge_net and edge_net[e]!=net:continue
                    others=node_nets[b]-{net}
                    if others:
                        ok=True
                        for other in others:
                            dirs=[]
                            for od,(ox,oy) in enumerate([(1,0),(0,1),(-1,0),(0,-1)]):
                                if edge_net.get(edge(b,(b[0]+ox,b[1]+oy)))==other:dirs.append(od)
                            if len(dirs)!=2 or (dirs[0]-dirs[1])%2!=0 or dirs[0]%2==d%2:ok=False
                        if not ok:continue
                    # A different-net crossing must be straight, never a bend.
                    if node_nets[p]-{net} and prev!=-1 and d!=prev:continue
                    ng=g+1+(5 if prev!=-1 and d!=prev else 0)+(12 if others else 0)
                    ns=(b[0],b[1],d)
                    if ng<cost.get(ns,1e20):
                        cost[ns]=ng;back[ns]=s;heapq.heappush(q,(ng+heuristic(b),ng,ns))
            if last is None:
                fail.append((net,target));break
            pts=[];s=last
            while True:
                pts.append((s[0],s[1]))
                if s==initial:break
                s=back[s]
            for a,b in zip(pts,pts[1:]):
                e=edge(a,b);edge_net[e]=net;used_edges.add(e)
            for p in pts:node_nets[p].add(net)
            tree.update(pts);todo-=tree
            paths.append((net,compress([(x*GRID,y*GRID) for x,y in pts])))
        audit[net]={'terminals':len(terminals[net]),'connected':not todo,'edges':len(used_edges)}
        print('route',net,len(terminals[net]),'OK' if not todo else 'FAIL',flush=True)
    assert not fail,fail
    # Check every tree by graph traversal, not just a successful router status.
    for net,ts in terminals.items():
        adj=defaultdict(set)
        for (a,b),n in edge_net.items():
            if n==net:adj[a].add(b);adj[b].add(a)
        seen={next(iter(ts))};todo=list(seen)
        while todo:
            for b in adj[todo.pop()]-seen:seen.add(b);todo.append(b)
        assert ts<=seen,(net,ts-seen)
    Path('/private/tmp/ym2203-connected-routing.json').write_text(json.dumps({'paths':paths,'edges':[[a,b,n] for (a,b),n in edge_net.items()],'audit':audit}))
    return paths,edge_net,audit


def validate_membership():
    assert set(ports)==set(pins),(set(pins)-set(ports),set(ports)-set(pins))
    expected=defaultdict(set)
    for key,p in pins.items():
        assert ports[key]['net']==p['net']
        if p['net']:expected[p['net']].add(key)
    actual=defaultdict(set)
    for net in ET.parse(NETLIST).getroot().findall('./nets/net'):
        name=net.attrib['name'].lstrip('/')
        if name.startswith('unconnected'):continue
        for n in net.findall('node'):
            if not n.attrib['ref'].startswith('#'):actual[name].add((n.attrib['ref'],n.attrib['pin']))
    assert dict(expected)==dict(actual)
    return expected


def export(paths,edge_net,audit):
    # Independently recheck wire geometry before writing any deliverable.
    connected=defaultdict(set)
    at_node=defaultdict(lambda:defaultdict(set))
    for (a,b),net in edge_net.items():
        assert abs(a[0]-b[0])+abs(a[1]-b[1])==1
        connected[net,a].add(b);connected[net,b].add(a)
        at_node[a][net].add(b);at_node[b][net].add(a)
    crossings=0
    for point,nets in at_node.items():
        if len(nets)<=1:continue
        assert len(nets)==2,(point,nets)
        axes=[]
        for net,neighbors in nets.items():
            assert len(neighbors)==2,(point,net,neighbors)
            a,b=neighbors
            assert a[0]+b[0]==2*point[0] and a[1]+b[1]==2*point[1]
            axes.append(a[0]==point[0])
        assert axes[0]!=axes[1]
        crossings+=1
    terminals=defaultdict(set)
    for p in ports.values():
        if p['net'] and p['net'] not in POWER:
            terminals[p['net']].add((p['x']//GRID,p['y']//GRID))
    for net,points in terminals.items():
        seen={next(iter(points))};pending=list(seen)
        while pending:
            for b in connected[net,pending.pop()]-seen:seen.add(b);pending.append(b)
        assert points<=seen,(net,points-seen)
    # Wires first, symbols and labels on top. Dot only real same-net branches.
    routed=[('line',p,WIRE,1.8,n,None) for n,p in paths]
    degrees=defaultdict(set)
    for (a,b),net in edge_net.items():degrees[net,a].add(b);degrees[net,b].add(a)
    for p in ports.values():
        if not p['net'] or p['net'] in POWER:continue
        point=(p['x']//GRID,p['y']//GRID)
        dx,dy={'L':(1,0),'R':(-1,0),'T':(0,1),'B':(0,-1)}[p['side']]
        degrees[p['net'],point].add((point[0]+dx,point[1]+dy))
    dots=[('circle',(p[0]*GRID,p[1]*GRID,3.3),WIRE,WIRE,1) for (n,p),v in degrees.items() if len(v)>=3]
    allshapes=routed+shapes+dots
    def esc(s):return html.escape(str(s),quote=True)
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        '<rect width="100%" height="100%" fill="white"/>']
    for sh in allshapes:
        typ=sh[0]
        if typ=='line':
            _,pts,col,sw,net,dash=sh
            attrs=(f' data-net="{esc(net)}"' if net else '')+(f' stroke-dasharray="{dash}"' if dash else '')
            svg.append(f'<polyline points="'+ ' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{col}" stroke-width="{sw}"{attrs}/>')
        elif typ=='rect':
            _,(x,y,w,h),fill,col,sw=sh;svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{col}" stroke-width="{sw}"/>')
        else:
            _,(x,y,r),fill,col,sw=sh;svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{col}" stroke-width="{sw}"/>')
    for s,x,y,sz,col,anchor in labels:
        svg.append(f'<text x="{x}" y="{y}" font-size="{sz}" fill="{col}" text-anchor="{anchor}" font-family="Arial, sans-serif" paint-order="stroke" stroke="white" stroke-width="3" stroke-linejoin="round">{esc(s)}</text>')
    svg.append('</svg>')
    svgname=OUT/'ym2203-single-board-rev-c-connected.svg';svgname.write_text('\n'.join(svg))
    pdfmetrics.registerFont(TTFont('JP','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    def draw(c):
        for sh in allshapes:
            typ=sh[0]
            if typ=='line':
                _,pts,col,sw,net,dash=sh;c.setStrokeColor(HexColor(col));c.setLineWidth(sw)
                c.setDash([6,5] if dash else [])
                p=c.beginPath();p.moveTo(pts[0][0],H-pts[0][1])
                for x,y in pts[1:]:p.lineTo(x,H-y)
                c.drawPath(p)
            elif typ=='rect':
                _,(x,y,w,h),fill,col,sw=sh;c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(col));c.setLineWidth(sw);c.setDash([]);c.rect(x,H-y-h,w,h,fill=1)
            else:
                _,(x,y,r),fill,col,sw=sh;c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(col));c.setLineWidth(sw);c.setDash([]);c.circle(x,H-y,r,fill=1)
        # White halo makes a pin name readable when a remote wire passes nearby.
        for s,x,y,sz,col,anchor in labels:
            t=c.beginText();t.setFont('JP',sz)
            if anchor=='middle':x-=pdfmetrics.stringWidth(s,'JP',sz)/2
            if anchor=='end':x-=pdfmetrics.stringWidth(s,'JP',sz)
            t.setTextOrigin(x,H-y);t.setTextRenderMode(1);c.setLineWidth(3);c.setStrokeColor(HexColor('#ffffff'));t.textOut(s);c.drawText(t)
            t=c.beginText();t.setFont('JP',sz);t.setTextOrigin(x,H-y);t.setTextRenderMode(1);t.setTextRenderMode(0);c.setFillColor(HexColor(col));t.textOut(s);c.drawText(t)
    full=PDF/'ym2203-single-board-rev-c-connected-a0.pdf'
    pw,ph=landscape(A0);c=canvas.Canvas(str(full),pagesize=(pw,ph));c.setTitle('YM2203C Rev C - 全体接続回路図')
    scale=min(pw/W,ph/H);c.saveState();c.scale(scale,scale);draw(c);c.restoreState();c.showPage();c.save()
    tiles=PDF/'ym2203-single-board-rev-c-connected-a3.pdf'
    pw,ph=landscape(A3);c=canvas.Canvas(str(tiles),pagesize=(pw,ph));c.setTitle('YM2203C Rev C - A3分割回路図')
    cols,rows=3,3;tw,th=W/cols,H/rows;sc=min((pw-40)/(tw+64),(ph-62)/(th+64))
    for row in range(rows):
        for col in range(cols):
            c.setFont('JP',11);c.drawString(22,ph-22,f'YM2203C Rev C / 全体図の拡大 {row*cols+col+1}/9 / 列{col+1} 行{row+1} / 周辺32単位を重ねて表示')
            c.saveState();p=c.beginPath();p.rect(20,30,pw-40,ph-62);c.clipPath(p,stroke=0)
            c.translate(20-(col*tw-32)*sc,30-((rows-1-row)*th-32)*sc);c.scale(sc,sc);draw(c);c.restoreState()
            c.showPage()
    c.save()
    report={'revision':'C','source_design_sha256':hashlib.sha256(DESIGN.read_bytes()).hexdigest(),
            'source_netlist_sha256':hashlib.sha256(NETLIST.read_bytes()).hexdigest(),
            'parts':len(P),'physical_pins':len(pins),'nets':len({p['net'] for p in pins.values() if p['net']}),
            'all_physical_pins_present':True,'pin_net_membership_matches_kicad':True,
            'signal_nets_are_continuous_wire_trees':True,'shared_supply_symbols':sorted(POWER),'routing':audit,
            'unconnected_crossings_verified_perpendicular':crossings,
            'no_coincident_different_net_conductors':True,
            'scope':'Reading drawing only; no PCB, circuit, GPIO or fabrication file changed.'}
    (OUT/'ym2203-single-board-rev-c-connected-validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    # Interactive tracing supplement, self-contained; no network dependencies.
    body='\n'.join(svg)
    (OUT/'ym2203-single-board-rev-c-connected.html').write_text('''<!doctype html><html lang="ja"><meta charset="utf-8"><title>YM2203C Rev C 回路図</title><style>body{margin:0;font:16px sans-serif;background:#e9eff2}header{position:sticky;top:0;background:#16364b;color:white;padding:14px;z-index:2}input{font-size:16px;width:200px}svg{background:white;width:4800px;height:3400px}svg [data-net]{cursor:crosshair}.selected{stroke:#e44920!important;stroke-width:4!important}button{font-size:16px}</style><header>Rev C 回路図 / 信号線に触れると接続経路を強調 <input id="find" placeholder="信号名: ARM / Y_D0"><button id="clear">解除</button> <button id="fit">全体表示</button> <label>拡大 <input id="zoom" type="range" min="15" max="150" value="30" style="width:140px"></label> <span id="net"></span></header>'''+body+'''<script>const all=[...document.querySelectorAll('[data-net]')];function show(n){all.forEach(e=>e.classList.toggle('selected',e.dataset.net===n));document.getElementById('net').textContent=n||''}all.forEach(e=>e.addEventListener('mouseenter',()=>show(e.dataset.net)));document.getElementById('find').addEventListener('input',e=>show(e.target.value.trim()));document.getElementById('clear').onclick=()=>show('');const view=document.querySelector('svg');function zoom(n){view.style.width=(4800*n/100)+'px';view.style.height=(3400*n/100)+'px'}document.getElementById('zoom').oninput=e=>zoom(Number(e.target.value));function fit(){const n=Math.max(15,Math.min(150,(innerWidth-20)/48));document.getElementById('zoom').value=n;zoom(n)}document.getElementById('fit').onclick=fit;fit();</script></html>''')
    print(full);print(tiles)


if __name__=='__main__':
    expected=validate_membership()
    print('Membership checked:',len(pins),'pins',len(expected),'nets',flush=True)
    render_power()
    paths,edge_net,audit=route()
    export(paths,edge_net,audit)
