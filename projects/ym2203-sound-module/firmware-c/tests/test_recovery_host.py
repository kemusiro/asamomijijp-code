# SPDX-License-Identifier: MIT
"""Physical recovery HOST script against real C core with modelled I2C/time."""
import binascii
import contextlib
import ctypes as C
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock
import test_stream as core

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class RecoveryHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core.StreamTests.setUpClass.__func__(cls)
        with mock.patch.dict(sys.modules, {'ym2203_revc_stream': cls.host}):
            cls.runner = module('recovery_check', ROOT / 'host/recovery_check.py')
        cls.assets = module('recovery_assets', ROOT / 'tools/embed_song.py')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_script(self, corrupt_lease=False, bad_audio=False, bad_score=False,
                   clock_origin=0):
        c = self.c
        c.model_init(50)
        c.model_clock(clock_origin)
        bus_events = []

        class Clock:
            @staticmethod
            def ticks_ms():
                return (c.model_now() // 1000) & ((1 << 30) - 1)

            @staticmethod
            def ticks_diff(a, b):
                return ((a - b + (1 << 29)) & ((1 << 30) - 1)) - (1 << 29)

            @staticmethod
            def sleep_ms(ms):
                c.model_advance(ms * 1000)

        class Bus:
            active = True

            def writeto(self, address, packet):
                assert self.active and address == 0x42
                bus_events.append(('write', c.model_now(), packet[3]))
                c.model_advance((len(packet) + 1) * 90)
                c.model_command(bytes(packet), len(packet))
                return len(packet)

            def readfrom(self, address, count):
                assert self.active and address == 0x42 and count == 64
                out = C.create_string_buffer(64)
                c.model_status(out)
                data = bytearray(out.raw)
                if corrupt_lease and data[9] == 5:
                    struct.pack_into('<H', data, 44, 9)  # UNDERRUN is not LEASE.
                if bad_audio:
                    data[11] &= ~2
                struct.pack_into('<I', data, 60, binascii.crc32(data[:60]) & 0xffffffff)
                bus_events.append(('read', c.model_now(), data[9]))
                c.model_advance((count + 1) * 90)
                return data

        def bind():
            bus_events.append(('bind', c.model_now(), c.model_trace_count()))
            return Bus()

        def release(bus):
            assert bus.active
            bus.active = False
            bus_events.append(('release', c.model_now(), c.model_trace_count()))

        score = self.assets.demo()
        if bad_score:
            score = score[:-1] + bytes([score[-1] ^ 1])
        path = Path(self.temp.name) / 'recovery.bin'
        path.write_bytes(score)
        output = io.StringIO()
        self.bus_events = bus_events
        self.output = output
        with mock.patch.object(self.host, 'time', Clock), \
             mock.patch.object(self.runner, 'time', Clock), \
             contextlib.redirect_stdout(output):
            return self.runner.run_check(bind, release, str(path))

    def test_all_four_sections_against_real_C_scheduler(self):
        results = self.run_script()
        self.assertEqual([s['state'] for s in results], [4, 3, 5, 3])
        self.assertEqual([s['error'] for s in results], [0, 0, 8, 0])
        self.assertEqual([s['executed'] for s in results], [185, 191, 185, 191])
        events = list(struct.iter_unpack('<IBB', self.assets.demo()[16:]))
        pair_bytes = lambda entries: bytes(v for _, r, value in entries for v in (r, value))
        expected = pair_bytes(events[:185]) + pair_bytes(events) + pair_bytes(events[:185]) + pair_bytes(events)
        actual = C.string_at(self.c.model_trace(), 2 * self.c.model_trace_count())
        self.assertEqual(actual, expected)  # Quiet intervals did not execute tails.
        unbind = next(i for i, entry in enumerate(self.bus_events) if entry[0] == 'release')
        self.assertEqual(self.bus_events[unbind + 1][0], 'bind')
        self.assertEqual(self.bus_events[unbind + 1][1] - self.bus_events[unbind][1], 1800000)
        self.assertEqual(self.bus_events[unbind + 1][2], self.bus_events[unbind][2])
        self.assertIn('HOST PASS', self.output.getvalue())
        self.assertEqual(self.bus_events[-1][0], 'release')

    def test_underrun_cannot_be_mistaken_for_successful_lease_stop(self):
        with self.assertRaisesRegex(self.host.ProtocolError, 'wrong STOP/lease state'):
            self.run_script(corrupt_lease=True)
        self.assertNotIn('HOST PASS', self.output.getvalue())
        self.assertEqual(self.bus_events[-1][0], 'release')

    def test_audio_fault_aborts_before_PLAY_and_releases_host(self):
        with self.assertRaisesRegex(self.host.ProtocolError, 'target audio is not healthy'):
            self.run_script(bad_audio=True)
        self.assertFalse(any(e[0] == 'write' and e[2] == 4 for e in self.bus_events))
        self.assertEqual(self.bus_events[-1][0], 'release')

    def test_wrong_score_is_rejected_before_binding_or_writing(self):
        with self.assertRaisesRegex(self.host.ProtocolError, 'wrong score CRC'):
            self.run_script(bad_score=True)
        self.assertEqual(self.bus_events, [])

    def test_host_clock_wrap_during_overall_check(self):
        self.run_script(clock_origin=((1 << 30) - 20000) * 1000)
        self.assertIn('HOST PASS', self.output.getvalue())
