#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild one review PDF (schematic + unrouted fixture) and the text SVG preview."""
import argparse,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--schematic-dir',type=Path,default=HERE/'schematic');p.add_argument('--pdf',type=Path,required=True);a=p.parse_args();a.pdf.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='p2-review-') as temp:
  t=Path(temp)
  subprocess.run(['kicad-cli','sch','export','pdf','--black-and-white','--exclude-pdf-property-popups','-o',str(t/'schematic.pdf'),str(a.schematic_dir/'p2-carrier.kicad_sch')],check=True)
  subprocess.run(['kicad-cli','pcb','export','pdf','--layers','F.Cu,F.SilkS,Edge.Cuts,Dwgs.User','--mode-single','--scale','1.5','--black-and-white','--no-property-popups','-o',str(t/'fixture.pdf'),str(a.schematic_dir/'p2-header-placement.kicad_pcb')],check=True)
  subprocess.run(['pdfunite',str(t/'schematic.pdf'),str(t/'fixture.pdf'),str(a.pdf)],check=True)
 svg=a.schematic_dir/'p2-header-placement.svg'
 subprocess.run(['kicad-cli','pcb','export','svg','--layers','F.Cu,F.SilkS,Edge.Cuts,Dwgs.User','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','-o',str(svg),str(a.schematic_dir/'p2-header-placement.kicad_pcb')],check=True)
 # KiCad SVG writer emits trailing blanks; normalize generated text for repository checks.
 svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
 print('Exported review PDF and normalized SVG; no fabrication output')
if __name__=='__main__':main()
