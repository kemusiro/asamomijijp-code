# SPDX-License-Identifier: MIT
"""The real-board heap probe must be quiet, finite and outside live capture."""
from contextlib import redirect_stdout
import io
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_voice_pitch import fixture


class BusHeapTests(unittest.TestCase):
    def test_silent_preflight_restores_all_pitches_and_scans_only_with_capture_stopped(self):
        model, module, host, target, board, wire, values = fixture()
        scans = []
        def allocated():
            self.assertFalse(getattr(model.stream, 'running', False))
            self.assertFalse(model.gc_enabled)
            self.assertEqual((model.level(19), model.level(26)), (0, 0))
            self.assertEqual(model.fm_keys, [False]*3)
            self.assertEqual(model.registers[8:11], [0]*3)
            scans.append(1)
            return 65536
        try:
            start = len(model.writes)
            with patch.object(module.gc, 'mem_alloc', allocated), redirect_stdout(io.StringIO()) as output:
                module.check_bus_heap(board)
            self.assertEqual(len(scans), 12)
            self.assertEqual(len(model.writes)-start, 216)
            self.assertEqual(output.getvalue().count('BUS HEAP: voice='), 6)
            self.assertIn('PASS: silent bus heap preflight', output.getvalue())
            self.assertTrue(model.gc_enabled)
            for channel in range(3):
                self.assertEqual((model.registers[0xA4+channel], model.registers[0xA0+channel]), module.control.live.PITCHES[module.INITIAL[channel]][1:])
                period = model.registers[channel*2] | model.registers[channel*2+1] << 8
                self.assertEqual(period, module.SSG_PERIODS[module.INITIAL[channel+3]])
        finally:
            board.close(); target.close()

    def test_growth_is_rejected_before_audio_and_original_GC_state_restored(self):
        for enabled in (True, False):
            model, module, host, target, board, wire, values = fixture()
            model.gc_enabled = enabled
            try:
                with patch.object(module.gc, 'mem_alloc', side_effect=[65536, 65632]), redirect_stdout(io.StringIO()) as output:
                    with self.assertRaisesRegex(RuntimeError, 'heap growth'):
                        module.check_bus_heap(board)
                self.assertEqual(model.gc_enabled, enabled)
                self.assertNotIn('PASS: silent bus', output.getvalue())
                self.assertEqual((model.level(19), model.level(26)), (0, 0))
            finally:
                board.close(); target.close()

    def test_probe_exception_restores_GC_without_enabling_sound(self):
        for error in (MemoryError, OSError, KeyboardInterrupt):
            model, module, host, target, board, wire, values = fixture()
            original = board.pitch_step; count = [0]
            def step(*args):
                count[0] += 1
                if count[0] == 3:
                    self.assertFalse(model.gc_enabled)
                    raise error('injected probe failure')
                original(*args)
            try:
                with patch.object(board, 'pitch_step', step), self.assertRaises(error):
                    module.check_bus_heap(board)
                self.assertTrue(model.gc_enabled)
                self.assertEqual((model.level(19), model.level(26)), (0, 0))
            finally:
                board.close(); target.close()

    def test_old_IO_helper_rejected_before_any_register_write(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            before = len(model.writes)
            board.io_version = '1.0'
            with self.assertRaisesRegex(RuntimeError, 'I/O v1.1'):
                module.check_bus_heap(board)
            self.assertEqual(len(model.writes), before)
        finally:
            board.close(); target.close()

    def test_running_capture_is_rejected_before_any_heap_scan(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            resources = types.SimpleNamespace(stream=types.SimpleNamespace(running=True))
            with patch.object(module, 'check_bus_heap') as probe:
                with self.assertRaisesRegex(RuntimeError, 'capture stopped'):
                    module.start_live(board, resources)
                probe.assert_not_called()
        finally:
            board.close(); target.close()


if __name__ == '__main__':
    unittest.main()
