# SPDX-License-Identifier: MIT
"""Inspect a local RCD1 diagnostic;export raw FM and the C-path PCM as WAV files."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import wave
import zlib
SIZE=432150
RAW_OFFSET=98400
FRAMES=111250

def parse(data):
    if len(data)!=SIZE or data[:4]!=b'RCD1':raise ValueError('Expected fixed432150-byte RCD1')
    h=struct.unpack_from('<23I',data,4)
    expected={0:96,1:SIZE,2:4000000,3:72,4:625,5:178,6:FRAMES,8:96,9:RAW_OFFSET,10:6,11:3}
    for index,value in expected.items():
        if h[index]!=value:raise ValueError('Unsupported header field at byte%d'%(4+index*4))
    count=h[7]
    if not 0<count<=16384 or h[15]>16 or h[16]>1 or h[19] or any(h[20:]):raise ValueError('Invalid/overflow diagnostic header')
    if h[12] not in (30000000,31000000,32000000,33000000):raise ValueError('Unexpected capture start')
    if not h[12]+11250<=h[13]<=h[12]+50000 or not 1900000<=h[14]-h[13]<=2100000:raise ValueError('Capture timing out of bounds')
    trace=[struct.unpack_from('<IBB',data,96+6*i) for i in range(count)]
    if any(a[0]>b[0] for a,b in zip(trace,trace[1:])):raise ValueError('Trace times not monotonic')
    if trace[-1][0]>h[14]+100000:raise ValueError('Trace extends beyond capture')
    words=[int.from_bytes(data[p:p+3],'little') for p in range(RAW_OFFSET,SIZE,3)]
    return h,trace,words

def decode(words):
    samples=[];exponents=Counter();unused=Counter();noncanonical=0
    for word in words:
        code=word>>11;exponent=code>>10;mantissa=code&1023
        if not exponent:raise ValueError('Invalid exponent0 in captured FM')
        exponents[exponent]+=1;unused[word&2047]+=1
        if exponent>1 and 256<=mantissa<768:noncanonical+=1
        samples.append((mantissa-512)*(1<<(exponent-1)))
    return samples,exponents,unused,noncanonical

def pcm(samples,gain):
    result=[];clipped=0
    for base in range(0,len(samples),625):
        block=samples[base:base+625]
        for i in range(540):
            index,fraction=divmod(i*125,108)
            value=(block[index]*(108-fraction)+block[index+1]*fraction)//108
            value=value*gain//8
            if not -32768<=value<=32767:clipped+=1
            result.append(max(-32768,min(32767,value)))
    return result,clipped

def write_wave(path,samples,rate):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
        f.writeframes(struct.pack('<%dh'%len(samples),*samples))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('capture',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--song',type=Path);a=ap.parse_args()
    if a.capture.stat().st_size!=SIZE:raise ValueError('Unexpected capture size')
    data=a.capture.read_bytes();h,trace,words=parse(data);samples,exp,unused,noncanonical=decode(words);output,clipped=pcm(samples,h[15])
    report={'format':'RCD1','scope':'Captured digital FM only;no analog line signal orSSG recording','capture_first_frame_estimate_us':h[13]-11250,'capture_last_dma_done_us':h[14],
      'raw_frames':len(samples),'trace_events':len(trace),'clock_hz':h[2],'sample_clock_divisor':h[3],'gain_eighths':h[15],'bus_fast':bool(h[16]),
      'peak_raw':max(map(abs,samples)),'peak_pcm':max(map(abs,output)),'clipped_output_samples':clipped,
      'exponents':dict(sorted(exp.items())),'unused11_bit_values':dict(unused.most_common(16)),'noncanonical_codes':noncanonical,
      'max_adjacent_raw_step':max(abs(a-b) for a,b in zip(samples,samples[1:])),
      'notes':['Noncanonical codes/large adjacent steps alone do not prove a fault','Raw WAV uses55556Hz integer approximation of4000000/72','PCM WAV matches block-local125:108 interpolation and the fixed gain recorded in header','DMA timestamps mark software observation,not exact wire-edge timing']}
    if a.song:
        song=a.song.read_bytes()
        if song[:4]!=b'WYM1' or zlib.crc32(song)!=h[17]:raise ValueError('Source WYM1 CRC mismatch')
        total=struct.unpack_from('<I',song,4)[0]
        if total!=h[18] or len(song)!=16+6*total or len(trace)>total:raise ValueError('Source WYM1 size/count mismatch')
        late=[]
        for i,(us,reg,val) in enumerate(trace):
            ms,r,v=struct.unpack_from('<IBB',song,16+6*i)
            if (reg,val)!=(r,v) or us<ms*1000:raise ValueError('Trace/source order or time mismatch at event%d'%i)
            late.append(us-ms*1000)
        report['source_prefix_register_order_preserved']=True
        report['max_write_return_late_us']=max(late)
        report['write_return_late_30_35s_us']={'max':max((v for (t,r,x),v in zip(trace,late) if 30000000<=t<35000000),default=None)}
    if a.out.exists():raise FileExistsError('Use a new output directory')
    a.out.mkdir(parents=True)
    write_wave(a.out/'fm-wire.wav',samples,55556);write_wave(a.out/'fm-pcm.wav',output,48000)
    (a.out/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    (a.out/'register-trace.json').write_text(json.dumps(trace)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
