# SPDX-License-Identifier: MIT
"""HOST-only pin release/rebind against the independently polled SixTarget."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_six import fixture

HERE = Path(__file__).resolve().parent


class HostHardware:
    def __init__(self, wire, target, model):
        self.connected = True
        self.rebinds = []
        self.releases = []
        self.attach_states = []
        outer = self

        class Pin:
            IN = 0
            def __init__(self, number, mode=None, pull=None):
                self.number = number
                if mode is not None:
                    assert number in (0, 1) and mode == self.IN and pull is None
                    outer.connected = False
                    outer.releases.append(number)

        class Link:
            def writeto(self, *args):
                assert outer.connected, 'I2C while HOST pins released'
                return wire.writeto(*args)
            def readfrom(self, *args):
                assert outer.connected, 'I2C while HOST pins released'
                return wire.readfrom(*args)

        def I2C(index, *, sda, scl, freq, timeout):
            outer.rebinds.append((index, sda.number, scl.number, freq, timeout))
            outer.attach_states.append((target.expirations, target.applied, model.level(19), model.level(26)))
            outer.connected = True
            return Link()
        self.Pin, self.I2C, self.Link = Pin, I2C, Link


def load(six, hardware):
    spec = importlib.util.spec_from_file_location('six_recovery', HERE/'rev_c_i2c_six_recovery_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'rev_c_i2c_six_host': six,
                                 'machine': types.SimpleNamespace(Pin=hardware.Pin, I2C=hardware.I2C)}):
        spec.loader.exec_module(module)
    module.time = six.time
    return module


class SixRecoveryTests(unittest.TestCase):
    def test_three_releases_no_IO_until_rebind_and_expiry_before_each_resume(self):
        model, target_module, six, target, board, wire, values = fixture()
        hardware = HostHardware(wire, target, model)
        module = load(six, hardware)
        observed = six.mixer.shared.ObservedI2C(hardware.Link())
        commits = []
        keeps = []
        original_write = wire.writeto
        def write(address, data, stop=True):
            if data == b'\x20\x06':
                keeps.append(data)
            return original_write(address, data, stop)
        wire.writeto = write
        original = target._commit
        def commit():
            original()
            commits.append(target.mask)
        target._commit = commit
        try:
            with redirect_stdout(io.StringIO()) as output:
                module.check_live(observed)
            wire.sleep_ms(30)
            self.assertEqual(hardware.releases, [0, 1]*3)
            self.assertEqual(hardware.rebinds, [(0, 0, 1, 10000, 500000)]*3)
            self.assertEqual(hardware.attach_states, [(i, 0, 0, 0) for i in (1, 2, 3)])
            self.assertEqual([x for x in commits if x], [63]*4)
            self.assertEqual((target.jobs, target.writes, target.expirations), (13, 48, 3))
            self.assertEqual((target.job, target.applied, target.prime_left), (-1, 0, 0))
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', output.getvalue())[1])
            self.assertEqual(final, wire.command_writes & 255)
            self.assertEqual(final, (len(keeps)+11) & 255)
            self.assertEqual(bytes(target.window.data[0x10:0x16]), bytes((final, 7, 0, 0, 0, 0)))
            self.assertTrue(target.window.finished)
            self.assertEqual(output.getvalue().count('ATTACH PASS'), 3)
            self.assertIn('HOST PASS:', output.getvalue())
            self.assertGreater(observed.read_calls, 64)
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_changed_ACK_bad_signature_or_unclean_lease_rejected_before_command(self):
        for fault in ('ACK', 'signature', 'lease', 'busy', 'mask'):
            model, target_module, six, target, board, wire, values = fixture()
            hardware = HostHardware(wire, target, model); module = load(six, hardware)
            try:
                with redirect_stdout(io.StringIO()):
                    remote = six.mixer.shared.preflight(wire, signature=six.SIGNATURE, remote_factory=six.Remote)
                remote.command(8, 0); remote.command(127, 1); remote.command(6, 1)
                wire.sleep_ms(1800)
                if fault == 'ACK': target.window.data[0x10] ^= 1
                if fault == 'signature': target.window.data[:8] = b'RCENV02!'
                if fault == 'lease': target.window.data[0x13] = 0
                if fault == 'busy': target.window.data[0x15] = 1
                if fault == 'mask': target.window.data[0x14] = 63
                before = wire.command_writes
                with self.assertRaisesRegex(RuntimeError, 'Recovery .* mismatch'):
                    module.RecoveredRemote(wire, remote.ack)
                self.assertEqual(wire.command_writes, before)
                self.assertEqual(target.applied, 0)
            finally:
                board.close(); target.close()

    def test_attach_reads_and_rebind_failures_do_not_retry_or_resume(self):
        for fault in ('rebind', 'read', 'STOP'):
            for error in (OSError, RuntimeError, MemoryError, KeyboardInterrupt):
                model, target_module, six, target, board, wire, values = fixture()
                hardware = HostHardware(wire, target, model); module = load(six, hardware)
                observed = six.mixer.shared.ObservedI2C(hardware.Link())
                attempts = []
                rebind = module.I2C; read = wire.readfrom; write = wire.writeto
                def I2C(*args, **kwargs):
                    if fault == 'rebind':
                        attempts.append(fault); raise error('injected rebind fault')
                    return rebind(*args, **kwargs)
                def readfrom(*args):
                    if fault == 'read' and hardware.rebinds:
                        attempts.append(fault); raise error('injected read fault')
                    return read(*args)
                def writeto(address, data, stop=True):
                    if fault == 'STOP' and hardware.rebinds and data == b'\x20\x00':
                        attempts.append(fault); raise error('injected STOP fault')
                    return write(address, data, stop)
                module.I2C = I2C; wire.readfrom = readfrom; wire.writeto = writeto
                try:
                    with redirect_stdout(io.StringIO()) as output, self.assertRaises(error):
                        module.check_live(observed)
                    self.assertEqual(attempts, [fault])
                    self.assertNotIn('six voices restored', output.getvalue())
                    self.assertNotIn('HOST PASS:', output.getvalue())
                    self.assertEqual((target.applied, target.expirations), (0, 1))
                finally:
                    board.close(); target.close()

    def test_expiry_already_present_is_not_cleared_by_release_or_STOP(self):
        model, target_module, six, target, board, wire, values = fixture()
        hardware = HostHardware(wire, target, model); module = load(six, hardware)
        try:
            with redirect_stdout(io.StringIO()):
                remote = six.mixer.shared.preflight(wire, signature=six.SIGNATURE, remote_factory=six.Remote)
            remote.command(8, 0); remote.command(127, 1); remote.command(6, 1)
            wire.sleep_ms(1800)
            before = wire.command_writes
            with self.assertRaisesRegex(RuntimeError, 'Six-voice state mismatch'):
                module.recover(wire, remote, 1)
            self.assertEqual(wire.command_writes, before)
            self.assertEqual(hardware.releases, [])
        finally:
            board.close(); target.close()

    def test_ticks_wrap_and_old_helper_rejected_before_startup(self):
        model, target_module, six, target, board, wire, values = fixture()
        hardware = HostHardware(wire, target, model); module = load(six, hardware)
        try:
            with patch.object(six.mixer.Remote, 'ack_wait_ms', 10), patch.object(six.staged.startup, 'check') as startup:
                with self.assertRaisesRegex(RuntimeError, 'v1.3 FM HOST'):
                    module.check(None)
                startup.assert_not_called()
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()):
                module.check_live(six.mixer.shared.ObservedI2C(hardware.Link()))
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.jobs, target.writes, target.expirations), (13, 48, 3))
        finally:
            board.close(); target.close()

    def test_import_is_silent_without_hardware_access(self):
        model, target_module, six, target, board, wire, values = fixture()
        hardware = HostHardware(wire, target, model)
        try:
            accesses = list(wire.regs.accesses); writes = list(model.writes)
            with redirect_stdout(io.StringIO()) as output:
                load(six, hardware)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(hardware.rebinds+hardware.releases, [])
            self.assertEqual(wire.regs.accesses, accesses)
            self.assertEqual(model.writes, writes)
        finally:
            board.close(); target.close()


if __name__ == '__main__':
    unittest.main()
