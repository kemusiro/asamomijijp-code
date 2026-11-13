# SPDX-License-Identifier: MIT
"""HOST completion checks against real C stream core, not a physical USB test."""
import binascii
import contextlib
import ctypes as C
import io
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock
from test_recovery_host import module
import test_stream as core

ROOT = Path(__file__).resolve().parents[1]


class UsbDisconnectHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core.StreamTests.setUpClass.__func__(cls)
        with mock.patch.dict(sys.modules, {'ym2203_revc_stream': cls.host}):
            cls.runner = module('usb_disconnect_check', ROOT / 'host/usb_disconnect_check.py')
        cls.assets = module('usb_check_assets', ROOT / 'tools/embed_song.py')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_script(self, fail_after_play=False, bad_score=False, finish_during_keep=False,
                   bad_completion=None):
        c = self.c
        c.model_init(50)
        events = []
        race = []
        class Clock:
            @staticmethod
            def ticks_ms():
                return c.model_now() // 1000
            @staticmethod
            def ticks_diff(a, b):
                return a - b
            @staticmethod
            def sleep_ms(ms):
                c.model_advance(ms * 1000)

        class Bus:
            def writeto(self, address, packet):
                events.append(('write', c.model_now(), packet[3]))
                if finish_during_keep and packet[3] == 5 and not race:
                    prior = C.create_string_buffer(64)
                    c.model_status(prior)
                    period = struct.unpack_from('<I', prior.raw, 32)[0]
                    elapsed = struct.unpack_from('<I', prior.raw, 40)[0]
                    if prior.raw[9] == 2 and prior.raw[11] & 8 and elapsed >= period - 250:
                        # The last RUNNING response becomes stale before KEEP arrives.
                        c.model_advance((period - elapsed + 1) * 1000)
                        race.append(struct.unpack_from('<I', packet, 4)[0])
                c.model_advance((len(packet) + 1) * 90)
                c.model_command(bytes(packet), len(packet))
                return len(packet)
            def readfrom(self, address, count):
                out = C.create_string_buffer(64)
                c.model_status(out)
                data = bytearray(out.raw)
                if bad_completion is not None and race and data[9:11] == b'\x03\x04':
                    offset, fmt, value = bad_completion
                    struct.pack_into(fmt, data, offset, value)
                    struct.pack_into('<I', data, 60, binascii.crc32(data[:60]) & 0xffffffff)
                if fail_after_play and data[9] == 3:
                    data[11] &= ~2
                    struct.pack_into('<I', data, 60, binascii.crc32(data[:60]) & 0xffffffff)
                c.model_advance((count + 1) * 90)
                return data

        def bind():
            events.append(('bind', c.model_now(), 0))
            return Bus()
        def release(bus):
            events.append(('release', c.model_now(), 0))

        data = self.assets.demo()
        if bad_score:
            data = data[:-1]
        path = Path(self.temp.name) / 'recovery.bin'
        path.write_bytes(data)
        self.events = events
        self.race = race
        self.output = io.StringIO()
        with mock.patch.object(self.host, 'time', Clock), mock.patch.object(self.runner, 'time', Clock), contextlib.redirect_stdout(self.output):
            return self.runner.run_check(bind, release, str(path))

    def test_exact_score_completion_quiet_interval_and_release(self):
        result = self.run_script()
        self.assertEqual((result['state'], result['error'], result['executed'], result['queued']), (4, 0, 191, 0))
        expected = bytes(x for _, reg, value in struct.iter_unpack('<IBB', self.assets.demo()[16:]) for x in (reg, value))
        actual = C.string_at(self.c.model_trace(), 2 * self.c.model_trace_count())
        self.assertEqual(actual, expected)
        play = next(e for e in self.events if e[0] == 'write' and e[2] == 4)
        final_stop = [e for e in self.events if e[0] == 'write' and e[2] == 1][-1]
        self.assertGreaterEqual(final_stop[1] - play[1], 17250000)
        self.assertEqual(self.events[-1][0], 'release')
        self.assertIn('HOST PASS', self.output.getvalue())

    def test_audio_failure_after_play_stops_releases_and_never_passes(self):
        with self.assertRaisesRegex(self.host.ProtocolError, 'Incomplete final state'):
            self.run_script(fail_after_play=True)
        self.assertNotIn('HOST PASS', self.output.getvalue())
        self.assertEqual(self.events[-1][0], 'release')
        self.assertEqual([e for e in self.events if e[0] == 'write'][-1][2], 1)

    def test_wrong_score_rejected_before_binding(self):
        with self.assertRaisesRegex(ValueError, 'original 191-event'):
            self.run_script(bad_score=True)
        self.assertEqual(self.events, [])

    def test_final_KEEP_rejected_in_DONE_still_completes_without_replaying(self):
        result = self.run_script(finish_during_keep=True)
        self.assertEqual(len(self.race), 1)
        self.assertEqual((result['state'], result['error'], result['executed']), (4, 0, 191))
        # Rejected KEEP does not consume its sequence; final STOP uses that sequence.
        self.assertEqual(result['ack'], self.race[0])
        self.assertEqual(self.c.model_trace_count(), 191)
        self.assertIn('HOST PASS', self.output.getvalue())
        self.assertEqual(self.events[-1][0], 'release')

    def test_final_KEEP_cannot_hide_wrong_score_or_fault_or_incomplete_state(self):
        for field in [(9, '<B', 4), (10, '<B', 3), (11, '<B', 9), (11, '<B', 3),
                      (11, '<B', 27), (16, '<I', 999), (20, '<I', 190),
                      (24, '<I', 190), (28, '<I', 190), (32, '<I', 12999),
                      (36, '<H', 1), (40, '<I', 0), (44, '<H', 8), (52, '<I', 0)]:
            with self.subTest(field=field):
                with self.assertRaises(self.host.ProtocolError):
                    self.run_script(finish_during_keep=True, bad_completion=field)
                self.assertEqual(len(self.race), 1)
                self.assertNotIn('HOST PASS', self.output.getvalue())
                self.assertEqual(self.events[-1][0], 'release')
                self.assertEqual([e for e in self.events if e[0] == 'write'][-1][2], 1)
