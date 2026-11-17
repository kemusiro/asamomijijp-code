# SPDX-License-Identifier: MIT
"""Descriptor structure and reproducible, locally generated ROM checks."""
import importlib.util
import os
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,HERE/'tools'/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class UsbMetadataTests(unittest.TestCase):
 def test_generated_descriptors_match_source(self):
  m=load('usb_descriptors');self.assertEqual((HERE/'rtl/revc_usb_descriptors.v').read_text(),m.render())
 def test_class_interface_endpoint_and_jack_links(self):
  c=load('usb_descriptors').descriptors()[0x200];self.assertEqual(len(c),int.from_bytes(c[2:4],'little'))
  p=0;items=[]
  while p<len(c):
   n=c[p];self.assertGreaterEqual(n,2);self.assertLessEqual(p+n,len(c));items.append(c[p:p+n]);p+=n
  interfaces=[x for x in items if x[1]==4];self.assertEqual([x[2] for x in interfaces],[0,1,2,3])
  self.assertEqual([tuple(x[5:8]) for x in interfaces],[(2,2,1),(10,0,0),(1,1,0),(1,3,0)])
  eps=[x for x in items if x[1]==5];self.assertEqual([(x[2],x[3],x[4]) for x in eps],[(0x81,3,8),(2,2,64),(0x82,2,64),(3,2,64),(0x83,2,64)])
  ms=items[items.index(interfaces[-1])+1:];header=ms[0]
  self.assertEqual(int.from_bytes(header[5:7],'little'),sum(len(x) for x in ms))
  ins=[x for x in ms if x[1:3]==bytes([0x24,2])];outs=[x for x in ms if x[1:3]==bytes([0x24,3])]
  self.assertEqual({x[4] for x in ins+outs},{1,2,3,4})
  self.assertEqual([(x[4],x[6]) for x in outs],[(3,2),(4,1)])
  self.assertEqual([x[4] for x in ms if x[1]==0x25],[1,3])
 def test_midi_rom_matches_accepted_c_source(self):
  self.assertEqual((HERE/'rtl/revc_midi_rom.v').read_text(),load('midi_rom').render(Path(os.environ['F1_PROJECT'])))
if __name__=='__main__':unittest.main()
