#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create original mechanical review sheets plus native copper/assembly plots. PDF stays in ignored outputs."""
from pathlib import Path
import argparse,subprocess,json,re,html,sys
HERE=Path(__file__).resolve().parent

def makepage(title,sub,body,number):
 return f'''<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297"><rect width="420" height="297" fill="white"/>
 <style>text{{font-family:DejaVu Sans,sans-serif;fill:#173047}} .h{{font-size:7px;font-weight:bold}} .s{{font-size:3.7px}} .n{{font-size:4.4px}} .small{{font-size:3.1px}}</style>
 <rect width="420" height="8" fill="#16364a"/><text x="16" y="24" class="h">{html.escape(title)}</text><text x="16" y="34" class="s">{html.escape(sub)}</text>{body}
 <line x1="16" y1="279" x2="404" y2="279" stroke="#abc" stroke-width=".3"/><text x="16" y="286" class="small">P2 revision3.1 / PCB review D / 2026-11-16 / CAD only; firmware port and bench acceptance pending</text><text x="400" y="286" text-anchor="end" class="s">{number:02}</text></svg>'''
def txt(x,y,s,cls='n'):return f'<text x="{x}" y="{y}" class="{cls}">{html.escape(s)}</text>'
def rect(x,y,w,h,color,stroke='#345'):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="1" fill="{color}" stroke="{stroke}" stroke-width=".5"/>'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--kicad-python',default=sys.executable);a=ap.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True);work=a.output.parent/(a.output.stem+'-plots');work.mkdir(exist_ok=True)
 v=json.loads((HERE/'verification.json').read_text());m=json.loads((HERE/'mechanical-review.json').read_text());pages=[]
 body=rect(18,52,184,68,'#e6f1ff')+rect(218,52,184,68,'#e7f5ea')
 for x,lines in [(25,['BASE / PGA2350','HOST I2C v2 + USB CDC/MIDI + UNO R3','Si5351A / I2S master / PCM5102A','Biased stereo output + hardware gate']), (225,['SOURCE / Core2350B0 + YM2203C','Local5V bus / raw FM decode and SRC','PCM1863 ADC for SSG / MCU digital mix','SPI control + mixed stereo I2S return'])]:
  for j,t in enumerate(lines):body+=txt(x,65+j*14,t)
 body+=txt(18,139,'Native KiCad checks: ERC0 / DRC0 / unconnected0 / schematic parity0 on BOTH boards')
 body+=txt(18,153,'292 electrical references; 1155 physical pad/pin checks; four copper layers per PCB')
 body+=txt(18,167,'In1.Cu reserved for GND. Signal routing uses F.Cu / In2.Cu / B.Cu.')
 body+=txt(18,181,'32 mating contacts; all38 UNO contacts and64 Core pins checked by coordinates.')
 body+=txt(18,195,'Existing Rev C firmware and HOST sources preserved; P2 runtime port remains separate.')
 body+=txt(18,217,'Assembly: inspect socket engagement, connector orientation and all listed SMT via sites.')
 body+=txt(18,231,'Power: external regulated5.1V class2A; verify YM4.75..5.25V under actual load.')
 body+=txt(18,245,'Audio: ADC rail discharge/input transients, SSG calibration and EMI need bench measurement.')
 pages.append(makepage('Placed and routed split sound module','PGA2350 base + Core2350B0 / PCM1863 / real YM2203C',body,1))
 # Original top-view assembly envelope: dimensions and contacts are native coordinates.
 scale=1.48;ox,oy=24,57;body=f'<g transform="translate({ox},{oy}) scale({scale})">'+rect(0,0,194,142,'#f7f9fb')+rect(7,7,76,60,'#e3f0ff')+rect(90,38,100,100,'#dbf0df')+rect(96.48,6.48,25.9,25.9,'#ffe9c9')
 body+=txt(15,26,'UNO R3 shield envelope','s')+txt(98,17,'PGA2350','s')+txt(99,46,'100 x100 source board','s')
 bp=json.loads((HERE/'base/placement-final.json').read_text())
 for i in range(1,13):
  x,y=bp['H'+str(i)]['xy'];body+=f'<circle cx="{x}" cy="{y}" r="1.6" fill="white" stroke="#345" stroke-width=".35"/>'
 for i in range(1,33):
  x=97 if i%2 else 94.46;y=50+((i-1)//2)*2.54;body+=f'<circle cx="{x}" cy="{y}" r=".7" fill="#ca8e36"/>'
 body+=rect(101.73,96.73,25.4,25.4,'#fff0cc')+txt(102,111,'Core2350B0','small')+rect(160,55,19,54,'#fff0cc')+txt(163,85,'YM','s')+'</g>'
 body+=txt(325,76,'194 x142mm base','s')+txt(325,88,'100 x100mm source','s')+txt(325,108,'7mm planar gap','s')+txt(325,119,'between reserved','s')+txt(325,130,'shield and source','s')+txt(325,153,'H11: bare UNO hole','s')+txt(325,164,'NO screw/standoff','s')+txt(325,188,'Asymmetric source','s')+txt(325,199,'support pattern','s')+txt(325,220,'Pin32 blocked;','s')+txt(325,231,'remove male pin32','s')
 pages.append(makepage('Mechanical envelopes - top view','Shield and daughterboard occupy separate planar regions; no arbitrary shield overhang assumed',body,2))
 # Side section, deliberately schematic in X, true-to-model in Z.
 body=rect(25,218,367,7.2,'#6e9b88')+rect(186,161.075,200,7.2,'#7fae7d')+rect(42,172.505,118,7.2,'#6196c7')
 body+=rect(192,179.705,10,38.295,'#333')+rect(192,168.275,10,11.43,'#d2aa64')+rect(320,156,12,62,'none')
 body+=rect(225,102.125,76,16.2,'#d9a85d')+rect(225,118.325,76,16.2,'#eee')+rect(225,137.09,76,23.985,'#ddd')+rect(335,111.575,35,49.5,'#c99')
 body+=txt(27,241,'BASE PCB: front face is Z0')+txt(212,195,'SSW8.51 + TSW2.54','s')
 body+=txt(212,72,'MCU module top envelope Z25.75mm','s')+txt(212,84,'9.5mm underside jig +3.6mm component envelope','s')
 body+=txt(42,164,'UNO socket8.51mm / underside protrusion<=5mm','s')
 body+=txt(25,255,'Base underside:8mm chassis clearance. Source supports match actual fully seated connector height.','s')
 body+=txt(25,267,'Model minimum cavity:10.5 -3.0mm source tails -3.0mm base parts =4.5mm. Fit must be measured.','s')
 pages.append(makepage('Socket and connector height model','Schematic X section; dimensions in Z refer to base PCB front copper. Not a manufactured-fit certificate.',body,3))
 for side,name,label in [('base','p2-base-d','BASE'),('module','p2-ym2203-d','SOURCE')]:
  for layers,heading in [('F.Fab,B.Fab,Edge.Cuts,Dwgs.User','Assembly / bodies / numbered key'),('F.Cu,F.Silkscreen,Edge.Cuts','Front copper'),('In1.Cu,Edge.Cuts','Inner1 - GND reference'),('In2.Cu,Edge.Cuts','Inner2 - power and signals'),('B.Cu,B.Silkscreen,Edge.Cuts','Back copper')]:
   n=len(pages)+1;svg=work/f'{n:02}-{side}.svg'
   board=HERE/side/(name+'.kicad_pcb')
   if heading.startswith('Assembly'):
    board=work/(side+'-numbered.kicad_pcb');subprocess.run([a.kicad_python,str(HERE/'assembly_copy.py'),side,str(board)],check=True,stdout=subprocess.DEVNULL)
   cmd=['kicad-cli','pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','--black-and-white','-l',layers,'-o',str(svg),str(board)]
   if heading.startswith('Assembly'):cmd.insert(4,'--sketch-pads-on-fab-layers')
   subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   raw=svg.read_text();start=raw.index('<svg');native=raw[start:];native=re.sub(r'<svg\b[^>]*>',lambda mm:re.sub(r'\s(?:width|height)="[^"]*"','',mm[0]).replace('<svg','<svg x="24" y="44" width="372" height="223"',1),native,count=1)
   desc='147 electrical references /194 x142mm' if side=='base' else '145 electrical references /100 x100mm; JMOD mounted on BOTTOM'
   pages.append(makepage(label+' / '+heading,desc,native,n))
   if heading.startswith('Assembly'):
    parts=sorted(json.loads((HERE/side/'circuit.json').read_text())['parts'],key=lambda p:p['ref']);rows=(len(parts)+3)//4;legend=''
    for col in range(4):
     x=16+col*98
     legend+=txt(x,45,'NO.  REFERENCE       VALUE','small')
    for ix,q in enumerate(parts):
     col=ix//rows;row=ix%rows;x=16+col*98;y=54+row*5.8
     legend+=txt(x,y,str(ix+1),'small')+txt(x+8,y,q['ref'],'small')+txt(x+35,y,q['value'][:36],'small')
    pages.append(makepage(label+' / assembly key',str(len(parts))+' electrical references; exact values and footprints are also in bom.csv',legend,len(pages)+1))
 pdfs=[]
 for i,s in enumerate(pages,1):
  f=work/f'page-{i:02}.svg';f.write_text(s);pdf=work/f'page-{i:02}.pdf';subprocess.run(['rsvg-convert','-f','pdf','-o',str(pdf),str(f)],check=True);pdfs.append(pdf)
 merged=work/'joined.pdf';subprocess.run(['pdfunite',*map(str,pdfs),str(merged)],check=True)
 subprocess.run(['gs','-q','-dNOPAUSE','-dBATCH','-sDEVICE=pdfwrite','-dCompatibilityLevel=1.7','-sOutputFile='+str(a.output),str(merged)],check=True)
 print('PDF',len(pages),'pages',a.output)
if __name__=='__main__':main()
