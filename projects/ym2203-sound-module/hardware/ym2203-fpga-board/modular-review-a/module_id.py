#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline64-byte draft EEPROM record builder. Not installed target firmware."""
import argparse,binascii,json,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent

def encode(d):
 b=bytearray(64)
 if (d['module_type'],d['audio_format'],d['chip_count'],d['fm_streams'],d['ssg_analog_channels'])!=(1,1,1,1,3):raise ValueError('Only reviewed YM2203x1 raw-FM profile is defined')
 if d['clock_hz']!=4000000:raise ValueError('Only4MHz is declared for this firmware profile')
 if not 0<d['budget_5v_ma']<=180 or not 0<d['budget_3v3_ma']<=20:raise ValueError('Module power budget exceeds review')
 struct.pack_into('<4s8BIHH',b,0,b'P2M1',1,64,d['module_type'],d['audio_format'],d['chip_count'],d['fm_streams'],d['ssg_analog_channels'],0,d['clock_hz'],d['budget_5v_ma'],d['budget_3v3_ma'])
 struct.pack_into('<I',b,60,binascii.crc32(b[:60])&0xffffffff)
 return bytes(b)

def decode(b):
 if len(b)!=64 or b[:6]!=b'P2M1\x01\x40':raise ValueError('ID header/length')
 if (binascii.crc32(b[:60])&0xffffffff)!=struct.unpack_from('<I',b,60)[0]:raise ValueError('ID CRC')
 if b[11] or any(b[20:60]):raise ValueError('Reserved ID bytes must be0')
 values=struct.unpack_from('<5BxIHH',b,6)
 d=dict(zip(['module_type','audio_format','chip_count','fm_streams','ssg_analog_channels','clock_hz','budget_5v_ma','budget_3v3_ma'],values))
 if encode(d)!=b:raise ValueError('Unsupported ID profile')
 return d

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,help='Optional raw64-byte programmer image; keep outside Git');a=p.parse_args()
 b=encode(json.loads((HERE/'module-id.json').read_text()));decode(b)
 if a.output:a.output.write_bytes(b)
 else:print(b.hex())
