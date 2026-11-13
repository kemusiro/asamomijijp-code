# SPDX-License-Identifier: MIT
"""Short-DMA conversion equivalence and publication/consumption invariants."""
import ctypes as C
import heapq
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Cursor(C.Structure):_fields_=[('consumed',C.c_uint32),('pending',C.c_bool)]
class Ramp(C.Structure):_fields_=[('current',C.c_uint32),('start',C.c_uint32),('target',C.c_uint32),('step',C.c_uint32)]
class LowLatencyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='revc-short-');lib=Path(cls.temp.name)/'core.so'
  subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'src/wym1.c'),'-o',str(lib)],check=True)
  cls.lib=C.CDLL(str(lib));args=[C.POINTER(C.c_uint32)]*3+[C.c_uint,C.c_uint,C.POINTER(C.c_uint32)]
  cls.lib.revc_convert_stream.argtypes=args;cls.lib.revc_convert_gain_ex.argtypes=args
  cls.lib.revc_tx_slot.argtypes=[C.POINTER(Cursor),C.c_uint32];cls.lib.revc_tx_slot.restype=C.c_int
  cls.lib.revc_gain_step.argtypes=[C.POINTER(Ramp),C.c_uint,C.POINTER(C.c_uint),C.POINTER(C.c_uint)];cls.lib.revc_gain_step.restype=C.c_bool
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_five_short_blocks_equal_one_old_block_at_every_supported_constant_gain(self):
  rng=random.Random(220305)
  for case in range(20):
   words=[((rng.randrange(1,8)<<10)|rng.randrange(1024))<<19 for i in range(625)]
   src=(C.c_uint32*625)(*words)
   for gain in range(17):
    old=(C.c_uint32*540)();oldpeak=C.c_uint32();oldclip=C.c_uint32()
    oldflags=self.lib.revc_convert_gain_ex(src,old,C.byref(oldpeak),gain,gain,C.byref(oldclip))
    combined=[];peaks=[];clips=0;flags=0
    for b in range(5):
     small=(C.c_uint32*125)(*words[b*125:(b+1)*125]);out=(C.c_uint32*108)();peak=C.c_uint32();clip=C.c_uint32()
     flags|=self.lib.revc_convert_stream(small,out,C.byref(peak),gain*128,gain*128,C.byref(clip));peaks.append(peak.value);clips+=clip.value;combined+=list(out)
    self.assertEqual(combined,list(old));self.assertEqual(max(peaks),oldpeak.value);self.assertEqual(clips,oldclip.value);self.assertEqual(flags,oldflags)
 def test_invalid_short_gain_zeros_only_108_outputs(self):
  src=(C.c_uint32*125)(*([0x600<<19]*125));out=(C.c_uint32*113)(*([0xdeadbeef]*113));peak=C.c_uint32(99);clip=C.c_uint32(99)
  self.assertEqual(self.lib.revc_convert_stream(src,out,C.byref(peak),2049,0,C.byref(clip)),4)
  self.assertEqual(list(out)[:108],[0]*108);self.assertEqual(list(out)[108:],[0xdeadbeef]*5);self.assertEqual(peak.value,0);self.assertEqual(clip.value,0)
 def test_gain_ramp_stays_continuous_for_five_blocks_and_retargets_without_step(self):
  r=Ramp(1024,1024,1024,5);start=C.c_uint();end=C.c_uint();last=1024
  for target in (16,0,12):
   for i in range(5):
    self.assertTrue(self.lib.revc_gain_step(C.byref(r),target,C.byref(start),C.byref(end)))
    self.assertEqual(start.value,last);self.assertTrue(0<=end.value<=2048);last=end.value
   self.assertEqual(last,target*128)
  self.lib.revc_gain_step(C.byref(r),0,C.byref(start),C.byref(end));last=end.value
  self.lib.revc_gain_step(C.byref(r),16,C.byref(start),C.byref(end));self.assertEqual(start.value,last)
  before=bytes(r);self.assertFalse(self.lib.revc_gain_step(C.byref(r),17,C.byref(start),C.byref(end)));self.assertEqual(bytes(r),before)
 def test_consumer_waits_once_then_only_returns_a_published_next_slot(self):
  c=Cursor()
  for i in range(10):self.assertEqual(self.lib.revc_tx_slot(C.byref(c),2),-1);self.assertEqual(c.consumed,1)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(c),3),2);self.assertFalse(c.pending)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(c),3),-1);self.assertEqual(c.consumed,2)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(c),4),3)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(Cursor()),0),-2)
 def test_ring_slots_and_consumption_cross_uint32_wrap(self):
  c=Cursor(0xfffffffe,False)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(c),0),-1);self.assertEqual(c.consumed,0xffffffff)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(c),1),0);self.assertEqual(c.consumed,0xffffffff)
  self.assertEqual(self.lib.revc_tx_slot(C.byref(c),2),1);self.assertEqual(c.consumed,0)
 def test_short_pipeline_keeps_order_with_RX_completion_jitter_and_ring_wraps(self):
  # Separate RX publications from TX completions. DMA partner may already be
  # transmitting while a completed channel waits for the next conversion.
  rng=random.Random(2040);count=10000;period=2250;start=4600;fifo_lead=8*1000000/48000
  events=[]
  for block in range(2,count+2):heapq.heappush(events,((block+1)*period+rng.randint(20,650),'rx',block))
  for block in range(count):heapq.heappush(events,(start+(block+1)*period-fifo_lead,'tx',block))
  c=Cursor();produced=2;ring=[0,1]+[None]*6;armed=[0,1];ti=0;outputs=[];waits=0
  def service():
   nonlocal ti,waits
   slot=self.lib.revc_tx_slot(C.byref(c),produced)
   if slot==-1:waits+=1;return
   self.assertGreaterEqual(slot,0);self.assertEqual(ring[slot],c.consumed+1)
   armed[ti]=ring[slot];ti^=1
  for time,typ,block in sorted(events):
   if typ=='rx':
    self.assertEqual(block,produced);self.assertLess(produced-c.consumed,8)
    ring[produced&7]=produced;produced+=1
    if c.pending:service()
   else:
    self.assertFalse(c.pending,'missed deadline before partner completion')
    self.assertEqual(armed[block&1],block);outputs.append(block);service()
  self.assertEqual(outputs,list(range(count)));self.assertGreater(waits,100)
