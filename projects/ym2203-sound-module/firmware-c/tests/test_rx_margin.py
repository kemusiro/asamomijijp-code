# SPDX-License-Identifier: MIT
"""Input-settling model and actual C failure snapshot,not an electrical capture."""
import ctypes as C
from pathlib import Path
import random
import re
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Bad(C.Structure):_fields_=[(n,C.c_uint32) for n in ['index','word','before','after']]
class ReceiverTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();lib=Path(cls.temp.name)/'core.so'
  subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'src/wym1.c'),'-o',str(lib)],check=True)
  cls.lib=C.CDLL(str(lib));cls.lib.revc_find_bad_frame.argtypes=[C.POINTER(C.c_uint32),C.c_uint,C.POINTER(Bad)];cls.lib.revc_find_bad_frame.restype=C.c_bool
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_invalid_exponent_snapshot_first_middle_last_and_valid_does_not_write(self):
  valid=[((1+i%7)<<29)|(i<<19) for i in range(125)]
  for i in [0,1,62,123,124]:
   words=valid.copy();words[i]=0x00123400
   if i<124:words[i+1]=0
   out=Bad();self.assertTrue(self.lib.revc_find_bad_frame((C.c_uint32*125)(*words),125,C.byref(out)))
   self.assertEqual((out.index,out.word,out.before,out.after),(i,words[i],words[i-1] if i else 0,words[i+1] if i<124 else 0))
  out=Bad(1,2,3,4);before=bytes(out)
  self.assertFalse(self.lib.revc_find_bad_frame((C.c_uint32*125)(*valid),125,C.byref(out)));self.assertEqual(bytes(out),before)
 def test_recording_snapshot_does_not_suppress_conversion_fault(self):
  self.lib.revc_convert_stream.argtypes=[C.POINTER(C.c_uint32)]*3+[C.c_uint,C.c_uint,C.POINTER(C.c_uint32)]
  words=[0x600<<19]*125;words[62]=0
  out=(C.c_uint32*108)();peak=C.c_uint32();clipped=C.c_uint32()
  flags=self.lib.revc_convert_stream((C.c_uint32*125)(*words),out,C.byref(peak),1024,1024,C.byref(clipped))
  self.assertEqual(flags,1);self.assertEqual(clipped.value,0)
 def test_qualified_receiver_retains_24bit_order_across_skew_and_phase(self):
  from rx_model import fixture,receive
  pio=(ROOT/'pio/fm_rx.pio').read_text();rng=random.Random(220307)
  self.assertIn('sm_config_set_jmp_pin(&in,PIN_FM_CLK)',(ROOT/'src/audio.c').read_text())
  for phase in range(24):
   for skew in range(4):
    words=[rng.randrange(1<<24) for _ in range(3)]
    frames,_=receive(pio,*fixture(words,phase=phase,skew=skew))
    self.assertEqual(frames,[w<<8 for w in words[:2]])
 def test_short_clock_excursion_reproduces_user_word_only_in_alpha6(self):
  from rx_model import fixture,receive
  old='wait 1 gpio 18\nwait 0 gpio 18\nset x, 23\nbits:\nwait 0 gpio 17\nwait 1 gpio 17 [4]\nin pins, 1\njmp x-- bits\n'
  args=fixture([0x87eb00,0xbbaa00,0xaaff00],glitches=[(32,34,1)])
  legacy,_=receive(old,*args);fixed,_=receive((ROOT/'pio/fm_rx.pio').read_text(),*args)
  self.assertEqual(legacy[0],0x0fd60000)  # exact user-reported invalid word
  self.assertEqual(fixed[0],0x87eb0000)  # synthetic source,not measured board data
  self.assertEqual(legacy[1],fixed[1])
 def test_high_and_low_glitches_across_every_bit_phase_do_not_insert_or_drop_words(self):
  from rx_model import fixture,receive
  pio=(ROOT/'pio/fm_rx.pio').read_text();words=[0x87eb00,0xbbaa00,0xaaff00]
  for start in range(29,1180):
   for width in [1,2]:
    original=int((start-40)%24<12)
    frames,_=receive(pio,*fixture(words,glitches=[(start,start+width,1-original)]))
    self.assertEqual(frames,[w<<8 for w in words[:2]],(start,width))
 def test_persistent_invalid_word_still_triggers_conversion_error(self):
  from rx_model import fixture,receive
  frames,_=receive((ROOT/'pio/fm_rx.pio').read_text(),*fixture([0x0fd600,0x87eb00,0xbbaa00]))
  self.assertEqual(frames[0],0x0fd60000)
  self.assertEqual(frames[0]>>29,0)
