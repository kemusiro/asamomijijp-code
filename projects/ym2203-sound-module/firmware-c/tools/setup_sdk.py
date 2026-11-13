# SPDX-License-Identifier: MIT
"""Fetch pinned SDK sources into project cache;no global installation changes."""
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent

def run(*args):subprocess.run(args,check=True)
def commit(path):return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
def main():
    lock=json.loads((ROOT/'toolchain-lock.json').read_text());cache=PROJECT/'.cache';cache.mkdir(exist_ok=True)
    for key in ('pico_sdk','picotool'):
        entry=lock[key];path=cache/('pico-sdk-2.2.0' if key=='pico_sdk' else 'picotool-2.2.0')
        if not path.exists():run('git','clone','--depth','1','--branch',entry['version'],entry['repository'],str(path))
        if commit(path)!=entry['commit']:raise RuntimeError('Pinned commit mismatch:'+key)
    sdk=cache/'pico-sdk-2.2.0';tiny=sdk/'lib/tinyusb'
    run('git','-C',str(sdk),'submodule','update','--init','--depth','1','lib/tinyusb')
    if commit(tiny)!=lock['tinyusb']['commit']:raise RuntimeError('Pinned TinyUSB mismatch')
    run('cmake','-S',str(cache/'picotool-2.2.0'),'-B',str(cache/'picotool-build'),'-DPICO_SDK_PATH='+str(sdk),'-DPICOTOOL_NO_LIBUSB=1','-DCMAKE_INSTALL_PREFIX='+str(cache/'picotool-install'))
    run('cmake','--build',str(cache/'picotool-build'),'-j','4')
    run('cmake','--install',str(cache/'picotool-build'))
    print('PASS: pinned SDK/TinyUSB/picotool ready;all caches remain outside Git')
if __name__=='__main__':main()
