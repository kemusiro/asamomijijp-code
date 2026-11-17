# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('run_fit', HERE / 'run.py')
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)


def report(fmax=23.74, constraint=16):
    return {'fmax': {'clk': {'achieved': fmax, 'constraint': constraint}},
            'utilization': {'ICESTORM_LC': {'used': 3062, 'available': 5280}},
            'critical_paths': []}


class Reports(unittest.TestCase):
    def test_pass_requires_routing_and_successful_exit(self):
        r = fit.summarize_pnr(16, 1, 0, report(), 'Info: Routing complete.')
        self.assertEqual(r['classification'], 'pass')
        self.assertEqual(fit.summarize_pnr(16, 1, 0, report(), '')['classification'],
                         'implementation_error')

    def test_failed_timing_cannot_be_counted_as_pass(self):
        log = 'Info: Routing complete.\nERROR: Max frequency for clock clk: 23.74 MHz (FAIL at 24.00 MHz)'
        r = fit.summarize_pnr(24, 1, 1, report(constraint=24), log)
        self.assertEqual(r['classification'], 'timing_fail')
        self.assertEqual(r['exit_code'], 1)

    def test_capacity_failure_is_not_timing_failure(self):
        r = fit.summarize_pnr(16, 1, 1, None, 'ERROR: Unable to place cell')
        self.assertEqual(r['classification'], 'implementation_error')

    def test_other_errors_override_timing_failure(self):
        log = 'Info: Routing complete.\nERROR: Max frequency for clock clk\nERROR: Failed to route net'
        r = fit.summarize_pnr(24, 1, 1, report(constraint=24), log)
        self.assertEqual(r['classification'], 'implementation_error')

    def test_wrong_constraint_rejected(self):
        with self.assertRaises(ValueError):
            fit.summarize_pnr(24, 1, 0, report(constraint=4), 'Info: Routing complete.')

    def test_empty_core_rejected(self):
        r = report()
        r['utilization']['ICESTORM_LC']['used'] = 0
        with self.assertRaises(ValueError):
            fit.summarize_pnr(16, 1, 0, r, 'Info: Routing complete.')

    def test_lut_and_ff_are_reported_separately(self):
        raw = {'modules': {'top': {'num_cells_by_type': {
            'SB_LUT4': 100, 'SB_DFF': 20, 'SB_DFFE': 30,
            'SB_DFFN': 4, 'SB_RAM40_4K': 3, 'SB_MAC16': 1}}}}
        result = fit.cell_summary(raw)
        self.assertEqual(result['lut4'], 100)
        self.assertEqual(result['flip_flops'], 54)
        self.assertEqual(result['ebr'], 3)

    def test_other_tool_binary_requires_explicit_override(self):
        lock = {'yosys': {'binary_sha256': 'a'}}
        actual = {'yosys': {'binary_sha256': 'b'}}
        with self.assertRaises(ValueError):
            fit.check_tools(lock, actual, False)
        self.assertFalse(fit.check_tools(lock, actual, True))
        self.assertTrue(fit.check_tools(lock, lock, False))


if __name__ == '__main__':
    unittest.main()
