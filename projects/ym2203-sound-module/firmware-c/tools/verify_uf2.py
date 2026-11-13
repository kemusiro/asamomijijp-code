# SPDX-License-Identifier: MIT
"""Inspect the official RP2350 UF2 container,including RP2350-E10 absolute prefix."""
from pathlib import Path
import argparse
import struct


def flash_image(data):
    if not data or len(data)%512:raise ValueError('UF2 size')
    flash=bytearray(b'\xff')*(4*1024*1024);addresses=set();real=0;total_expected=len(data)//512-1
    for offset in range(0,len(data),512):
        block=data[offset:offset+512]
        magic0,magic1,flags,target,length,index,total,family=struct.unpack_from('<8I',block)
        if (magic0,magic1)!=(0x0a324655,0x9e5d5157) or struct.unpack_from('<I',block,508)[0]!=0x0ab16f30:raise ValueError('UF2 magic')
        if offset==0:
            # Official picotool2.2.0 RP2350-E10 workaround prefix;not executable payload.
            if (flags,target,length,index,total,family)!=(0xa000,0x10ffff00,256,0,2,0xe48bff57):raise ValueError('RP2350 prefix')
            if block[32:288]!=b'\xef'*256 or struct.unpack_from('<I',block,288)[0]!=0x9957e304:raise ValueError('RP2350 ignore extension')
            continue
        if family!=0xe48bff59 or flags!=0x2000 or length!=256 or index!=real or total!=total_expected:raise ValueError('UF2 target/order')
        if not 0x10000000<=target<0x10400000 or target+length>0x10400000 or target in addresses:raise ValueError('UF2 bounds/overlap')
        addresses.add(target);flash[target-0x10000000:target-0x10000000+length]=block[32:32+length];real+=1
    return flash


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('uf2',type=Path);parser.add_argument('--song',type=Path);args=parser.parse_args()
    flash=flash_image(args.uf2.read_bytes())
    if args.song and flash.count(args.song.read_bytes())!=1:raise ValueError('Source WYM1 not preserved exactly once')
    print('PASS: RP2350-E10 prefix,Arm Secure family,block order,address bounds and optional exact song payload')
if __name__=='__main__':main()
