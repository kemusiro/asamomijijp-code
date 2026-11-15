# SPDX-License-Identifier: MIT
"""Actual main.c arbitration and disconnect logic; SDK/GPIO/USB are modelled."""
import binascii
import ctypes as C
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from test_stream import packet

ROOT = Path(__file__).resolve().parents[1]
STUB = '''#ifndef CONTROL_STUB_H
#define CONTROL_STUB_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {uint32_t sof_rd;} usb_model_regs;
extern usb_model_regs model_usb_regs;
#define usb_hw (&model_usb_regs)
enum {DCD_EVENT_BUS_RESET=1,DCD_EVENT_UNPLUGGED=2,DCD_EVENT_SUSPEND=3};
uint64_t time_us_64(void);uint32_t time_us_32(void);void tight_loop_contents(void);
void multicore_launch_core1(void(*)(void));void reset_usb_boot(unsigned,unsigned);
void watchdog_update(void);void watchdog_enable(unsigned,bool);void watchdog_reboot(unsigned,unsigned,unsigned);
void tusb_init(void);void tud_task(void);bool tud_cdc_connected(void);bool tud_mounted(void);
bool tud_suspended(void);bool tud_midi_mounted(void);bool tud_midi_packet_read(uint8_t *);
void tud_cdc_read_flush(void);unsigned tud_cdc_available(void);unsigned tud_cdc_read(void *,unsigned);
unsigned tud_cdc_write_available(void);unsigned tud_cdc_write(const void *,unsigned);void tud_cdc_write_flush(void);
#endif
'''


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='revc-control-')
        folder = Path(cls.temp.name)
        (folder / 'control_stub.h').write_text(STUB)
        for name in ['pico/stdlib.h', 'pico/multicore.h', 'pico/bootrom.h', 'hardware/watchdog.h',
                     'hardware/structs/usb.h', 'tusb.h', 'device/dcd.h']:
            p = folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('#include "control_stub.h"\n')
        spec = importlib.util.spec_from_file_location('control_embed', ROOT / 'tools/embed_song.py')
        cls.embed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.embed)
        data = cls.embed.demo()
        (folder / 'song.c').write_text(cls.embed.emit('revc_song', data) + cls.embed.emit('revc_demo', data))
        lib = folder / 'control.so'
        subprocess.run([shutil.which('cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-shared', '-fPIC', '-I' + str(folder), '-I' + str(ROOT / 'src'),
                        str(ROOT / 'tests/control_bridge.c'), str(ROOT / 'src/midi.c'),
                        str(ROOT / 'src/stream.c'), str(ROOT / 'src/wym1.c'),
                        str(ROOT / 'src/diagnostic.c'), str(folder / 'song.c'), '-o', str(lib)], check=True)
        cls.c = C.CDLL(str(lib))
        cls.c.cm_add.argtypes = [C.c_uint64, C.c_uint, C.c_void_p, C.c_uint]
        cls.c.cm_run.argtypes = [C.c_uint64]
        cls.c.cm_logs.restype = C.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.c.cm_clear()
        self.events = []

    def add(self, at_ms, kind, data=b''):
        self.events.append((int(at_ms * 1000), kind, data))

    def run_events(self, until_ms):
        for at, kind, data in sorted(self.events, key=lambda e: e[0]):
            self.c.cm_add(at, kind, data, len(data))
        self.c.cm_run(int(until_ms * 1000))
        return [[self.c.cm_snap(i, f) for f in range(14)] for i in range(self.c.cm_count())]

    def test_MIDI_without_CDC_and_I2C_begin_rejected_then_STOP_preempts(self):
        self.add(200, 6)  # DTR falls before MIDI begins.
        self.add(500, 1, b'\x09\x90\x3c\x64')
        self.add(550, 0)
        self.add(600, 6)  # CDC closing alone must not stop MIDI.
        data = self.embed.demo()
        self.add(700, 2, packet(2, 0, data[:16] + struct.pack('<I', binascii.crc32(data))))
        self.add(750, 0)
        self.add(800, 2, packet(1, 0))
        self.add(850, 0)
        self.add(1100, 0)
        self.add(1200, 1, b'\x09\x93\x30\x64')
        self.add(1300, 0)
        s = self.run_events(1400)
        self.assertEqual([x[0] for x in s], [1, 1, 0, 0, 1])
        self.assertEqual([x[1] for x in s], [1, 1, 0, 0, 1])
        self.assertEqual(s[1][5], 4)  # BEGIN STATE result, MIDI keeps playing.
        self.assertEqual(s[2][4:7], [4, 0, 0])
        self.assertTrue(all(x[3] == 0 for x in s))

    def test_reset_suspend_and_SOF_timeout_stop_MIDI_without_automatic_replay(self):
        for kind in [4, 5, 7, 9]:
            with self.subTest(kind=kind):
                self.setUp()
                self.add(500, 1, b'\x09\x90\x3c\x64')
                self.add(550, 0)
                self.add(600, kind)
                self.add(900, 0)
                self.add(1000, 8)  # Mount/SOF resumes, no new Note On.
                self.add(1300, 0)
                s = self.run_events(1400)
                self.assertEqual([x[0] for x in s], [1, 0, 0])
                self.assertEqual([x[1] for x in s], [1, 0, 0])
                self.assertTrue(all(x[3] == 0 for x in s))

    def test_CDC_STOP_is_global_and_buffered_notes_do_not_restart(self):
        self.add(500, 1, b'\x09\x90\x3c\x64')
        self.add(550, 0)
        self.add(600, 3, b'stop\n')
        self.add(600, 1, b'\x09\x93\x30\x64' * 8)
        self.add(900, 0)
        self.add(1200, 0)
        s = self.run_events(1300)
        self.assertEqual([x[0] for x in s], [1, 0, 0])
        self.assertEqual([x[1] for x in s], [1, 0, 0])

    def test_chord_300ms_after_last_solo_note_off_is_accepted(self):
        self.add(500, 1, b'\x09\x95\x37\x64')
        self.add(1400, 0)
        self.add(1500, 1, b'\x08\x85\x37\x00')
        self.add(1750, 0)
        self.add(1800, 1, b'\x09\x90\x3c\x64\x09\x91\x40\x64\x09\x92\x43\x64'
                            b'\x09\x93\x30\x64\x09\x94\x34\x64\x09\x95\x37\x64')
        self.add(1900, 0)
        self.add(2500, 0)
        s = self.run_events(2600)
        self.assertEqual([x[0] for x in s], [1, 0, 1, 1])
        self.assertEqual([x[1] for x in s], [1, 0, 1, 1])
        self.assertTrue(all(x[3] == 0 for x in s))

    def test_browser_button1_timing_all_six_solos_then_chord(self):
        notes = [60, 64, 67, 48, 52, 55]
        for voice, note in enumerate(notes):
            start = 500 + voice * 1300
            self.add(start, 1, bytes([9, 0x90 | voice, note, 100]))
            self.add(start + 100, 0)
            self.add(start + 1000, 1, bytes([8, 0x80 | voice, note, 0]))
            self.add(start + 1250, 0)
        self.add(8300, 1, b''.join(bytes([9, 0x90 | v, note, 100]) for v, note in enumerate(notes)))
        self.add(8400, 0)
        self.add(10300, 0)
        s = self.run_events(10400)
        self.assertEqual([x[0] for x in s], [1, 0] * 6 + [1, 1])
        self.assertEqual([x[1] for x in s], [1, 0] * 6 + [1, 1])
        self.assertEqual([self.c.cm_snap(i, 14) for i in range(len(s))],
                         [mask for v in range(6) for mask in (1 << v, 0)] + [63, 63])
        self.assertTrue(all(x[3] == 0 for x in s))

    def test_explicit_STOP_and_panic_keep_200ms_input_discard(self):
        for kind, data in [(3, b'stop\n'), (1, b'\x0b\xb0\x78\x00'), (2, packet(1, 0))]:
            with self.subTest(kind=kind):
                self.setUp()
                self.add(500, 1, b'\x09\x90\x3c\x64')
                self.add(550, 0)
                self.add(600, kind, data)
                self.add(750, 1, b'\x09\x93\x30\x64')
                self.add(775, 0)
                self.add(850, 1, b'\x09\x93\x30\x64')
                self.add(950, 0)
                s = self.run_events(1000)
                self.assertEqual([x[0] for x in s], [1, 0, 1])
                self.assertEqual([x[1] for x in s], [1, 0, 1])
                self.assertTrue(all(x[3] == 0 for x in s))

    def test_I2C_score_ignores_MIDI_and_USB_reset_and_keeps_exact_completion(self):
        data = self.embed.demo()
        self.add(500, 2, packet(2, 0, data[:16] + struct.pack('<I', binascii.crc32(data))))
        seq = 1
        for offset in range(16, len(data), 192):
            self.add(500 + seq * 20, 2, packet(3, seq, data[offset:offset + 192]))
            seq += 1
        self.add(640, 2, packet(6, seq))
        seq += 1
        self.add(660, 2, packet(4, seq))
        seq += 1
        self.add(800, 1, b'\x09\x90\x3c\x64\x09\x93\x30\x64')
        self.add(850, 1, b'\x0b\xb0\x78\x00\x0f\xff\x00\x00')
        self.add(1000, 5)
        self.add(1100, 4)
        self.add(1200, 0)
        for at in range(1100, 13900, 400):
            self.add(at, 2, packet(5, seq))
            seq += 1
        self.add(13980, 0)
        self.add(14000, 8)
        self.add(14400, 0)
        self.add(14500, 1, b'\x09\x90\x3c\x64')
        self.add(14600, 0)
        s = self.run_events(14700)
        self.assertEqual(s[0][0], 0)
        self.assertEqual(s[0][4], 2)
        self.assertEqual(s[0][10], 2)
        self.assertEqual(s[1][4:10], [3, 0, 0, 191, 191, 191])
        self.assertEqual(s[1][1], 0)
        self.assertEqual(s[2][0], 0)
        self.assertEqual(s[3][0:2], [1, 1])
        self.assertTrue(all(x[3] == 0 for x in s))
