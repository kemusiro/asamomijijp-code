#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify immutable usbcorev sources, apply the versioned F1 patch to an output copy."""
import argparse,hashlib,json,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'vendor/usbcorev'

def prepare(output):
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):raise FileExistsError('Use an empty vendor build directory')
    output.mkdir(parents=True,exist_ok=True)
    pin=json.loads((BASE/'upstream.json').read_text())
    for name,digest in pin['files_sha256'].items():
        data=(BASE/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Changed upstream source '+name)
        (output/name).write_bytes(data)
    subprocess.run(['patch','-p1','--batch','-i',str(BASE/'patches/f1-validation.patch')],cwd=output,check=True)
    # Upstream style waivers are scoped to the generated vendor copies only.
    rules=['DECLFILENAME','PINCONNECTEMPTY','WIDTHEXPAND','UNUSEDPARAM','CASEINCOMPLETE']
    config='`verilator_config\n'+''.join('lint_off -rule '+r+' -file "'+str(output/'*.v')+'"\n' for r in rules)
    (output/'vendor.vlt').write_text(config)
    return sorted(output.glob('*.v'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.output)
