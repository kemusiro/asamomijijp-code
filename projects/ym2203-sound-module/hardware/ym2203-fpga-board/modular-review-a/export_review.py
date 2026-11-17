#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One PDF: audio path + contact list + native base/module schematics.
Requires KiCad CLI, librsvg, Poppler and Ghostscript. Keep the PDF in ignored outputs/.
"""
import argparse,html,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def run(*cmd):subprocess.run(list(map(str,cmd)),check=True,stdout=subprocess.DEVNULL)
def text(x,y,value,size=16,color='#172e46'):
 return f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" fill="{color}">{html.escape(value)}</text>'
def rect(x,y,w,h,fill):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="#8fa8bc"/>'
def line(x,y,xx,yy,color='#2464a1'):
 return f'<path d="M{x},{y} L{xx},{yy}" stroke="{color}" stroke-width="3" fill="none" marker-end="url(#a)"/>'
def canvas():return ['<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 1123 794"><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#2464a1"/></marker></defs><rect width="1123" height="794" fill="white"/>']

def cover():
 a=canvas();a+=[text(35,48,'P2 modular review A / YM2203 x1',29),text(35,79,'2026-11-16 | PGA2350 + Si5351A + real YM2203C | NOT FOR FABRICATION',15)]
 a+=[rect(30,110,320,340,'#fff4dc'),rect(390,110,700,340,'#edf5fc'),text(50,140,'SOUND MODULE / no DAC',19),text(410,140,'BASE / all 47 native GPIO unchanged',19)]
 a+=[rect(50,185,120,85,'white'),text(65,220,'YM2203C',19),text(65,247,'socket / 4MHz',13),rect(210,185,120,85,'white'),text(223,217,'LVC125',18),text(221,242,'5V -> 3.3V',14),line(170,225,210,225)]
 a+=[rect(410,185,215,85,'white'),text(425,212,'PGA2350',19),text(425,237,'PIO/DMA -> PCM -> I2S',14),text(425,258,'same GP16/17/18 +26/27/28',11),line(330,225,410,225),text(348,177,'JMOD',13),rect(675,185,150,85,'white'),text(689,217,'PCM5102A',19),text(689,244,'stereo DAC',14),line(625,225,675,225),text(630,207,'I2S',12)]
 a+=[rect(875,185,190,85,'white'),text(889,216,'Stereo mixers',18),text(889,243,'FM + SSG + AUX',14),line(825,225,875,225)]
 a+=[text(58,318,'SSG A / B / C',18),text(58,344,'1k loads on module',14),line(110,270,110,294),line(195,320,968,320,'#268159'),text(400,310,'analog SSG / base AC coupling',15),line(968,319,968,275,'#268159')]
 a+=[rect(675,357,150,65,'white'),text(689,384,'Si5351A',19),text(689,408,'CLK0 /3.3V',13),line(675,392,240,392),text(260,382,'clock -> module3.3V/5V shifter',13)]
 a+=[rect(875,357,190,65,'white'),text(887,384,'Dual LINE mute',17),text(887,408,'volume -> line L/R',14),line(969,270,1065,300),line(1065,300,1065,355)]
 a+=[text(35,490,'I2S contains digitally received FM. SSG is mixed in analog; no ADC is added.',18),text(35,522,'YM2203 uses identical FM on L/R; future stereo formats need separate decoder validation.',15)]
 stats=json.loads((HERE/'verification.json').read_text());a+=[text(35,567,'NATIVE KiCad10.0.5 CHECKS',19),text(35,595,f'Base: {stats["boards"]["base"]["components"]} components / ERC0 | Module: {stats["boards"]["module"]["components"]} components / ERC0',17),text(35,624,'HOST I2C v2, USB CDC/MIDI, UNO R3 3.3V, STOP/lease are retained design requirements.',14),text(35,653,'Default: YM reset, data/control buffers disabled, DAC muted and both LINE gates closed.',14),text(35,682,'P2 firmware, PCB layout, connector/stack fit, power/thermal/SI and audio acceptance are pending.',14),text(35,711,'Separate grounds are NOT introduced; use a solid reference plane and controlled return paths.',14),text(35,750,'Review source: modular-review-a/README.md | contact map on next page',13)]
 return '\n'.join(a+['</svg>'])

def contact_map():
 d=json.loads((HERE/'connector.json').read_text());a=canvas();a+=[text(35,46,'JMOD / 60 positions /2x30 /2.54mm',26),text(35,74,'Electrical conductor numbering only: NOT a PCB top-view or connector mating-face drawing.',14),text(35,98,'Base female / module male. Remove male60 + block female60; add asymmetric supports.',14)]
 for i in range(30):
  y=132+i*19
  for col in range(2):
   p=d['pins'][i*2+col];x=45+col*540
   color='#9a3040' if p['pin']==60 else '#74818b' if p['status']=='reserved_unwired' else '#172e46'
   suffix='  [NC]' if p['status']=='reserved_unwired' else '  [module NC]' if p['module_net'] is None and p['pin']!=60 else ''
   a+=[text(x,y,f'{p["pin"]:02d}  {p["signal"]}{suffix}',15,color)]
 a+=[text(35,740,'Digital bus/FM at3.3V. SSG pins43/45/47 are analog0..5V with DC bias. NO HOT PLUG.',14)]
 return '\n'.join(a+['</svg>'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pdf',type=Path,required=True);a=p.parse_args();a.pdf.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='p2-module-review-') as td:
  t=Path(td);pdfs=[]
  for name,data in [('cover',cover()),('contacts',contact_map())]:
   (t/(name+'.svg')).write_text(data);run('rsvg-convert','-f','pdf','-o',t/(name+'.pdf'),t/(name+'.svg'));pdfs.append(t/(name+'.pdf'))
  for board,name in [('base','p2-base-a'),('module','p2-ym2203-a')]:
   dest=t/(board+'.pdf');run('kicad-cli','sch','export','pdf','--black-and-white','--exclude-pdf-property-popups','-o',dest,HERE/board/(name+'.kicad_sch'));pdfs.append(dest)
  run('pdfunite',*pdfs,t/'joined.pdf')
  run('gs','-q','-dSAFER','-dBATCH','-dNOPAUSE','-sDEVICE=pdfwrite','-dPDFSETTINGS=/prepress','-dCompatibilityLevel=1.7','-sOutputFile='+str(a.pdf),t/'joined.pdf')
 print('Exported review PDF:',a.pdf.name)
