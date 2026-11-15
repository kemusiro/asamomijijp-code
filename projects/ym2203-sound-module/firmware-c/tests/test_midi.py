# SPDX-License-Identifier: MIT
"""Real C MIDI planner, fixed register budget and BUSY/ownership semantics."""
import ctypes as C
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MidiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='revc-midi-')
        path = Path(cls.temp.name) / 'midi.so'
        subprocess.run([shutil.which('cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-shared', '-fPIC', '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/midi.c'), str(ROOT / 'src/wym1.c'),
                        str(ROOT / 'tests/midi_bridge.c'), '-o', str(path)], check=True)
        cls.c = C.CDLL(str(path))
        cls.c.mm_packet.argtypes = [C.c_void_p, C.c_bool]
        cls.c.mm_advance.argtypes = [C.c_uint64]
        cls.c.mm_trace.restype = C.c_void_p
        cls.c.revc_midi_pitch.argtypes = [C.c_uint, C.c_uint, C.c_void_p, C.c_void_p]
        cls.c.revc_midi_pitch.restype = C.c_bool

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.c.mm_init()

    def message(self, status, a=0, b=0, *, blocked=False, cin=None, cable=0):
        p = bytes([(status >> 4 if cin is None else cin) | (cable << 4), status, a, b])
        return self.c.mm_packet(p, blocked)

    def trace(self):
        data = C.string_at(self.c.mm_trace(), self.c.mm_get(4) * 2)
        return list(zip(data[::2], data[1::2]))

    def test_silent_until_explicit_supported_note(self):
        self.c.mm_advance(1000000)
        self.assertEqual(self.c.mm_get(1), 0)
        self.assertEqual(self.trace(), [])
        self.message(0xf8, cin=15)
        self.message(0xc0, 10)
        self.message(0x96, 60, 100)
        self.message(0x90, 60, 100, cable=1)
        self.assertEqual(self.c.mm_get(1), 0)

    def test_pitch_tables_match_accepted_MicroPython_all_128_notes(self):
        path = ROOT.parent / 'hardware/ym2203-single-board/firmware/src/ym2203_pitch.py'
        spec = importlib.util.spec_from_file_location('old_pitch', path)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        for voice in range(6):
            for note in range(128):
                first, second = C.c_uint8(), C.c_uint8()
                ok = self.c.revc_midi_pitch(voice, note, C.byref(first), C.byref(second))
                if voice < 3:
                    self.assertEqual(ok, old.FM_HIGH[note] != 255)
                    if ok:
                        self.assertEqual((first.value, second.value), (old.FM_HIGH[note], old.FM_LOW[note]))
                else:
                    self.assertEqual(ok, bool(old.SSG_PERIODS[note]))
                    if ok:
                        self.assertEqual(first.value + (second.value << 8), old.SSG_PERIODS[note])

    def test_fm_setup_then_off_high_low_and_all_operator_key_on(self):
        self.assertEqual(self.message(0x90, 60, 100), 1)
        self.assertFalse(self.c.mm_get(2))
        self.c.mm_advance(30000)
        self.assertEqual(self.c.mm_get(0), 3)
        self.assertTrue(self.c.mm_get(2))
        self.assertEqual(self.trace()[-4:], [(0x28, 0), (0xa4, 0x1c), (0xa0, 211), (0x28, 0xf0)])
        self.assertEqual(len(self.trace()), 88 + 4)

    def test_six_voices_and_each_channel_note_off(self):
        for voice, note in enumerate([60, 64, 67, 48, 52, 55]):
            self.message(0x90 | voice, note, 100)
        self.c.mm_advance(50000)
        self.assertEqual(self.c.mm_get(3), 63)
        for ch in range(3):
            self.assertIn((0x28, 0xf0 | ch), self.trace())
            self.assertIn((8 + ch, 7), self.trace())
        for voice in range(6):
            self.message(0xb0 | voice, 123, 0)
        self.c.mm_advance(10000)
        self.assertEqual(self.c.mm_get(3), 0)
        self.assertTrue(self.c.mm_get(1))  # Release tail holds ownership.
        self.c.mm_advance(150000)
        self.assertFalse(self.c.mm_get(1))
        self.assertFalse(self.c.mm_get(2))

    def test_latest_note_and_stale_note_off(self):
        self.message(0x90, 60, 100)
        self.c.mm_advance(30000)
        self.message(0x90, 64, 100)
        self.message(0x80, 60, 0)
        self.assertEqual(self.c.mm_note(0), 64)
        self.c.mm_advance(30000)
        self.message(0x90, 64, 0)
        self.c.mm_advance(150000)
        self.assertFalse(self.c.mm_get(1))

    def test_busy_retry_key_on_opens_gate_only_after_success(self):
        self.message(0x90, 60, 100)
        # Stop immediately before key-on, then defer its write.
        for _ in range(2000):
            self.c.mm_advance(20)
            if self.c.mm_get(9) == 3 and self.c.mm_get(0) == 3:
                break
        self.assertFalse(self.c.mm_get(2))
        self.c.mm_busy(5)
        self.c.mm_advance(40)
        self.assertTrue(self.c.mm_get(8))
        self.assertFalse(self.c.mm_get(2))
        self.c.mm_advance(1000)
        self.assertTrue(self.c.mm_get(2))

    def test_replacement_does_not_change_a_BUSY_latched_register(self):
        self.message(0x90, 60, 100)
        self.c.mm_advance(30000)
        self.message(0x90, 62, 100)
        self.c.mm_busy(10)
        self.c.mm_advance(40)
        self.assertTrue(self.c.mm_get(8))
        self.message(0x90, 67, 100)
        self.c.mm_advance(30000)
        self.assertEqual(self.c.mm_get(0), 3)  # Model faults on any latch mismatch.
        self.assertEqual(self.c.mm_note(0), 67)
        self.assertEqual(self.trace()[-4:], [(0x28, 0), (0xa4, 0x1f), (0xa0, 58), (0x28, 0xf0)])

    def test_note_off_during_BUSY_key_on_does_not_open_output_gate(self):
        self.message(0x90, 60, 100)
        for _ in range(2000):
            self.c.mm_advance(20)
            if self.c.mm_get(9) == 3 and self.c.mm_get(0) == 3:
                break
        self.c.mm_busy(10)
        self.c.mm_advance(40)
        self.assertTrue(self.c.mm_get(8))
        self.message(0x80, 60, 0)
        for _ in range(1500):
            self.c.mm_advance(20)
            self.assertFalse(self.c.mm_get(2))
        self.assertEqual(self.c.mm_get(0), 3)

    def test_IO_timeout_does_not_open_gate_or_continue_writes(self):
        self.message(0x90, 60, 100)
        self.c.mm_busy(100000)
        self.c.mm_advance(101000)
        self.assertEqual(self.c.mm_get(0), 4)
        self.assertFalse(self.c.mm_get(2))
        n = len(self.trace())
        self.c.mm_advance(100000)
        self.assertEqual(len(self.trace()), n)

    def test_blocked_notes_and_panic_cannot_affect_an_I2C_owner(self):
        for status, a, b in [(0x90, 60, 100), (0x93, 60, 100), (0xb0, 120, 0), (0xff, 0, 0)]:
            self.assertEqual(self.message(status, a, b, blocked=True), 0)
        self.assertEqual(self.c.mm_get(5), 2)
        self.c.mm_advance(100000)
        self.assertEqual(self.trace(), [])
        # Blocked messages are not held for a later source release.
        self.c.mm_advance(100000)
        self.assertFalse(self.c.mm_get(1))

    def test_panic_and_reset_require_explicit_new_note(self):
        for status, a, cin in [(0xb0, 120, 11), (0xff, 0, 15)]:
            self.c.mm_init()
            self.message(0x90, 60, 100)
            self.c.mm_advance(30000)
            self.assertEqual(self.message(status, a, 0, cin=cin), 2)
            self.c.mm_cancel()
            n = len(self.trace())
            self.c.mm_advance(200000)
            self.assertEqual(len(self.trace()), n)
            self.assertFalse(self.c.mm_get(1))
            self.assertEqual(self.message(0x93, 60, 100), 1)

    def test_malformed_supported_packet_panics_only_its_MIDI_session(self):
        self.assertEqual(self.message(0x90, 255, 1), 0)
        self.message(0x90, 60, 100)
        self.assertEqual(self.message(0x80, 60, 0, cin=9), 2)
        self.assertEqual(self.c.mm_get(6), 2)

    def test_out_of_range_note_silences_only_its_voice(self):
        self.message(0x90, 60, 100)
        self.message(0x93, 48, 100)
        self.c.mm_advance(30000)
        self.message(0x90, 127, 100)
        self.c.mm_advance(10000)
        self.assertEqual(self.c.mm_get(3), 8)
        self.message(0x93, 0, 100)
        self.c.mm_advance(150000)
        self.assertFalse(self.c.mm_get(1))

    def test_MIDI_holds_without_I2C_keep_and_one_tick_is_bounded(self):
        self.message(0x90, 60, 100)
        for _ in range(1200):
            n = len(self.trace())
            self.c.mm_advance(20)
            self.assertLessEqual(len(self.trace()) - n, 1)
        self.c.mm_advance(2000000)
        self.assertTrue(self.c.mm_get(1))
        self.assertTrue(self.c.mm_get(2))
