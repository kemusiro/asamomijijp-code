# SPDX-License-Identifier: MIT
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from protocol import packet, parse_status, crc8


class Protocol(unittest.TestCase):
    def test_crc_standard_vector(self):
        self.assertEqual(crc8(b'123456789'), 0xf4)

    def test_packet_big_endian_microseconds(self):
        p = packet(1, 0x28, 0xf0, 0x12345678)
        self.assertEqual(p[:7], bytes.fromhex('0128f012345678'))
        self.assertEqual(p[7], crc8(p[:7]))

    def test_status(self):
        p = bytes.fromhex('4a011f000101ff')
        s = parse_status(p + bytes((crc8(p),)))
        self.assertTrue(s['running'] and s['fault'] and s['audio_primed'])
        self.assertEqual((s['free_slots'], s['ack']), (257, 255))

    def test_corrupt_status(self):
        p = bytearray.fromhex('4a01000001000000');p[7] = crc8(p[:7]);p[3] ^= 1
        with self.assertRaises(ValueError): parse_status(p)
        with self.assertRaises(ValueError): parse_status(b'')

    def test_range(self):
        for fields in [(256, 0, 0, 0), (1, 256, 0, 0), (1, 0, -1, 0), (1, 0, 0, 0x100000000)]:
            with self.assertRaises(ValueError): packet(*fields)


if __name__ == '__main__': unittest.main()
