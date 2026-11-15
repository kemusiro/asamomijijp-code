# SPDX-License-Identifier: MIT
"""Real audio.c loop with chained DMA, FIFO credits and repeated pause/resume.

This is a software model, not an RP2350 electrical trace. The alternate-source
option proves the old lifecycle fails under the same injected credit state.
"""
import ctypes as C
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AudioCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='revc-audio-core-')
        p = Path(cls.temp.name)
        for rel in ['hardware/pio.h', 'hardware/dma.h', 'hardware/clocks.h',
                    'hardware/structs/dma_debug.h', 'pico/stdlib.h']:
            f = p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('#include "audio_core_stub.h"\n')
        for prefix in ['fm_rx', 'i2s_tx']:
            (p / (prefix + '.pio.h')).write_text('''#include "audio_core_stub.h"
static const pio_program NAME_program={0};
static inline pio_sm_config NAME_program_get_default_config(unsigned offset){(void)offset;return (pio_sm_config){0};}
#define NAME_offset_entry 0
'''.replace('NAME', prefix))
        source = Path(os.environ.get('REVC_TEST_AUDIO_SOURCE', ROOT / 'src/audio.c'))
        lib = p / 'audio.so'
        args = [shutil.which('cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-fPIC', '-shared', '-I' + str(p),
                '-I' + str(ROOT / 'src'), '-I' + str(ROOT / 'tests')]
        if 'REVC_TEST_AUDIO_SOURCE' in os.environ:
            args += ['-DREVC_AUDIO_LEGACY_SNAPSHOT']
        args += [str(source), str(ROOT / 'src/audio_start.c'), str(ROOT / 'src/audio_dma.c'),
                 str(ROOT / 'src/wym1.c'), str(ROOT / 'src/diagnostic.c'),
                 str(ROOT / 'tests/audio_core_bridge.c'), '-o', str(lib)]
        subprocess.run(args, check=True)
        cls.c = C.CDLL(str(lib))
        cls.c.am_run.argtypes = [C.c_uint, C.c_uint, C.c_uint]
        cls.c.am_drift.argtypes = [C.c_int, C.c_uint]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_repeated_restart_renews_credits_and_disables_every_chain_before_abort(self):
        for phase in [125, 500, 2200, 4500, 15000]:
            with self.subTest(phase=phase):
                self.c.am_run(32, phase, 0)
                self.assertEqual(self.c.am_get(0), 0, 'audio fault after DMA restart')
                self.assertEqual(self.c.am_get(1), 1)
                self.assertEqual(self.c.am_get(2), 32)
                self.assertEqual(self.c.am_get(3), 33)
                self.assertEqual(self.c.am_get(4), 0, 'abort while a chain member remains enabled')
                self.assertEqual(self.c.am_get(9), 0, 'enabled before CHAN_ABORT retired')
                self.assertGreater(self.c.am_get(5), 2)

    def test_real_audio_loop_retains_fault16_and_snapshots_failed_DMA_prime(self):
        self.c.am_run(0, 1000, 1)
        self.assertEqual(self.c.am_get(0), 16)
        self.assertEqual(self.c.am_get(1), 0)
        self.assertEqual(self.c.am_get(3), 0)
        self.assertEqual(self.c.am_get(5), 2)
        self.assertEqual(self.c.am_get(6), 1)
        self.assertEqual(self.c.am_get(7), 0)
        self.assertEqual(self.c.am_get(8), 0)

    def test_fractional_clock_drift_does_not_exhaust_the_short_pipeline(self):
        for ppm in [-500, -30, -5, 5, 30, 500]:
            with self.subTest(ppm=ppm):
                self.c.am_drift(ppm, 600)
                self.assertEqual(self.c.am_get(0), 0,
                                 'fault%d at%dms for%dppm' % (self.c.am_get(0), self.c.am_get(10), ppm))
                self.assertGreaterEqual(self.c.am_get(10), 600000)
                self.assertEqual(self.c.am_get(1), 1)

    def test_genuine_TX_chain_failure_still_mutes_and_snapshots_fault5(self):
        self.c.am_run(0, 1000, 2)
        self.assertEqual(self.c.am_get(0), 5)
        self.assertEqual(self.c.am_get(1), 0)
        self.assertEqual(self.c.am_get(8), 0)
        self.assertEqual(self.c.am_get(13), 1)
        self.assertEqual(self.c.am_get(14), 2)
