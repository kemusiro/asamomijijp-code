# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('uf2',ROOT/'tools/verify_uf2.py');uf2=importlib.util.module_from_spec(spec);spec.loader.exec_module(uf2)

def block(flags,address,index,total,family,payload):
    return struct.pack('<8I',0x0a324655,0x9e5d5157,flags,address,256,index,total,family)+payload+b'\0'*(476-len(payload))+struct.pack('<I',0x0ab16f30)

class UF2Tests(unittest.TestCase):
    def image(self):
        prefix=block(0xa000,0x10ffff00,0,2,0xe48bff57,b'\xef'*256+struct.pack('<I',0x9957e304))
        program=block(0x2000,0x10000000,0,1,0xe48bff59,b'x'*256)
        return prefix+program
    def test_official_E10_prefix_is_not_an_out_of_bounds_program_write(self):
        memory=uf2.flash_image(self.image());self.assertEqual(memory[:256],b'x'*256);self.assertEqual(memory[256:512],b'\xff'*256)
    def test_bad_family_prefix_order_bounds_and_truncation_are_rejected(self):
        data=self.image()
        for offset,value in ((0,0),(288,0),(512+8,0),(512+12,0x10400000),(512+20,1),(512+24,2),(512+28,0xe48bff56)):
            bad=bytearray(data);struct.pack_into('<I',bad,offset,value)
            with self.assertRaises(ValueError):uf2.flash_image(bad)
        with self.assertRaises(ValueError):uf2.flash_image(data[:-1])
if __name__=='__main__':unittest.main()
