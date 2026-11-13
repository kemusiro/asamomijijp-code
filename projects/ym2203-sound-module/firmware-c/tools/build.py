# SPDX-License-Identifier: MIT
"""Build and package an RP2350 UF2;optional local WYM1 is never copied into Git."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from embed_song import validate,demo
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git_head(path):return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
def run(args,env=None):subprocess.run([str(a) for a in args],env=env,check=True)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--song',type=Path);ap.add_argument('--host-song',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    output=a.output.resolve()
    if output.exists():raise FileExistsError('Use a new output filename;accepted artifacts are immutable')
    lock=json.loads((ROOT/'toolchain-lock.json').read_text());cache=PROJECT/'.cache';sdk=cache/'pico-sdk-2.2.0'
    for path,expected in [(sdk,lock['pico_sdk']['commit']),(sdk/'lib/tinyusb',lock['tinyusb']['commit']),(cache/'picotool-2.2.0',lock['picotool']['commit'])]:
        if git_head(path)!=expected:raise RuntimeError('SDK source commit mismatch;run setup_sdk.py')
    compiler=shutil.which('arm-none-eabi-gcc')
    if not compiler:raise RuntimeError('Install the pinned Arm GNU toolchain;global installation is not changed by this tool')
    version=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0]
    if lock['arm_gcc'] not in version:raise RuntimeError('Expected Arm GNU10.3.1 20210824;found '+version)
    licenses=Path(compiler).resolve().parents[1]/'share/doc/gcc-arm-none-eabi/license.txt'
    if not licenses.is_file():raise RuntimeError('Arm toolchain license bundle not found:'+str(licenses))
    song=a.song.resolve() if a.song else None
    if song:validate(song.read_bytes())
    host_song=a.host_song.resolve() if a.host_song else None
    host_asset=validate(host_song.read_bytes()) if host_song else None
    build=cache/('revc-c-private' if song else 'revc-c-demo')
    config=next((cache/'picotool-install').rglob('picotoolConfig.cmake'))
    env=os.environ.copy();env['PICO_SDK_PATH']=str(sdk)
    env['SOURCE_DATE_EPOCH']=str(int(datetime.datetime(2026,11,13,tzinfo=datetime.timezone.utc).timestamp()))
    run(['cmake','-S',ROOT,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-Dpicotool_DIR='+str(config.parent),'-DREVC_SONG='+str(song or '')],env)
    run(['cmake','--build',build,'-j','4'],env)
    picotool=next(p for p in (cache/'picotool-install').rglob('picotool') if p.is_file())
    info=subprocess.check_output([str(picotool),'info','-a',str(build/'revc_c.uf2')],text=True)
    if 'RP2350' not in info or 'ARM Secure' not in info:raise RuntimeError('Unexpected UF2 target')
    info=info.replace(str(build),'build')
    size=subprocess.check_output(['arm-none-eabi-size',str(build/'revc_c.elf')],text=True).splitlines()[1].split()
    stats={'text_bytes':int(size[0]),'data_bytes':int(size[1]),'bss_bytes':int(size[2])}
    if stats['text_bytes']+stats['data_bytes']>=4*1024*1024 or stats['data_bytes']+stats['bss_bytes']>=512*1024:raise RuntimeError('Unexpected image size')
    asset=json.loads((build/'song-data.json').read_text())
    members={'revc-c.uf2':(build/'revc_c.uf2').read_bytes(),'pc/revc-console.html':(ROOT/'pc/revc-console.html').read_bytes(),
      'README-ja.md':(ROOT/'README.md').read_bytes(),'LICENSE-MIT.txt':(PROJECT/'LICENSE').read_bytes(),
      'USB-MIDI-README.txt':(ROOT/'USB-MIDI-README.txt').read_bytes(),'pc/usb-midi-test.html':(ROOT/'pc/usb-midi-test.html').read_bytes(),
      'MIDI-RELEASE-FIX-README.txt':(ROOT/'MIDI-RELEASE-FIX-README.txt').read_bytes(),
      'MIDI-I2C-HANDOVER-README.txt':(ROOT/'MIDI-I2C-HANDOVER-README.txt').read_bytes(),
      'AUDIO-DMA-RESTART-README.txt':(ROOT/'AUDIO-DMA-RESTART-README.txt').read_bytes(),
      'LICENSE-I2S-BSD.txt':(ROOT/'THIRD_PARTY_LICENSES.txt').read_bytes(),'LICENSE-PICO-SDK.txt':(sdk/'LICENSE.TXT').read_bytes(),
      'LICENSE-TINYUSB.txt':(sdk/'lib/tinyusb/LICENSE').read_bytes(),'LICENSE-CMSIS.txt':(sdk/'src/rp2_common/cmsis/stub/CMSIS/LICENSE.txt').read_bytes(),
      'LICENSE-PICO-PRINTF.txt':(sdk/'src/rp2_common/pico_printf/LICENSE').read_bytes(),'LICENSE-ARM-TOOLCHAIN.txt':licenses.read_bytes(),
      'tools/analyze_capture.py':(ROOT/'tools/analyze_capture.py').read_bytes(),'diagnostic-format.md':(ROOT/'diagnostic-format.md').read_bytes(),
      'picotool-info.txt':info.encode(),'hardware-results.json':(ROOT/'hardware-results.json').read_bytes()}
    if b'/Users/' in members['revc-c.uf2'] or b'/private/tmp/' in members['revc-c.uf2']:raise RuntimeError('Build path leaked into UF2')
    for path in sorted((ROOT/'host').rglob('*.py')):members['host/'+str(path.relative_to(ROOT/'host'))]=path.read_bytes()
    members['protocol-v2.md']=(ROOT/'protocol-v2.md').read_bytes()
    members['I2C-YSII-README.txt']=(ROOT/'I2C-YSII-README.txt').read_bytes()
    members['I2C-RECOVERY-README.txt']=(ROOT/'I2C-RECOVERY-README.txt').read_bytes()
    members['host/music/recovery.bin']=demo()
    if host_song:members['host/music/song.bin']=host_song.read_bytes()
    members['LICENSE-PICO-I2C-SLAVE.txt']=(ROOT/'LICENSE-PICO-I2C-SLAVE.txt').read_bytes()
    manifest={'host_asset':host_asset,'version':lock['version'],'board':lock['board'],'hardware_tested':False,'scope':'WYM1 flash,I2C v2 streaming,USB-MIDI1.0 six voices and CDC;no REPL',
      'asset':asset,'toolchain':lock,'memory':stats,'source_sha256':{str(f.relative_to(ROOT)):sha(f) for f in sorted(ROOT.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and 'verification' not in f.relative_to(ROOT).parts and (f.suffix in ('.c','.h','.py','.pio','.mjs','.html') or f.name in ('CMakeLists.txt','README.md','THIRD_PARTY_LICENSES.txt','toolchain-lock.json','diagnostic-format.md','protocol-v2.md','I2C-YSII-README.txt','LICENSE-PICO-I2C-SLAVE.txt'))},
      'files':{name:hashlib.sha256(data).hexdigest() for name,data in members.items()}}
    members['build-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(members.items()):
            entry=zipfile.ZipInfo(name,(2026,11,13,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for name,digest in manifest['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    print('PASS: RP2350 UF2,source asset preservation,licenses,ZIP CRC and payload hashes')
    print('Package SHA256:',sha(output));print(output)
if __name__=='__main__':main()
