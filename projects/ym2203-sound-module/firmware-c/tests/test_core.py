# SPDX-License-Identifier: MIT
"""Run the actual portable C parser/converter/scheduler on host;no MCU emulation."""
import ctypes as C
import importlib.util
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
embed=module('embed',ROOT/'tools/embed_song.py')
policy=module('accepted_policy',ROOT.parent/'hardware/ym2203-single-board/firmware/src/ym2203_fw.py')
class File(C.Structure):_fields_=[('bytes',C.c_void_p),('count',C.c_uint32),('period_ms',C.c_uint32)]
class Player(C.Structure):_fields_=[('file',C.POINTER(File)),('origin_us',C.c_uint64),('index',C.c_uint32),('max_late_us',C.c_uint32),('late_hist',C.c_uint32*5),('state',C.c_int)]
class Guard(C.Structure):_fields_=[("last_progress_us",C.c_uint64),("sof",C.c_uint16),("valid",C.c_bool)]
WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint8,C.c_uint8)

class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='revc-c-test-');library=Path(cls.temp.name)/'core.so'
        subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',str(ROOT/'src/wym1.c'),'-o',str(library)],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.wym1_open.argtypes=[C.POINTER(File),C.c_void_p,C.c_size_t]
        cls.lib.revc_valid_register.argtypes=[C.c_uint8,C.c_uint8];cls.lib.revc_valid_register.restype=C.c_bool
        cls.lib.revc_i2s_div256.argtypes=[C.c_uint32,C.c_uint32];cls.lib.revc_i2s_div256.restype=C.c_uint32
        cls.lib.revc_crc32.argtypes=[C.c_void_p,C.c_size_t];cls.lib.revc_crc32.restype=C.c_uint32
        cls.lib.revc_convert.argtypes=[C.POINTER(C.c_uint32),C.POINTER(C.c_uint32),C.POINTER(C.c_uint32)]
        cls.lib.revc_convert_gain.argtypes=cls.lib.revc_convert.argtypes+[C.c_uint,C.c_uint]
        cls.lib.revc_parse_fm_gain.argtypes=[C.c_char_p,C.POINTER(C.c_uint)];cls.lib.revc_parse_fm_gain.restype=C.c_bool
        cls.lib.revc_player_start.argtypes=[C.POINTER(Player),C.POINTER(File),C.c_uint64]
        cls.lib.revc_player_stop.argtypes=[C.POINTER(Player)]
        cls.lib.revc_usb_alive.argtypes=[C.POINTER(Guard),C.c_uint64,C.c_uint16,C.c_bool];cls.lib.revc_usb_alive.restype=C.c_bool
        cls.lib.revc_player_tick.argtypes=[C.POINTER(Player),C.c_uint64,WRITE,C.c_void_p]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def open(self,data):
        buffer=C.create_string_buffer(data);f=File();result=self.lib.wym1_open(C.byref(f),buffer,len(data));return result,f,buffer
    def test_valid_register_policy_matches_accepted_MicroPython_for_all_65536_pairs(self):
        for r in range(256):
            for v in range(256):self.assertEqual(self.lib.revc_valid_register(r,v),policy.valid_register(r,v),(r,v))
    def test_parser_rejects_shape_clock_time_and_unsupported_registers_without_changing_output(self):
        good=embed.demo();_,f,backing=self.open(good);before=bytes(f)
        bad=[b'',good[:15],b'BAD!'+good[4:],good+b'\0',good[:4]+struct.pack('<I',131072)+good[8:],good[:12]+struct.pack('<I',3993600)+good[16:],good[:8]+b'\0'*4+good[12:]]
        for data in bad:
            b=C.create_string_buffer(data);self.assertNotEqual(self.lib.wym1_open(C.byref(f),b,len(data)),0);self.assertEqual(bytes(f),before)
        for records in [[(2,0,0),(1,0,0)],[(200,0,0)],[(0,0x2d,0)],[(0,0x27,0xc0)],[(0,7,255)]]:
            data=struct.pack('<4sIII',b'WYM1',len(records),100,4000000)+b''.join(struct.pack('<IBB',*r) for r in records)
            self.assertNotEqual(self.open(data)[0],0)
    def test_USB_SOF_wrap_close_and_timeout_require_fresh_progress(self):
        g=Guard();now=(1<<32)+1000
        self.assertFalse(self.lib.revc_usb_alive(C.byref(g),now,0,False))
        self.assertTrue(self.lib.revc_usb_alive(C.byref(g),now,2047,True))
        self.assertTrue(self.lib.revc_usb_alive(C.byref(g),now+1000,0,True))
        self.assertTrue(self.lib.revc_usb_alive(C.byref(g),now+250999,0,True))
        self.assertFalse(self.lib.revc_usb_alive(C.byref(g),now+251000,0,True))
        self.assertTrue(self.lib.revc_usb_alive(C.byref(g),now+251001,1,True))
        self.assertFalse(self.lib.revc_usb_alive(C.byref(g),now+251002,1,False))
    def test_I2S_rate_tracks_external_clock_drift_and_rejects_wrong_clock(self):
        self.assertEqual(self.lib.revc_i2s_div256(150000000,1440000),12500)
        # A100ppm slower FM input requires a slower I2S clock,not dropped frames.
        self.assertEqual(self.lib.revc_i2s_div256(150000000,1440144),12501)
        self.assertEqual(self.lib.revc_i2s_div256(150000000,1439856),12499)
        for elapsed in (0,1000000,1600000,0xffffffff):self.assertEqual(self.lib.revc_i2s_div256(150000000,elapsed),0)
    def test_crc32_matches_independent_standard_library(self):
        for data in (b'',b'123456789',embed.demo(),bytes(range(256))*8):
            b=C.create_string_buffer(data);self.assertEqual(self.lib.revc_crc32(b,len(data)),zlib.crc32(data))
    def test_conversion_matches_Python_floor_rounding_and_silent_right_channel(self):
        randomizer=random.Random(2203)
        for case in range(65):
            words=[((randomizer.randrange(1024)|(randomizer.randrange(1,8)<<10))<<19) for _ in range(625)]
            if case<8:words=[((case<<10)|511)<<19]*625
            source=(C.c_uint32*625)(*words);out=(C.c_uint32*540)();peak=C.c_uint32()
            flags=self.lib.revc_convert(source,out,C.byref(peak));expected=[];invalid=0
            for i in range(540):
                position=125*i;index,fraction=divmod(position,108);wa=words[index]>>19;wb=words[index+1]>>19;ea=wa>>10;eb=wb>>10
                if not ea or not eb:value=0;invalid=1
                else:value=(((wa&1023)-512)*(1<<(ea-1))*(108-fraction)+((wb&1023)-512)*(1<<(eb-1))*fraction)//108
                expected.append(value)
            self.assertEqual(flags,invalid)
            self.assertEqual([C.c_int16(v>>16).value for v in out],expected)
            self.assertTrue(all(v&65535==0 for v in out));self.assertEqual(peak.value,max(map(abs,expected)))
    def test_full_13bit_domain_corners_and_all_supported_gains_stay_in_PCM16(self):
        out=(C.c_uint32*540)();peak=C.c_uint32()
        for exponent in range(1,8):
            for mantissa in (0,1,511,512,513,1022,1023):
                raw=(mantissa-512)*(1<<(exponent-1))
                source=(C.c_uint32*625)(*([((exponent<<10)|mantissa)<<19]*625))
                for gain in range(9):
                    flags=self.lib.revc_convert_gain(source,out,C.byref(peak),gain,gain)
                    value=(raw*gain)//8
                    self.assertEqual(flags,0,(exponent,mantissa,gain))
                    self.assertTrue(all(C.c_int16(v>>16).value==value and v&65535==0 for v in out))
                    self.assertEqual(peak.value,abs(value));self.assertLessEqual(peak.value,32768)
    def test_every_valid_floating_code_at_all_gains_fits_PCM16_without_clipping(self):
        source=(C.c_uint32*625)();out=(C.c_uint32*540)();peak=C.c_uint32()
        for word in range(1024,8192):
            for i in range(625):source[i]=word<<19
            raw=((word&1023)-512)*(1<<((word>>10)-1))
            for gain in range(9):
                flags=self.lib.revc_convert_gain(source,out,C.byref(peak),gain,gain);expected=raw*gain//8
                self.assertEqual(flags,0,(word,gain))
                self.assertEqual(C.c_int16(out[0]>>16).value,expected);self.assertEqual(C.c_int16(out[539]>>16).value,expected)
                self.assertEqual(peak.value,abs(expected))
    def test_gain_ramp_is_bounded_monotonic_and_has_exact_endpoints(self):
        source=(C.c_uint32*625)(*([0x1fff<<19]*625));out=(C.c_uint32*540)();peak=C.c_uint32()
        for start,end in ((0,8),(8,0),(1,8),(8,1)):
            self.assertEqual(self.lib.revc_convert_gain(source,out,C.byref(peak),start,end),0)
            values=[C.c_int16(v>>16).value for v in out]
            self.assertEqual(values[0],32704*start//8);self.assertEqual(values[-1],32704*end//8)
            self.assertTrue(all((a<=b if start<end else a>=b) for a,b in zip(values,values[1:])))
        for start,end in ((17,8),(8,17),(0xffffffff,8)):
            self.assertEqual(self.lib.revc_convert_gain(source,out,C.byref(peak),start,end),4)
            self.assertTrue(all(v==0 for v in out));self.assertEqual(peak.value,0)
    def test_boost_saturates_without_integer_wrap_and_reports_exact_clipped_samples(self):
        self.lib.revc_convert_gain_ex.argtypes=self.lib.revc_convert_gain.argtypes+[C.POINTER(C.c_uint32)]
        out=(C.c_uint32*540)();peak=C.c_uint32();clipped=C.c_uint32()
        for word in (0x0400,0x0600,0x067f,0x1c00,0x1dff,0x1e00,0x1fff):
            raw=((word&1023)-512)*(1<<((word>>10)-1))
            source=(C.c_uint32*625)(*([word<<19]*625))
            for gain in range(17):
                flags=self.lib.revc_convert_gain_ex(source,out,C.byref(peak),gain,gain,C.byref(clipped))
                value=raw*gain//8;limited=max(-32768,min(32767,value));over=value!=limited
                self.assertEqual(flags,2 if over else 0);self.assertEqual(clipped.value,540 if over else 0)
                self.assertTrue(all(C.c_int16(v>>16).value==limited for v in out));self.assertEqual(peak.value,abs(limited))
        self.assertEqual(self.lib.revc_convert_gain_ex(source,out,C.byref(peak),17,8,C.byref(clipped)),4)
        self.assertEqual(clipped.value,0);self.assertTrue(all(v==0 for v in out))
    def test_ymfm_encode_decode_at_all_exponent_transitions_and_zero(self):
        # Independent inverse:ymfm encode_fp/roundtrip_fp in ymfm.h,81aec25.
        # A change in exponent must remain monotonic,not produce an amplitude jump.
        values={-32768,32767,0,-1,1}
        for power in range(8,16):
            for delta in range(-3,4):
                for sign in (-1,1):values.add(max(-32768,min(32767,sign*((1<<power)+delta))))
        out=(C.c_uint32*540)();peak=C.c_uint32();previous=-32769
        for value in sorted(values):
            scan=value if value>=0 else ~value
            exponent=max(1,scan.bit_length()-8)
            word=((exponent<<10)|((value>>(exponent-1))&1023))^512
            source=(C.c_uint32*625)(*([word<<19]*625))
            self.assertEqual(self.lib.revc_convert(source,out,C.byref(peak)),0)
            decoded=C.c_int16(out[0]>>16).value;expected=value&~((1<<(exponent-1))-1)
            self.assertEqual(decoded,expected);self.assertGreaterEqual(decoded,previous);previous=decoded
    def test_legacy_one_eighth_gain_is_bit_identical_to_previous_valid_conversion(self):
        rng=random.Random(3014);words=[((rng.randrange(1,8)<<10)|rng.randrange(1024))<<19 for _ in range(625)]
        source=(C.c_uint32*625)(*words);out=(C.c_uint32*540)();peak=C.c_uint32()
        self.assertEqual(self.lib.revc_convert_gain(source,out,C.byref(peak),1,1),0)
        expected=[]
        for i in range(540):
            index,fraction=divmod(i*125,108);wa=words[index]>>19;wb=words[index+1]>>19
            a=((wa&1023)-512)*(1<<((wa>>10)-1));b=((wb&1023)-512)*(1<<((wb>>10)-1))
            expected.append((a*(108-fraction)+b*fraction)//864)
        self.assertEqual([C.c_int16(v>>16).value for v in out],expected)
    def test_FM_gain_command_is_strict_and_never_modifies_state_on_invalid_input(self):
        for gain in range(17):
            value=C.c_uint(99);self.assertTrue(self.lib.revc_parse_fm_gain(('fm %d'%gain).encode(),C.byref(value)));self.assertEqual(value.value,gain)
        for command in (b'',b'fm',b'fm ',b'fm 17',b'fm 20',b'fm -1',b'fm 8 ',b'fm 08',b'fm 999999999999999999999999999999999999',b'fm 8x'):
            value=C.c_uint(99);self.assertFalse(self.lib.revc_parse_fm_gain(command,C.byref(value)));self.assertEqual(value.value,99)
    def replay(self,data,service_us=250,busy_every=0):
        result,f,backing=self.open(data);self.assertEqual(result,0)
        events=list(struct.iter_unpack('<IBB',data[16:]));p=Player();origin=(1<<32)+300000;self.lib.revc_player_start(C.byref(p),C.byref(f),origin)
        now=origin-1;writes=[];attempts=0
        @WRITE
        def writer(ctx,r,v):
            nonlocal attempts
            attempts+=1
            if busy_every and attempts%busy_every==0:return 0
            writes.append((r,v));return 1
        while p.state==1:
            due=origin+(events[p.index][0] if p.index<f.count else f.period_ms)*1000
            now=max(now,due);self.lib.revc_player_tick(C.byref(p),now,writer,None);now+=service_us
        return p,writes,now-origin,events
    def test_actual_C_scheduler_preserves_every_demo_event_same_timestamp_order_and_period(self):
        p,writes,elapsed,events=self.replay(embed.demo(),250,7)
        self.assertEqual(p.state,2);self.assertEqual(writes,[(r,v) for t,r,v in events]);self.assertEqual(sum(p.late_hist),len(events));self.assertGreaterEqual(elapsed,13000000)
    def test_stop_and_replay_require_explicit_start_and_keep_score(self):
        result,f,backing=self.open(embed.demo());self.assertEqual(result,0);p=Player();writes=[]
        @WRITE
        def writer(ctx,r,v):writes.append((r,v));return 1
        self.lib.revc_player_start(C.byref(p),C.byref(f),0);self.lib.revc_player_tick(C.byref(p),0,writer,None);self.lib.revc_player_stop(C.byref(p))
        count=len(writes)
        for t in (1,1000000,5000000):self.lib.revc_player_tick(C.byref(p),t,writer,None)
        self.assertEqual(len(writes),count);self.assertEqual(p.state,3)
        self.lib.revc_player_start(C.byref(p),C.byref(f),9000000);self.lib.revc_player_tick(C.byref(p),9000000,writer,None)
        self.assertEqual(writes[-1],writes[0]);self.assertEqual(p.index,1)
    def test_genuine_deadline_and_hardware_errors_fail_without_advancing(self):
        result,f,backing=self.open(embed.demo());self.assertEqual(result,0)
        for now,result in ((100001,1),(0,-1)):
            p=Player();self.lib.revc_player_start(C.byref(p),C.byref(f),0)
            @WRITE
            def writer(ctx,r,v):return result
            self.lib.revc_player_tick(C.byref(p),now,writer,None);self.assertEqual(p.state,4);self.assertEqual(p.index,0)
    @unittest.skipUnless(os.getenv('REVC_TEST_SONG'),'set REVC_TEST_SONG for private full-score test')
    def test_private_full_score_executes_every_original_register_in_order(self):
        data=Path(os.environ['REVC_TEST_SONG']).read_bytes()
        for service in (20,250,400):
            p,writes,elapsed,events=self.replay(data,service,13)
            self.assertEqual(p.state,2);self.assertEqual(p.index,len(events));self.assertEqual(writes,[(r,v) for t,r,v in events])
            print('FULL SCORE simulated service_us=%d events=%d max_late_us=%d period_us=%d'%(service,p.index,p.max_late_us,elapsed))

class SerializerTests(unittest.TestCase):
    def test_PIO_MSB_left_and_zero_right_with_one_bit_I2S_delay(self):
        # Interpret the actual PIO text,including side-set on every instruction.
        code=[];labels={}
        for raw in (ROOT/'pio/i2s_tx.pio').read_text().splitlines():
            line=raw.split(';')[0].strip()
            if not line or line.startswith('.'):continue
            if line.endswith(':'):labels[line.removeprefix('public ').rstrip(':')]=len(code)
            else:code.append(line)
        pc=labels['entry'];x=0;word=0x12340000;bits=0;pin=0;bclk=0;previous_ws=1;acc=[[],[]];decoded=[[],[]]
        for step in range(500):
            op,side=code[pc].rsplit(' side ',1);side=int(side,2);next_pc=(pc+1)%len(code)
            if op.startswith('set x'):x=int(op.split(',')[1])
            elif op.startswith('out pins'):
                pin=(word>>(31-bits))&1;bits=(bits+1)%32
            elif op.startswith('jmp x--'):
                if x:next_pc=labels[op.split()[-1]]
                x=(x-1)&0xffffffff
            else:self.fail(op)
            ws=side>>1;newclk=side&1
            if newclk and not bclk:
                c=previous_ws;acc[c].append(pin)
                if len(acc[c])==16:
                    decoded[c].append(sum(v<<(15-i) for i,v in enumerate(acc[c])));acc[c]=[]
                previous_ws=ws
            bclk=newclk;pc=next_pc
        self.assertTrue(all(v==0x1234 for v in decoded[0]),decoded)
        self.assertTrue(all(v==0 for v in decoded[1]),decoded)
        self.assertGreater(len(decoded[0]),3)

if __name__=='__main__':unittest.main()
