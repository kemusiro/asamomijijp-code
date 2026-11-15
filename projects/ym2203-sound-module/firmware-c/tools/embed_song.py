# SPDX-License-Identifier: MIT
"""Validate WYM1,embed read-only flash bytes;never modify the source score."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def valid_register(r,v):
    if r<=13:
        if r in (1,3,5,13):return v<=15
        if r==6:return v<=31
        if r==7:return v<=63
        if 8<=r<=10:return v<=31
        return True
    if r==0x28:return not v&12 and v&3!=3
    if r in (0x24,0x26):return True
    if r==0x25:return v<=3
    if r==0x27:return v<=63
    if 0x30<=r<=0x9e and r&3!=3:
        group=r>>4;mask=127 if group<=4 else 223 if group==5 else 159 if group==6 else 31 if group==7 else 255 if group==8 else 15
        return not v&~mask
    return 0xa0<=r<=0xa2 or ((0xa4<=r<=0xa6 or 0xb0<=r<=0xb2) and v<=63)


def validate(data):
    if len(data)<16:raise ValueError('Short WYM1 header')
    magic,n,period,clock=struct.unpack_from('<4sIII',data)
    if magic!=b'WYM1' or not 1<=n<=131071 or not period or clock!=4000000 or len(data)!=16+6*n:raise ValueError('Invalid WYM1 shape/clock')
    last=0
    for i,(t,r,v) in enumerate(struct.iter_unpack('<IBB',data[16:])):
        if not last<=t<=period or not valid_register(r,v):raise ValueError('Invalid event at index%d'%i)
        last=t
    return {'events':n,'period_ms':period,'clock_hz':clock,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'crc32':zlib.crc32(data)}


def demo():
    events=[]
    def w(t,r,v):events.append((t,r,v))
    w(0,0x27,0)
    for c in range(3):w(0,0x28,c);w(0,8+c,0)
    w(0,7,0x38)
    for c in range(3):
        for slot in (0,4,8,12):
            for base,value in ((0x30,1),(0x40,0 if slot==0 else 127),(0x50,31),(0x60,0),(0x70,0),(0x80,15),(0x90,0)):w(0,base+slot+c,value)
        w(0,0xb0+c,7)
    highs=(0x22,0x22,0x23,0x23,0x23);lows=(0x69,0xb5,0x0a,0x38,0x9d)
    periods=(239,213,190,179,160)
    for family,start in ((0,500),(1,5500)):
        for i,note in enumerate((0,1,2,3,4,3,2,1,0)):
            t=start+500*i
            if family:
                w(t,0,periods[note]&255);w(t,1,periods[note]>>8);w(t,8,7);w(t+400,8,0)
            else:
                w(t,0xa4,highs[note]);w(t,0xa0,lows[note]);w(t,0x28,0x10);w(t+400,0x28,0)
    for c,note in enumerate((0,2,4)):
        w(10500,0xa4+c,highs[note]);w(10500,0xa0+c,lows[note]);w(10500,0x28,0x10+c)
        period=(478,379,319)[c];w(10500,2*c,period&255);w(10500,2*c+1,period>>8);w(10500,8+c,7)
    for c in range(3):w(12500,0x28,c);w(12500,8+c,0)
    events.sort(key=lambda e:e[0])  # stable: preserve write order within a timestamp
    return struct.pack('<4sIII',b'WYM1',len(events),13000,4000000)+b''.join(struct.pack('<IBB',*e) for e in events)


def emit(name,data):
    rows=['// SPDX-License-Identifier: MIT','// Generated local asset;never commit a song-containing output.']
    rows.append('const unsigned char '+name+'[] __attribute__((aligned(4))) = {')
    rows.extend('  '+','.join('0x%02x'%v for v in data[i:i+24])+',' for i in range(0,len(data),24))
    rows.extend(['};','const unsigned int '+name+'_size = '+str(len(data))+'u;','const unsigned int '+name+'_crc = '+str(zlib.crc32(data))+'u;'])
    return '\n'.join(rows)+'\n'


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',default='');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    original=demo();data=Path(a.input).read_bytes() if a.input else original
    report=validate(data);report['kind']='local user-provided song;not for redistribution' if a.input else 'original synthetic FM/SSG scales and chord'
    report['event_bytes_preserved']=True
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(emit('revc_demo',original)+emit('revc_song',data))
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: WYM1 validated;'+str(report['events'])+' events;source bytes unchanged')


if __name__=='__main__':main()
