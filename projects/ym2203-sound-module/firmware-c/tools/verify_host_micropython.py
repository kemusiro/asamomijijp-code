# SPDX-License-Identifier: MIT
"""Run actual MicroPython host against actual native C stream core over modelled I2C/time."""
import argparse
import binascii
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
CHILD=r'''
import sys,binascii
import ym2203_revc_stream as host
class Clock:
    now=0
    def ticks_ms(self):return (self.now//1000)&((1<<30)-1)
    def ticks_diff(self,a,b):return ((a-b+(1<<29))&((1<<30)-1))-(1<<29)
    def sleep_ms(self,ms):
        self.now+=ms*1000
        print('S',ms)
        if sys.stdin.readline().strip()!='OK':raise Exception('clock bridge')
clock=Clock();host.time=clock
class Bus:
    def writeto(self,address,data):
        clock.now+=(len(data)+1)*90
        print('W',binascii.hexlify(data).decode())
        return int(sys.stdin.readline())
    def readfrom(self,address,n):
        clock.now+=(n+1)*90
        print('R',n)
        return binascii.unhexlify(sys.stdin.readline().strip())
player=host.RevCStream(Bus())
result=player.play_file(sys.argv[1])
print('PASS',result['executed'],result['period_ms'],result['crc32'],result['max_late_us'],player.commands)
'''
RECOVERY_CHILD=CHILD[:CHILD.index('player=host.RevCStream(Bus())')]+r'''
import recovery_check as recovery
recovery.time=clock
recovery.print=lambda *args:print('LOG',*args)
def bind():
    print('B')
    if sys.stdin.readline().strip()!='OK':raise Exception('bind bridge')
    return Bus()
def release(bus):
    print('U')
    if sys.stdin.readline().strip()!='OK':raise Exception('release bridge')
results=recovery.run_check(bind,release,sys.argv[1])
if [s['state'] for s in results]!=[4,3,5,3]:raise Exception('wrong recovery states')
if [s['error'] for s in results]!=[0,0,8,0]:raise Exception('wrong recovery errors')
if [s['executed'] for s in results]!=[185,191,185,191]:raise Exception('wrong recovery counts')
final=results[-1]
print('PASS',final['executed'],final['period_ms'],final['crc32'],max(s['max_late_us'] for s in results),0)
'''
USB_CHILD=RECOVERY_CHILD[:RECOVERY_CHILD.index('results=recovery.run_check')].replace(
    'import recovery_check as recovery','import usb_disconnect_check as recovery')+r'''
final=recovery.run_check(bind,release,sys.argv[1])
if final['state']!=4 or final['error'] or final['queued']:raise Exception('wrong USB check final state')
print('PASS',final['executed'],final['period_ms'],final['crc32'],final['max_late_us'],0)
'''
PLAYER_CHILD=CHILD[:CHILD.index('player=host.RevCStream(Bus())')]+r'''
import ym2203_revc_player as playlist
playlist.time=clock
player=host.RevCStream(Bus())
choices=iter(['2','r 1','a','l','q'])
completed=0;interrupt_at=0;pending_interrupt=False
original_sleep=clock.sleep_ms
def player_sleep(ms):
    global pending_interrupt
    if pending_interrupt:
        pending_interrupt=False
        raise KeyboardInterrupt()
    original_sleep(ms)
clock.sleep_ms=player_sleep
def choose(prompt):
    global interrupt_at
    choice=next(choices)
    interrupt_at=completed+2 if choice=='r 1' else completed+3 if choice=='l' else 0
    return choice
def report(text):
    global completed,pending_interrupt
    print('LOG',text)
    if text.startswith('DONE /'):
        completed+=1
        if interrupt_at and completed==interrupt_at:pending_interrupt=True
playlist.run_console(player,sys.argv[1].rsplit('/',1)[0],read_line=choose,write=report)
if completed!=8:raise Exception('wrong playlist total')
final=player.status()
if final['state']!=4 or final['error'] or final['queued']:raise Exception('wrong player final state')
print('PASS',final['executed'],final['period_ms'],final['crc32'],final['max_late_us'],player.commands)
'''
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--micropython',type=Path,required=True)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--song',type=Path);mode.add_argument('--recovery',action='store_true',help='Run physical recovery HOST script against modelled I2C/time')
    mode.add_argument('--usb-disconnect',action='store_true',help='Run USB-disconnect HOST script; USB itself is not emulated by this stream-core test')
    mode.add_argument('--player',action='store_true',help='Run catalogue/menu and a two-track playlist against the C stream core')
    ap.add_argument('--keep-done-race',action='store_true',help='With --usb-disconnect, finish the target between its last RUNNING status and a final KEEP')
    a=ap.parse_args()
    if a.keep_done_race and not a.usb_disconnect:ap.error('--keep-done-race requires --usb-disconnect')
    if a.recovery or a.usb_disconnect or a.player:
        from embed_song import demo
        data=demo()
    else:data=a.song.read_bytes()
    total=struct.unpack_from('<I',data,4)[0]
    with tempfile.TemporaryDirectory(prefix='revc-host-') as folder:
        folder=Path(folder);lib=folder/'bridge.so'
        subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','-I'+str(ROOT/'src'),str(ROOT/'src/wym1.c'),str(ROOT/'src/stream.c'),str(ROOT/'src/transport.c'),str(ROOT/'tests/stream_bridge.c'),'-o',str(lib)],check=True)
        c=C.CDLL(str(lib));c.model_init(50);c.model_advance.argtypes=[C.c_uint64];c.model_command.argtypes=[C.c_void_p,C.c_uint];c.model_status.argtypes=[C.c_void_p];c.model_trace.restype=C.c_void_p;c.model_now.restype=C.c_uint64
        child=folder/'host.py';child.write_text(PLAYER_CHILD if a.player else USB_CHILD if a.usb_disconnect else RECOVERY_CHILD if a.recovery else CHILD)
        score=folder/'score.bin';score.write_bytes(data)
        if a.player:(folder/'second.bin').write_bytes(data)
        env=os.environ.copy();env['MICROPYPATH']=str(ROOT/'host/lib')+':'+str(ROOT/'host')
        p=subprocess.Popen([str(a.micropython),str(child),str(score)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,bufsize=1)
        passed=None
        activity=[];logs=[];bound=not (a.recovery or a.usb_disconnect);raced=False
        try:
            for line in p.stdout:
                tokens=line.strip().split()
                if not tokens:continue
                if tokens[0]=='W':
                    assert bound
                    packet=bytes.fromhex(tokens[1])
                    if a.keep_done_race and packet[3]==5 and not raced:
                        out=C.create_string_buffer(64);c.model_status(out)
                        period=struct.unpack_from('<I',out.raw,32)[0];elapsed=struct.unpack_from('<I',out.raw,40)[0]
                        if out.raw[9]==2 and out.raw[11]&8 and elapsed>=period-250:
                            c.model_advance((period-elapsed+1)*1000);raced=True
                    c.model_advance((len(packet)+1)*90);c.model_command(packet,len(packet));reply=str(len(packet))
                elif tokens[0]=='R':
                    assert bound
                    n=int(tokens[1]);out=C.create_string_buffer(64);c.model_status(out);reply=out.raw.hex();c.model_advance((n+1)*90)
                elif tokens[0]=='S':c.model_advance(int(tokens[1])*1000);reply='OK'
                elif tokens[0] in ('B','U'):
                    assert bound==(tokens[0]=='U')
                    bound=tokens[0]=='B'
                    activity.append((tokens[0],c.model_now(),c.model_trace_count()))
                    reply='OK'
                elif tokens[0]=='LOG':logs.append(line.strip());continue
                elif tokens[0]=='PASS':passed=list(map(int,tokens[1:]));break
                else:raise RuntimeError('MicroPython host: '+line.strip())
                p.stdin.write(reply+'\n');p.stdin.flush()
            p.wait(timeout=5)
            if p.returncode or passed is None:raise RuntimeError('MicroPython host did not pass')
        finally:
            if p.poll() is None:p.kill();p.wait()
        actual=C.string_at(c.model_trace(),2*c.model_trace_count());expected=b''.join(data[i+4:i+6] for i in range(16,len(data),6))
        if a.recovery:expected=expected[:185*2]+expected+expected[:185*2]+expected
        elif a.player:expected=expected*8
        assert actual==expected and passed[0]==total and passed[2]==binascii.crc32(data)&0xffffffff
        version=subprocess.check_output([str(a.micropython),'-c','import sys;print(sys.version)'],text=True).strip()
        report={'passed':True,'runtime':version,'scope':'Actual MicroPython host and actual C core,modelled100kHz wire/time,YM service50us;not electrical hardware','events':passed[0],'period_ms':passed[1],'crc32':passed[2],'max_late_us':passed[3],'source_sha256':hashlib.sha256(data).hexdigest(),'register_value_order_exact':True}
        if a.recovery:
            assert [e[0] for e in activity]==['B','U','B','U']
            assert activity[2][1]-activity[1][1]==1800000 and activity[2][2]==activity[1][2]
            assert any('HOST PASS:' in line for line in logs)
            report.update(mode='STOP/lease/rebind/replay',sections=4,completions=2,interruptions=2,register_writes=c.model_trace_count(),host_pins_rebound=True)
        elif a.usb_disconnect:
            assert [e[0] for e in activity]==['B','U']
            assert any('HOST PASS:' in line for line in logs)
            report.update(mode='USB-disconnect HOST completion/quiet check; physical USB removal not observed',register_writes=c.model_trace_count(),final_state=4)
            if a.keep_done_race:
                assert raced
                report['KEEP_rejected_after_DONE_race_exercised']=True
        elif a.player:
            assert sum(line.startswith('LOG DONE /') for line in logs)==8
            assert sum(line.startswith('LOG STOP /') for line in logs)==2
            assert any('PLAYLIST DONE / tracks=2 cycles=1' in line for line in logs)
            report.update(mode='Catalogue/menu with scripted2,r1,a,l,q choices; injected Ctrl+C exceptions stop repeats',
                          tracks_completed=8,repeat_interruptions=2,register_writes=c.model_trace_count(),final_state=4,commands=passed[4])
        else:report['commands']=passed[4]
        print(json.dumps(report,indent=2))
if __name__=='__main__':main()
