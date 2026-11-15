# SPDX-License-Identifier: MIT
"""Catalogue/menu tests and actual playlists against the real C stream core."""
import binascii
import contextlib
import ctypes as C
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock
from test_recovery_host import module
import test_stream as core

ROOT = Path(__file__).resolve().parents[1]


class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core.StreamTests.setUpClass.__func__(cls)
        with mock.patch.dict(sys.modules, {'ym2203_revc_stream': cls.host}):
            cls.player = module('playlist_test', ROOT / 'host/lib/ym2203_revc_player.py')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.c.model_init(50)
        self.folder = tempfile.TemporaryDirectory(prefix='revc-music-')
        self.addCleanup(self.folder.cleanup)
        self.music = Path(self.folder.name)
        self.a = core.score(4)
        self.b = core.score(5)
        (self.music / 'A.bin').write_bytes(self.a)
        (self.music / 'B.bin').write_bytes(self.b)
        self.messages = []

    def scan(self):
        def entries(directory):
            return ((p.name, 0x4000 if p.is_dir() else 0x8000, 0) for p in Path(directory).iterdir())
        with mock.patch.object(self.player.os, 'ilistdir', entries, create=True):
            return self.player.scan_tracks(str(self.music))

    def run_tracks(self, *, repeat=False, stop_at=None, fail_at=None, paths=None):
        c = self.c
        owner = self
        class Clock:
            @staticmethod
            def ticks_ms():
                return (c.model_now() // 1000) & ((1 << 30) - 1)
            @staticmethod
            def ticks_diff(a, b):
                return ((a - b + (1 << 29)) & ((1 << 30) - 1)) - (1 << 29)
            @staticmethod
            def sleep_ms(ms):
                if stop_at and c.model_trace_count() >= stop_at:
                    raise KeyboardInterrupt()
                c.model_advance(ms * 1000)
        class Bus:
            failed = False
            def writeto(self, address, packet):
                owner.commands.append(packet[3])
                c.model_advance((len(packet) + 1) * 90)
                c.model_command(bytes(packet), len(packet))
                return len(packet)
            def readfrom(self, address, size):
                if fail_at and not self.failed and c.model_trace_count() >= fail_at:
                    self.failed = True
                    raise OSError('injected I2C failure')
                out = C.create_string_buffer(64)
                c.model_status(out)
                c.model_advance((size + 1) * 90)
                return out.raw
        self.commands = []
        stream = self.host.RevCStream(Bus())
        tracks = self.scan()[0]
        if paths is not None:
            tracks = [item for item in tracks if item['name'] in paths]
        with mock.patch.object(self.host, 'time', Clock), mock.patch.object(self.player, 'time', Clock):
            self.summary = self.player.run_playlist(stream, tracks, repeat=repeat, gap_ms=100,
                                                     write=self.messages.append)

    def trace(self):
        return C.string_at(self.c.model_trace(), 2 * self.c.model_trace_count())

    def assert_stopped(self):
        out = C.create_string_buffer(64)
        self.c.model_status(out)
        self.assertEqual(out.raw[9], 4)
        self.assertEqual(struct.unpack_from('<H', out.raw, 36)[0], 0)
        before = self.trace()
        self.c.model_advance(4000000)
        self.assertEqual(self.trace(), before)

    def test_catalogue_sorts_valid_files_and_rejects_wrong_clock_and_length(self):
        (self.music / 'Z.BIN').write_bytes(self.a)
        (self.music / 'truncated.bin').write_bytes(self.a[:-1])
        data = bytearray(self.a)
        struct.pack_into('<I', data, 12, 8000000)
        (self.music / 'wrong-clock.bin').write_bytes(data)
        (self.music / 'not-wym.bin').write_bytes(b'junk')
        (self.music / 'folder.bin').mkdir()
        (self.music / '.hidden.bin').write_bytes(self.a)
        tracks, rejected = self.scan()
        self.assertEqual([t['name'] for t in tracks], ['A.bin', 'B.bin', 'Z.BIN'])
        self.assertEqual([name for name, _ in rejected], ['not-wym.bin', 'truncated.bin', 'wrong-clock.bin'])

    def test_catalogue_limit_fails_without_silently_selecting_arbitrary_files(self):
        for i in range(63):
            (self.music / ('track%02d.bin' % i)).write_bytes(self.a)
        with self.assertRaisesRegex(ValueError, 'At most64'):
            self.scan()

    def test_selection_and_empty_catalogue_are_explicit(self):
        tracks, _ = self.scan()
        self.assertEqual(self.player.parse_selection('2', tracks), ([tracks[1]], False))
        self.assertEqual(self.player.parse_selection('R 1', tracks), ([tracks[0]], True))
        self.assertEqual(self.player.parse_selection('a', tracks), (tracks, False))
        self.assertEqual(self.player.parse_selection('l', tracks), (tracks, True))
        for value in ['', '0', '3', '-1', '1 2', 'r 0', 'r a', '9999999999']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.player.parse_selection(value, tracks)
        with self.assertRaises(ValueError):
            self.player.parse_selection('a', [])

    def test_two_track_order_CRC_completion_and_final_stop(self):
        self.run_tracks()
        self.assertEqual(self.summary, {'completed': 2, 'cycles': 1})
        self.assertEqual(self.trace(), b''.join(data[i+4:i+6] for data in (self.a, self.b)
                                               for i in range(16, len(data), 6)))
        self.assertEqual(sum(m.startswith('DONE /') for m in self.messages), 2)
        self.assert_stopped()

    def test_selected_track_only(self):
        self.run_tracks(paths=['B.bin'])
        self.assertEqual(self.summary['completed'], 1)
        self.assertEqual(self.trace(), b''.join(self.b[i+4:i+6] for i in range(16, len(self.b), 6)))
        self.assert_stopped()

    def test_repeat_one_interrupt_stops_and_does_not_restart(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_tracks(repeat=True, paths=['A.bin'], stop_at=10)
        one = b''.join(self.a[i+4:i+6] for i in range(16, len(self.a), 6))
        self.assertEqual(self.trace(), one * 2 + one[:4])
        self.assert_stopped()

    def test_loop_all_keeps_order_across_cycle_boundary(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_tracks(repeat=True, stop_at=11)
        expected = b''.join(data[i+4:i+6] for data in (self.a, self.b, self.a) for i in range(16, len(data), 6))
        self.assertEqual(self.trace(), expected[:22])
        self.assert_stopped()

    def test_I2C_failure_does_not_skip_to_next_track_or_retry_automatically(self):
        with self.assertRaisesRegex(OSError, 'injected I2C failure'):
            self.run_tracks(fail_at=2)
        self.assertEqual(self.commands.count(2), 1)
        self.assert_stopped()

    def test_modified_file_fails_before_a_second_track_starts(self):
        data = bytearray(self.a)
        data[20] = 0xff  # Invalid register; target validates the PUSH atomically.
        (self.music / 'A.bin').write_bytes(data)
        with self.assertRaises(self.host.ProtocolError):
            self.run_tracks()
        self.assertEqual(self.commands.count(2), 1)
        self.assertEqual(self.trace(), b'')
        self.assert_stopped()

    def test_console_does_not_auto_play_and_CtrlC_returns_to_menu(self):
        owner = self
        class Stream:
            calls = []
            stops = 0
            def play_file(self, path):
                self.calls.append(Path(path).name)
                if len(self.calls) == 1:
                    raise KeyboardInterrupt()
                return {'executed': 5, 'total': 5, 'period_ms': 700, 'crc32': binascii.crc32(owner.b)}
            def stop(self):
                self.stops += 1
        stream = Stream()
        tracks = self.scan()[0]
        commands = iter(['invalid', 'r 1', '2', 'q'])
        with mock.patch.object(self.player, 'scan_tracks', return_value=(tracks, [])):
            self.player.run_console(stream, read_line=lambda prompt: next(commands), write=self.messages.append)
        self.assertEqual(stream.calls, ['A.bin', 'B.bin'])
        self.assertEqual(stream.stops, 2)
        self.assertTrue(any(m.startswith('STOP /') for m in self.messages))

    def test_menu_quit_and_rescan_never_take_ownership(self):
        class ReadOnly:
            def play_file(self, path):
                raise AssertionError('Unrequested play')
            def stop(self):
                raise AssertionError('Idle menu must not globally STOP MIDI')
        commands = iter(['u', 'q'])
        with mock.patch.object(self.player, 'scan_tracks', return_value=([], [])) as scan:
            self.player.run_console(ReadOnly(), read_line=lambda prompt: next(commands), write=self.messages.append)
            self.assertEqual(scan.call_count, 2)

    def test_entry_releases_HOST_pins_on_quit_and_unexpected_error(self):
        c = self.c
        for failure in (False, True):
            with self.subTest(failure=failure):
                events = []
                class Bus:
                    def readfrom(self, address, size):
                        out = C.create_string_buffer(64)
                        c.model_status(out)
                        return out.raw
                    def writeto(self, *args):
                        raise AssertionError('Idle entry must not STOP or PLAY')
                    def deinit(self):
                        events.append('deinit')
                class Pin:
                    IN = 0
                    def __init__(self, number, mode=None):
                        if mode == self.IN:
                            events.append(number)
                machine = types.SimpleNamespace(Pin=Pin, I2C=lambda *args, **kwargs: Bus())
                with mock.patch.dict(sys.modules, {'machine': machine,
                        'ym2203_revc_stream': self.host, 'ym2203_revc_player': self.player}):
                    entry = module('player_entry', ROOT / 'host/player.py')
                with mock.patch.object(entry, 'run_console', side_effect=RuntimeError('test') if failure else None), \
                        contextlib.redirect_stdout(io.StringIO()):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError, 'test'):
                            entry.main()
                    else:
                        entry.main()
                self.assertEqual(events, ['deinit', 0, 1])

    @unittest.skipUnless(os.getenv('REVC_TEST_SONG'), 'private full-score model')
    def test_private_full_song_followed_by_next_track(self):
        self.a = Path(os.environ['REVC_TEST_SONG']).read_bytes()
        (self.music / 'A.bin').write_bytes(self.a)
        self.run_tracks()
        expected = b''.join(data[i+4:i+6] for data in (self.a, self.b) for i in range(16, len(data), 6))
        self.assertEqual(self.trace(), expected)
        self.assertEqual(self.summary, {'completed': 2, 'cycles': 1})
        self.assert_stopped()
