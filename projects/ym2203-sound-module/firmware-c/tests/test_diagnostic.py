# SPDX-License-Identifier: MIT
"""Actual bounded C recorder and independent binary parsing/PCM export tests."""
import ctypes as C
import importlib.util
import os
import zlib
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('analysis',ROOT/'tools/analyze_capture.py');analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)
class DiagnosticTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='revc-diag-');p=Path(cls.temp.name)/'diag.so'
  subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',str(ROOT/'src/diagnostic.c'),str(ROOT/'src/wym1.c'),'-o',str(p)],check=True)
  cls.lib=C.CDLL(str(p));cls.lib.revc_diag_arm.argtypes=[C.c_uint64,C.c_uint,C.c_uint,C.c_bool,C.c_uint32,C.c_uint32];cls.lib.revc_diag_arm.restype=C.c_bool
  cls.lib.revc_diag_rx_frames.argtypes=[C.POINTER(C.c_uint32),C.c_uint,C.c_uint64]
  cls.lib.revc_diag_rx.argtypes=[C.POINTER(C.c_uint32),C.c_uint64];cls.lib.revc_diag_trace.argtypes=[C.c_uint64,C.c_uint8,C.c_uint8]
  cls.lib.revc_convert_gain.argtypes=[C.POINTER(C.c_uint32),C.POINTER(C.c_uint32),C.POINTER(C.c_uint32),C.c_uint,C.c_uint]
  cls.lib.revc_diag_data.restype=C.c_void_p;cls.lib.revc_diag_seal.restype=C.c_bool
  cls.lib.revc_parse_capture.argtypes=[C.c_char_p,C.POINTER(C.c_uint)];cls.lib.revc_parse_capture.restype=C.c_bool
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def setUp(self):self.lib.revc_diag_reset();self.origin=(1<<32)+12345
 def source(self):return (C.c_uint32*625)(*[(((0x600+i%128)<<11)|(i&2047))<<8|0xa5 for i in range(625)])
 def arm(self):self.assertTrue(self.lib.revc_diag_arm(self.origin,31,12,True,0x12345678,123137))
 def fill(self):
  source=self.source()
  for i in range(178):self.lib.revc_diag_rx(source,self.origin+31011250+i*11250)
 def blob(self):return C.string_at(self.lib.revc_diag_data(),analysis.SIZE)
 def test_strict_command_and_arm_validation_preserve_result_on_error(self):
  for second in range(30,34):
   value=C.c_uint(99);self.assertTrue(self.lib.revc_parse_capture(('capture %d'%second).encode(),C.byref(value)));self.assertEqual(value.value,second)
  for s in (b'capture',b'capture 29',b'capture 34',b'capture 031',b'capture 31 ',b'capture 31x',b'capture -1'):
   value=C.c_uint(99);self.assertFalse(self.lib.revc_parse_capture(s,C.byref(value)));self.assertEqual(value.value,99)
  for second,gain in ((29,12),(34,12),(31,17)):
   self.assertFalse(self.lib.revc_diag_arm(self.origin,second,gain,True,0,10));self.assertEqual(self.lib.revc_diag_state(),0)
 def test_raw_bit_order_trace_layout_and_sealed_ownership_after_32bit_time_wrap(self):
  self.arm();self.assertFalse(self.lib.revc_diag_data());self.assertFalse(self.lib.revc_diag_seal())
  self.lib.revc_diag_trace(self.origin-1,1,2);self.lib.revc_diag_trace(self.origin+100,0xa4,0x22);self.lib.revc_diag_trace(self.origin+200,0xa0,0x44)
  self.lib.revc_diag_rx(self.source(),self.origin+31011249);self.assertEqual(self.lib.revc_diag_state(),1)
  self.fill();self.assertEqual(self.lib.revc_diag_state(),2);self.assertFalse(self.lib.revc_diag_data())
  self.assertTrue(self.lib.revc_diag_seal());before=self.blob();h,trace,words=analysis.parse(before)
  self.assertEqual(trace,[(100,0xa4,0x22),(200,0xa0,0x44)]);self.assertEqual(h[15],12);self.assertEqual(h[17],0x12345678)
  expected=[((0x600+i%128)<<11)|(i&2047) for i in range(625)]
  self.assertEqual(words,expected*178)
  self.lib.revc_diag_rx(self.source(),self.origin+90000000);self.lib.revc_diag_trace(self.origin+90000000,1,2);self.lib.revc_diag_abort()
  self.assertEqual(self.lib.revc_diag_state(),3);self.assertEqual(self.blob(),before)
  samples,exponents,unused,noncanonical=analysis.decode(words)
  self.assertEqual(samples,[i%128 for i in range(625)]*178);self.assertEqual(noncanonical,0);self.assertEqual(exponents,{1:111250})
  pcm,clipped=analysis.pcm(samples,12);self.assertEqual(len(pcm),178*540);self.assertEqual(clipped,0)
  out=(C.c_uint32*540)();peak=C.c_uint32()
  self.assertEqual(self.lib.revc_convert_gain(self.source(),out,C.byref(peak),12,12),0)
  self.assertEqual([C.c_int16(word>>16).value for word in out],pcm[:540])
 def test_abort_never_exports_partial_data_and_reset_can_start_fresh(self):
  self.arm();self.lib.revc_diag_rx(self.source(),self.origin+31011250);self.lib.revc_diag_abort();self.fill()
  self.assertEqual(self.lib.revc_diag_state(),0);self.assertFalse(self.lib.revc_diag_seal());self.assertFalse(self.lib.revc_diag_data())
  self.lib.revc_diag_reset();self.arm();self.lib.revc_diag_trace(self.origin,0,0);self.fill();self.assertTrue(self.lib.revc_diag_seal());analysis.parse(self.blob())
 def test_trace_overflow_is_flagged_and_does_not_overwrite_raw_region(self):
  self.arm()
  for i in range(16385):self.lib.revc_diag_trace(self.origin+i,0x40,0x55)
  self.fill();self.assertTrue(self.lib.revc_diag_seal());data=self.blob()
  self.assertEqual(struct.unpack_from('<I',data,32)[0],16384);self.assertEqual(struct.unpack_from('<I',data,80)[0],1)
  self.assertEqual(data[analysis.RAW_OFFSET:analysis.RAW_OFFSET+3],((0x600<<11)).to_bytes(3,'little'))
  with self.assertRaises(ValueError):analysis.parse(data)
 def test_parser_rejects_bad_sizes_counts_offsets_times_and_invalid_exp(self):
  self.arm();self.lib.revc_diag_trace(self.origin,0,0);self.fill();self.lib.revc_diag_seal();data=self.blob()
  for bad in (data[:-1],b'NOPE'+data[4:],data+b'\0'):
   with self.assertRaises(ValueError):analysis.parse(bad)
  for offset,value in ((28,0),(32,16385),(40,0),(64,17),(80,1),(56,0),(60,0)):
   bad=bytearray(data);struct.pack_into('<I',bad,offset,value)
   with self.assertRaises(ValueError):analysis.parse(bad)
  with self.assertRaises(ValueError):analysis.decode([0])

 @unittest.skipUnless(os.getenv('REVC_TEST_SONG'),'private full-score prefix test')
 def test_real_song_trace_capacity_and_offline_export_use_identical_prefix(self):
  from test_core import File,Player,WRITE
  self.lib.wym1_open.argtypes=[C.POINTER(File),C.c_void_p,C.c_size_t]
  self.lib.revc_player_start.argtypes=[C.POINTER(Player),C.POINTER(File),C.c_uint64]
  self.lib.revc_player_tick.argtypes=[C.POINTER(Player),C.c_uint64,WRITE,C.c_void_p]
  song_path=Path(os.environ['REVC_TEST_SONG']);song=song_path.read_bytes();buffer=C.create_string_buffer(song);file=File()
  self.assertEqual(self.lib.wym1_open(C.byref(file),buffer,len(song)),0)
  events=list(struct.iter_unpack('<IBB',song[16:]));player=Player();self.lib.revc_player_start(C.byref(player),C.byref(file),self.origin)
  self.assertTrue(self.lib.revc_diag_arm(self.origin,31,12,True,zlib.crc32(song),file.count))
  now=self.origin;rx_due=self.origin+11250;source=self.source()
  @WRITE
  def write(ctx,reg,val):self.lib.revc_diag_trace(now+250,reg,val);return 1
  while self.lib.revc_diag_state()==1:
   due=self.origin+events[player.index][0]*1000
   now=max(now,min(rx_due,due))
   if rx_due<=now:
    self.lib.revc_diag_rx(source,now);rx_due+=11250
   else:
    self.lib.revc_player_tick(C.byref(player),now,write,None);now+=250
  self.assertTrue(self.lib.revc_diag_seal());data=self.blob();h,trace,words=analysis.parse(data)
  self.assertEqual([(r,v) for t,r,v in trace],[(r,v) for t,r,v in events[:len(trace)]])
  self.assertLess(len(trace),16384)
  with tempfile.TemporaryDirectory(prefix='revc-export-') as tmp:
   tmp=Path(tmp);capture=tmp/'test.rcd';capture.write_bytes(data)
   run=subprocess.run([os.sys.executable,str(ROOT/'tools/analyze_capture.py'),str(capture),'--out',str(tmp/'out'),'--song',str(song_path.resolve())],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr)
   self.assertTrue((tmp/'out/fm-wire.wav').is_file());self.assertTrue((tmp/'out/fm-pcm.wav').is_file())
  print('CAPTURE synthetic timing/raw model:prefix events=%d,frames=%d;real WYM1 order and standalone export verified'%(len(trace),len(words)))

 def test_125_frame_fragments_preserve_RCD1_logical_groups_and_offline_PCM(self):
  self.arm();self.lib.revc_diag_trace(self.origin,0,0)
  for i in range(890):
   words=[(((0x600+(i*125+j)%128)<<11)|((i*125+j)&2047))<<8 for j in range(125)]
   src=(C.c_uint32*125)(*words)
   self.lib.revc_diag_rx_frames(src,125,self.origin+31002250+i*2250)
  self.assertEqual(self.lib.revc_diag_state(),2);self.assertTrue(self.lib.revc_diag_seal())
  h,trace,words=analysis.parse(self.blob());self.assertEqual(h[13],31011250);self.assertEqual(h[14],33002500)
  self.assertEqual(words,[((0x600+i%128)<<11)|(i&2047) for i in range(111250)])
 def test_capture_rejects_inconsistent_fragment_sizes(self):
  self.arm();src=(C.c_uint32*125)(*([0x600<<19]*125))
  self.lib.revc_diag_rx_frames(src,125,self.origin+31002250)
  self.lib.revc_diag_rx(self.source(),self.origin+31013500)
  self.assertEqual(self.lib.revc_diag_state(),0);self.assertFalse(self.lib.revc_diag_data())
