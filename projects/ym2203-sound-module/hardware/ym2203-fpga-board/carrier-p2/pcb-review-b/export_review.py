#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export one review PDF: scope/budgets, native schematic and all PCB copper layers.
Requires KiCad CLI and Poppler; generated PDF/PNG belong in ignored outputs/.
"""
import argparse,subprocess,tempfile,json,html
from pathlib import Path
HERE=Path(__file__).resolve().parent

def run(*cmd):subprocess.run(list(map(str,cmd)),check=True)
def main():
 a=argparse.ArgumentParser();a.add_argument('--pdf',type=Path,required=True);v=a.parse_args();v.pdf.parent.mkdir(parents=True,exist_ok=True);o=HERE/'schematic'
 d=json.loads((o/'verification.json').read_text())
 with tempfile.TemporaryDirectory(prefix='p2-pcb-review-') as td:
  t=Path(td)
  rows=[('P2 revision 2.1 / PCB review B',30),('PGA2350 + real YM2203C + Si5351A | 2026-11-16',15),('',7),('164 components | 164 x 124 mm | 4 copper layers',19),('In1.Cu: solid GND reference; F.Cu / In2.Cu / B.Cu: routing',14),('Native KiCad DRC: 0 violations, 0 unconnected, 0 parity differences',16),('Native ERC: 0 violations | 47 GPIO / UNO contact coordinates unchanged',14),('Five standard auxiliary checks are disabled; see DRC report for exact scope.',13),('',8),('POWER / calculated budgets, not bench measurements',18),('PGA 3V3: 259.4 / 300 mA | AUX 3V3: 150 / 500 mA',15),('External regulated 5V: 674.4 mA design budget; 1.5A supply target',14),('Shield loads: 3V3 <= 100 mA; optional 5V <= 100 mA; 3.3V signals only',14),('',8),('MECHANICAL / conditional stack',18),('64 individual square-pin sockets; standard four 2x8 strips interfere at corners',14),('PGA bottom 9.5 mm / top envelope 13.1 mm; verify fitted sample and engagement',14),('UNO headers 8.51 mm nominal; shield underhang <= 5 mm; no fastener at H3',14),('',8),('Preserved: HOST GP0/GP1 -> target GP20/GP21; 0x42, 100kHz, I2C v2',14),('P2 firmware port, current/thermal/USB tests and fabrication release remain pending.',14),('This is a routed prototype candidate, not physical hardware acceptance.',16)]
  y=40;ss=['<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 1123 794"><rect width="1123" height="794" fill="white"/>']
  for text,size in rows:
   y+=size+11
   if text:ss.append(f'<text x="54" y="{y}" font-family="sans-serif" font-size="{size}" fill="#172e46">{html.escape(text)}</text>')
  ss.append('</svg>');(t/'cover.svg').write_text('\n'.join(ss))
  run('rsvg-convert','-f','pdf','-o',t/'cover.pdf',t/'cover.svg')
  run('kicad-cli','sch','export','pdf','--black-and-white','--exclude-pdf-property-popups','-o',t/'schematic.pdf',o/'p2-carrier-b.kicad_sch')
  pdfs=[t/'cover.pdf',t/'schematic.pdf']
  for name,layers in [('front','F.Cu,F.SilkS,Edge.Cuts'),('ground','In1.Cu,Edge.Cuts'),('inner','In2.Cu,Edge.Cuts'),('back','B.Cu,B.SilkS,Edge.Cuts'),('assembly','F.Fab,F.SilkS,Edge.Cuts')]:
   p=t/(name+'.pdf');extra=['--black-and-white'] if name=='assembly' else [];run('kicad-cli','pcb','export','pdf','--layers',layers,'--mode-single','--scale','0.95','--include-border-title','--no-property-popups',*extra,'-o',p,o/'p2-carrier-b.kicad_pcb');pdfs.append(p)
  run('pdfunite',*pdfs,t/'combined.pdf')
  # Rewrite cross-reference streams: native multi-PDF joining can leave malformed Length entries.
  run('gs','-q','-dSAFER','-dBATCH','-dNOPAUSE','-sDEVICE=pdfwrite','-dPDFSETTINGS=/prepress','-dCompatibilityLevel=1.7','-sOutputFile='+str(v.pdf),t/'combined.pdf')
 print('Exported one review PDF; not a manufacturing package')
if __name__=='__main__':main()
