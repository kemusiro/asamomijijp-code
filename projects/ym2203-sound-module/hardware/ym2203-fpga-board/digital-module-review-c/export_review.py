#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Review PDF from original SVG diagrams and native KiCad sheets. Output stays ignored."""
import argparse,html,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def run(*cmd):subprocess.run(list(map(str,cmd)),check=True,stdout=subprocess.DEVNULL)
def text(x,y,s,size=16,color='#17364c'):return f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" fill="{color}">{html.escape(s)}</text>'
def box(x,y,w,h,color='#edf5fc'):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" stroke="#829bad"/>'
def arrow(x,y,xx,yy):return f'<path d="M{x},{y} L{xx},{yy}" stroke="#247a78" stroke-width="3" marker-end="url(#a)" fill="none"/>'
def canvas():return ['<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 1123 794"><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#247a78"/></marker></defs><rect width="1123" height="794" fill="white"/>']
def cover():
 a=canvas();a += [text(30,45,'P2 digital audio module / schematic review C',28),text(30,78,'2026-11-16 | approved GPIO adopted | KiCad10.0.5 | NOT FOR FABRICATION',15)]
 a += [box(20,125,770,295,'#fff7e9'),box(810,125,295,455,'#edf5fc'),text(35,151,'SOURCE MODULE',18),text(825,151,'BASE',18)]
 for x,y,w,h,title in [(35,180,195,200,'YM2203C'),(280,300,180,80,'PCM1863'),(550,180,220,200,'Core2350B0'),(830,180,260,200,'PGA2350'),(830,450,260,100,'PCM5102A + LINE')]:
  a += [box(x,y,w,h,'white'),text(x+12,y+29,title,20)]
 a += [text(48,240,'5V / socket /4MHz',15),text(48,278,'FM digital + SSG3',15),arrow(230,235,550,235),text(290,222,'FM SD / CLK / SH (local)',14),arrow(230,340,280,340),text(235,326,'SSG',11),arrow(460,340,550,340),text(465,326,'ADC PCM',12)]
 a += [text(565,279,'FM decode + SRC',16),text(565,308,'ADC receive + mix',16),text(565,355,'I2S slave /24bit',15),arrow(770,280,830,280),text(777,267,'I2S',12)]
 a += [text(845,245,'HOST / USB CDC / MIDI',16),text(845,275,'UNO / FIFO / STOP / lease',15),text(845,315,'I2S clock master',16),text(845,345,'48kHz /3.072MHz',15),arrow(960,380,960,450),text(845,510,'stereo DAC / hardware mute',15),text(845,535,'biased L/R gates / volume',15)]
 a += [text(35,460,'Internal control: base SPI0 -> source SPI1; public HOST I2C v2 unchanged.',17),text(35,495,'Common32 contacts: SPI + mixed I2S + clocks + ENABLE/ALERT +5V/GND.',15),text(35,530,'Si5351A stays on base. Core2350B0 is NOT pin-compatible with PGA2350.',15)]
 r=json.loads((HERE/'native-verification.json').read_text())['boards']
 a += [text(30,618,f'Native ERC0: base {r["base"]["components"]} parts / source {r["module"]["components"]} parts.',20),text(30,650,'STOP: final gates close; source RUN/YM reset and ADC power inhibit do not wait for SPI.',15),text(30,680,'ADC input isolation and rail clamps are on next page; full pin-level sheets follow.',15),text(30,710,'PCB layout, power/thermal waveforms, firmware port and hardware audio acceptance are pending.',14),text(30,750,'Source: digital-module-review-c/README.md | no music or firmware binary included.',13)]
 return '\n'.join(a+['</svg>'])
def protection():
 a=canvas();a += [text(30,45,'ADC input protection / power and reset',28),text(30,78,'One SSG channel shown. A/B/C use the same circuit; native pin maps follow.',15)]
 items=[(30,170,170,'SSG output','1.33k load'),(230,170,170,'3.01k :1k','divider'),(430,170,170,'TMUX1511','power-off isolation'),(630,170,150,'2.2uF','AC coupling'),(810,170,120,'4.7k','current limit'),(960,170,135,'ADC VIN','470p toGND')]
 for x,y,w,t1,t2 in items:a += [box(x,y,w,80),text(x+10,y+29,t1,18),text(x+10,y+56,t2,13)]
 for x,xx in [(200,230),(400,430),(600,630),(780,810),(930,960)]:a.append(arrow(x,210,xx,210))
 a += [text(30,296,'BAT54S at ADC VIN: pin1=GND, pin2=ADC_3V3, pin3=VIN (two rail clamps).',17),text(30,329,'TMUX is before the coupling capacitor: its signal stays nonnegative and below1.34V.',15),text(30,362,'Switch ON requires ADC GPIO3 ARM AND local YM release AND source RUN/ENABLE.',15)]
 a += [box(30,407,510,175),text(45,437,'DEFAULT / RESET / POWER LOSS',19),text(45,470,'Base RUN -> AND gates -> final DAC/LINE mute',15),text(45,503,'ENABLE low -> source RUN via open-drain buffer',15),text(45,536,'5V-powered transistor clamp keeps YM RESET low',15),text(45,565,'ADC LDO EN low; TMUX switch is OFF',15)]
 a += [box(570,407,525,175),text(585,437,'ADC POWER CYCLE',19),text(585,470,'Independent3V3; no connection to MCU3V3 output',15),text(585,503,'680ohm rail bleed / minimum250ms OFF',15),text(585,536,'Conditional bound: C<=80uF, leakage<=50uA',15),text(585,565,'Rail must be measured below0.1V before restart',15)]
 a += [text(30,630,'Clamp/RC checks are conditional calculations, not a silicon SPICE or bench validation.',16),text(30,664,'PCM1863 has no external RESET pin. Reinitialize PLL/MUX/GPIO after each power cycle.',15),text(30,698,'Power-off logic buffers use receiving-domain supply and explicit Ioff protection.',15),text(30,746,'See POWER-SEQUENCE.md for startup, mid-rail brownout limits and test points.',14)]
 return '\n'.join(a+['</svg>'])
def contacts():
 a=canvas();d=json.loads((HERE/'connector.json').read_text());a += [text(30,45,'JMOD /32 contacts /2x16 /2.54mm',28),text(30,78,'Conductor numbering only, NOT a mating-face/PCB orientation drawing. No hot plug.',15)]
 for row in range(16):
  y=128+row*31
  for col in range(2):
   p=d['pins'][row*2+col];s=f'{p["pin"]:02d}  {p["signal"]}'
   if p['module_net'] is None:s+='  [module NC]' if p['base_net'] is not None else '  [NC]'
   a.append(text(40+col*540,y,s,18))
 a += [text(30,670,'Power:5V and common GND only; all other active signals3.3V. No analog or3V3 rail crosses.',15),text(30,707,'Remove male32 / block female32; asymmetric guides and socket fit still require PCB review.',15),text(30,750,'Legacy60-contact and40-contact proposals are NOT interchangeable with this connector.',14)]
 return '\n'.join(a+['</svg>'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--pdf',type=Path,required=True);a=ap.parse_args();a.pdf.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='p2-review-c-') as temp:
  t=Path(temp);pdfs=[]
  for name,data in [('cover',cover()),('protection',protection()),('contacts',contacts())]:
   (t/(name+'.svg')).write_text(data);run('rsvg-convert','-f','pdf','-o',t/(name+'.pdf'),t/(name+'.svg'));pdfs.append(t/(name+'.pdf'))
  for b,name in [('base','p2-base-c'),('module','p2-ym2203-c')]:
   dst=t/(b+'.pdf');run('kicad-cli','sch','export','pdf','--black-and-white','--exclude-pdf-property-popups','-o',dst,HERE/b/(name+'.kicad_sch'));pdfs.append(dst)
  run('pdfunite',*pdfs,t/'joined.pdf');run('gs','-q','-dSAFER','-dBATCH','-dNOPAUSE','-sDEVICE=pdfwrite','-dPDFSETTINGS=/prepress','-dCompatibilityLevel=1.7','-sOutputFile='+str(a.pdf),t/'joined.pdf')
 print('Exported',a.pdf.name)
