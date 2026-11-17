#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PC reference for editor voice interchange and torn-write recovery. Not P2 firmware."""
import copy,json,struct,zlib
FIELDS=('dt','mul','tl','ks','ar','dr','sr','sl','rr','ssg_eg','enabled')
LIMITS=(7,15,127,3,31,31,31,15,15,15,1)
OFFSETS=(0,8,4,12)  # logical algorithm OP1..4 -> OPN parameter slot offset
FORMAT='p2-ym2203-voice';SCHEMA=1;SIZE=32768;SLOTS=64;RECORD=256

def integer(v,lo,hi):
    if type(v) is not int or not lo<=v<=hi:raise ValueError('integer range')
    return v

def validate(v):
    if not isinstance(v,dict) or set(v)!=set(('format','version','chip','clock_hz','name','algorithm','feedback','preview_note','preview_velocity','operators')):raise ValueError('voice keys')
    if v['format']!=FORMAT or type(v['version']) is not int or v['version']!=1 or v['chip']!='YM2203':raise ValueError('format')
    integer(v['clock_hz'],1,100000000);integer(v['algorithm'],0,7);integer(v['feedback'],0,7);integer(v['preview_note'],0,127);integer(v['preview_velocity'],1,127)
    if not isinstance(v['name'],str) or not 1<=len(v['name'].encode('utf8'))<=24 or any(ord(c)<32 for c in v['name']):raise ValueError('name')
    if type(v['operators']) is not list or len(v['operators'])!=4:raise ValueError('operators')
    for op in v['operators']:
        if type(op) is not dict or set(op)!=set(FIELDS):raise ValueError('operator keys')
        for k,hi in zip(FIELDS,LIMITS):integer(op[k],0,hi)
    return copy.deepcopy(v)

def default_voice():
    op=dict(zip(FIELDS,(0,1,96,0,31,0,0,0,8,0,1)))
    v=dict(format=FORMAT,version=1,chip='YM2203',clock_hz=4000000,name='Init quiet sine',algorithm=7,feedback=0,preview_note=60,preview_velocity=80,operators=[copy.deepcopy(op) for _ in range(4)])
    v['operators'][3]['tl']=48
    return validate(v)

def loads(text):
    if not isinstance(text,str) or len(text.encode('utf8'))>4096:raise ValueError('file too large')
    def unique(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate key')
            d[k]=v
        return d
    return validate(json.loads(text,object_pairs_hook=unique))

def dumps(voice):return json.dumps(validate(voice),ensure_ascii=False,indent=2)+'\n'

def register_plan(voice,channel=0):
    v=validate(voice);integer(channel,0,2);out=[(0x28,channel)]
    for o,p in zip(OFFSETS,v['operators']):
        values=((0x30,p['dt']<<4|p['mul']),(0x40,p['tl']),(0x50,p['ks']<<6|p['ar']),(0x60,p['dr']),(0x70,p['sr']),(0x80,p['sl']<<4|p['rr']),(0x90,p['ssg_eg']))
        out.extend((base+o+channel,value) for base,value in values)
    out.append((0xB0+channel,v['feedback']<<3|v['algorithm']))
    return out  # includes key OFF, never key ON, never clock/timer/SSG writes

def encode(voice,slot,generation):
    v=validate(voice);integer(slot,0,63);integer(generation,0,0xffffffff);b=bytearray(256)
    b[:4]=b'Y2VP';struct.pack_into('<BBHI',b,4,1,slot,80,generation)
    b[16:20]=bytes((v['algorithm'],v['feedback'],v['preview_note'],v['preview_velocity']))
    name=v['name'].encode('utf8');b[24:24+len(name)]=name
    b[48:92]=bytes(p[k] for p in v['operators'] for k in FIELDS);struct.pack_into('<I',b,92,v['clock_hz'])
    struct.pack_into('<I',b,12,zlib.crc32(b[:12]+b[16:255]));b[255]=0xA5
    return bytes(b)

def decode(data,slot,committed=True):
    if len(data)!=256 or data[:4]!=b'Y2VP' or (committed and data[255]!=0xA5):raise ValueError('record header')
    ver,s,n,g=struct.unpack_from('<BBHI',data,4)
    if (ver,s,n)!=(1,slot,80) or zlib.crc32(data[:12]+data[16:255])!=struct.unpack_from('<I',data,12)[0]:raise ValueError('record CRC/identity')
    if any(data[20:24]) or any(data[96:255]):raise ValueError('reserved')
    raw=data[24:48];name=raw.split(b'\0',1)[0]
    if raw[len(name):].strip(b'\0'):raise ValueError('name padding')
    v=default_voice();v.update(algorithm=data[16],feedback=data[17],preview_note=data[18],preview_velocity=data[19],name=name.decode('utf8'),clock_hz=struct.unpack_from('<I',data,92)[0],operators=[dict(zip(FIELDS,data[48+i*11:59+i*11])) for i in range(4)])
    return validate(v),g

def active(memory,slot):
    integer(slot,0,63)
    if len(memory)!=SIZE:raise ValueError('FRAM size')
    good=[]
    for copy_id in (0,1):
        start=(slot*2+copy_id)*256
        try:v,g=decode(bytes(memory[start:start+256]),slot);good.append((copy_id,v,g))
        except (ValueError,UnicodeError):pass
    if not good:raise ValueError('empty or corrupt preset')
    if len(good)==2:
        a,b=good;delta=(b[2]-a[2])&0xffffffff
        if delta==0x80000000:raise ValueError('ambiguous generation')
        return b if 0<delta<0x80000000 else a
    return good[0]

def save(memory,slot,voice,cut_after=None):
    """Model byte writes, readback, commit-last; cut_after simulates loss between writes."""
    validate(voice);integer(slot,0,63)
    if len(memory)!=SIZE:raise ValueError('FRAM size')
    try:c,_,g=active(memory,slot);target=1-c;generation=(g+1)&0xffffffff
    except ValueError:
        # Only treat wholly invalid copies as empty. Ambiguous valid copies must not be overwritten.
        any_valid=False
        for c in (0,1):
            try:decode(bytes(memory[(slot*2+c)*256:(slot*2+c+1)*256]),slot);any_valid=True
            except (ValueError,UnicodeError):pass
        if any_valid:raise
        target=0;generation=0
    start=(slot*2+target)*256;record=encode(voice,slot,generation)
    writes=[(255,0)]+list(enumerate(record[:255]))
    count=0
    for offset,value in writes:
        if cut_after is not None and count>=cut_after:return False
        memory[start+offset]=value;count+=1
    decode(bytes(memory[start:start+256]),slot,committed=False)
    if cut_after is not None and count>=cut_after:return False
    memory[start+255]=0xA5
    assert active(memory,slot)[1]==validate(voice)
    return True

class Pickup:
    """Normalized 12-bit ADC soft takeover, rearm on every operator/page/load change."""
    def __init__(self,target):self.target=integer(target,0,4095);self.previous=None;self.latched=False
    def sample(self,value):
        integer(value,0,4095)
        if abs(value-self.target)<=32 or self.previous is not None and min(value,self.previous)<=self.target<=max(value,self.previous):self.latched=True
        self.previous=value
        return value if self.latched else None
