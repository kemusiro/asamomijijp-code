# SPDX-License-Identifier: MIT
"""Model of RP2350 target registers plus the actual external-host test script."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel


HERE = Path(__file__).resolve().parent


class Registers:
    def __init__(self, bus, allow_ssg=False, allow_fm=False):
        self.bus = bus
        self.allow_ssg = allow_ssg
        self.allow_fm = allow_fm
        self.values = {0x400900FC:0x44570140}
        self.rx = deque()
        self.tx = deque()
        self.accesses = []
        self.interrupt = False
        self.stuck_enable = False

    def __getitem__(self, address):
        self.accesses.append(("read",address))
        assert self.allow_fm or self.bus.level(26) == 0
        assert self.allow_ssg or all(self.bus.level(pin) == 0 for pin in (9,19,22))
        if address == 0x40090034 and self.interrupt:
            self.interrupt = False
            raise KeyboardInterrupt
        if address == 0x40090078:
            return len(self.rx)
        if address == 0x40090010:
            return self.rx.popleft()
        clear_bits = {0x40090050:0x20,0x40090054:0x40,0x40090058:0x80,
                      0x40090060:0x200,0x400900A8:0x1000}
        if address == 0x40090040:
            self.values[0x40090034] = 0
        elif address in clear_bits:
            if address == 0x40090050 and self.values.get(0x40090034,0) & 0x20:
                assert self.tx, 'Read request cleared before TX data is queued'
            self.values[0x40090034] = self.values.get(0x40090034,0) & ~clear_bits[address]
        return self.values.get(address,0)

    def __setitem__(self, address, value):
        self.accesses.append(("write",address,value))
        assert self.allow_fm or self.bus.level(26) == 0
        assert self.allow_ssg or all(self.bus.level(pin) == 0 for pin in (9,19,22))
        self.values[address] = value
        if address == 0x4009006C:
            self.values[0x4009009C] = 0 if self.stuck_enable else value & 1
        if address == 0x40090010:
            assert self.values.get(0x40090034,0) & 0x20, "Read request released before TX"
            self.tx.append(value)


def load(bus, registers_factory=Registers):
    base = bus.load()
    regs = registers_factory(bus)
    machine = types.SimpleNamespace(Pin=bus.Pin, mem32=regs)
    def initialize(bus_id, **kwargs):
        assert bus_id == 0
        assert kwargs['sda'].gpio == 20 and kwargs['scl'].gpio == 21
        assert kwargs['freq'] == 100000
        return object()  # deliberately has no I2C.deinit
    machine.I2C = initialize
    machine.SoftI2C = object
    def import_file(name, filename):
        spec = importlib.util.spec_from_file_location(name, HERE / filename)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'machine':machine,'rev_c_bus_check':base}):
            spec.loader.exec_module(module)
        return module
    target = import_file('i2c_target_diagnostic','rev_c_i2c_target_check.py')
    host = import_file('i2c_host_diagnostic','rev_c_i2c_host_check.py')
    target.time = types.SimpleNamespace(
        ticks_ms=lambda: bus.us // 1000,
        ticks_diff=lambda a,b:a-b,
        sleep_us=lambda us:bus.sleep_us(max(us,1000)),
    )
    return target, host, regs


class Link:
    def __init__(self, target, regs):
        self.target, self.regs = target, regs

    def scan(self):
        return [0x42]

    def writeto(self, address, data, stop=True):
        assert address == 0x42
        self.regs.values[0x40090070] = 0x40
        for index, value in enumerate(data):
            self.regs.rx.append(value | (0x800 if index == 0 else 0))
            self.target.poll()
        if stop:
            self.regs.values[0x40090070] = 0
            self.regs.values[0x40090034] = 0x200
            self.target.poll()
        return len(data)

    def readfrom(self, address, count):
        assert address == 0x42
        self.regs.values[0x40090070] = 0x40
        data = bytearray(count)
        for index in range(count):
            self.regs.values[0x40090034] = 0x20
            self.target.poll()
            data[index] = self.regs.tx.popleft()
        self.regs.values[0x40090070] = 0
        self.regs.values[0x40090034] = 0x280
        self.target.poll()
        return bytes(data)


class I2CTests(unittest.TestCase):
    def test_read_request_remains_asserted_while_reply_is_prepared(self):
        bus = BusModel()
        module,host,regs = load(bus)
        board = module.RevCBus()
        target = module.Target()
        try:
            target.prepare()
            original = target.window.next_byte
            def delayed_byte():
                self.assertTrue(regs.values[module.IC_RAW_INTR_STAT] & module.RD_REQ,
                                'RD_REQ released before reply preparation')
                bus.sleep_ms(20)  # represent an interrupt/GC pause in Python
                self.assertTrue(regs.values[module.IC_RAW_INTR_STAT] & module.RD_REQ)
                return original()
            target.window.next_byte = delayed_byte
            regs.values[module.IC_RAW_INTR_STAT] = module.RD_REQ
            target.poll()
            self.assertEqual(regs.tx.popleft(),ord('R'))
            self.assertFalse(regs.values[module.IC_RAW_INTR_STAT] & module.RD_REQ)
        finally:
            target.close()
            board.close()

    def test_actual_host_patterns_run_against_target_register_polling(self):
        bus = BusModel()
        module, host, regs = load(bus)
        output = io.StringIO()
        def serve(target):
            target._enable(1)
            host.check(Link(target,regs))
            self.assertTrue(target.window.finished)
            self.assertEqual(target.window.ignored,1)  # read-only protection test
        with patch.object(module.Target,'serve',serve), redirect_stdout(output):
            module.run()
        self.assertIn('22 patterns x 32 bytes',output.getvalue())
        self.assertIn('HOST PASS:',output.getvalue())
        self.assertIn('SAFE:',output.getvalue())
        self.assertIn('DONE:',output.getvalue())
        self.assertFalse(bus.writes)
        bus.assert_stopped()
        self.assertEqual(regs.values[module.IC_ENABLE],0)
        self.assertTrue(all(bus.pins[p].mode == bus.Pin.IN for p in (20,21)))

    def test_repeated_start_drains_pointer_before_serving_read(self):
        bus = BusModel()
        module, host, regs = load(bus)
        board = module.RevCBus()
        target = module.Target()
        try:
            target.prepare()
            target.window.data[0x21] = 85
            regs.rx.append(0x800 | 0x21)
            regs.values[module.IC_RAW_INTR_STAT] = 0x1020
            target.poll()
            self.assertEqual(regs.tx.popleft(),85)
        finally:
            target.close()
            board.close()

    def test_finish_waits_for_slave_activity_to_end(self):
        bus = BusModel()
        module, host, regs = load(bus)
        board = module.RevCBus()
        target = module.Target()
        try:
            target.prepare()
            regs.values[module.IC_STATUS] = 0x40
            regs.rx.extend((0x800 | 0x7F,0xA5))
            target.poll()
            self.assertTrue(target.window.finish_pending)
            self.assertFalse(target.window.finished)
            regs.values[module.IC_STATUS] = 0
            target.poll()
            self.assertTrue(target.window.finished)
        finally:
            target.close()
            board.close()

    def test_first_byte_marker_resets_pointer_and_protected_writes_are_ignored(self):
        module, host, regs = load(BusModel())
        window = module.Window()
        for word in (0x820,85,170,0x821,127,0x800,0):
            window.receive(word)
        self.assertEqual(window.data[0x20:0x22],b'\x55\x7f')
        self.assertEqual(window.data[:8],module.SIGNATURE)
        self.assertEqual(window.ignored,1)
        self.assertFalse(window.finish_pending)

    def test_fifo_and_unexpected_abort_errors_keep_board_silent_and_clean_up(self):
        for raw, source in ((1,0),(2,0),(8,0),(0x40,0x4000),(0x40,0x5000)):
            with self.subTest(raw=raw,source=source):
                self.check_failure('irq',raw,source)

    def test_stale_tx_flush_is_acknowledged_before_read_request(self):
        bus = BusModel()
        module, host, regs = load(bus)
        board = module.RevCBus()
        target = module.Target()
        try:
            target.prepare()
            regs.values[module.IC_RAW_INTR_STAT] = 0x60
            regs.values[module.IC_TX_ABRT_SOURCE] = 0x2000
            target.poll()
            self.assertEqual(target.flushes,1)
            self.assertEqual(regs.tx.popleft(),ord('R'))
        finally:
            target.close()
            board.close()

    def test_setup_failure_interrupt_and_enable_timeout_close_pins(self):
        for fault in ('component','interrupt','enable'):
            with self.subTest(fault=fault):
                self.check_failure(fault)

    def check_failure(self, fault, raw=0, source=0):
        bus = BusModel()
        module, host, regs = load(bus)
        if fault == 'component':
            regs.values[module.IC_COMP_TYPE] = 0
        def serve(target):
            if fault == 'enable':
                regs.stuck_enable = True
            target._enable(1)
            if fault == 'interrupt':
                regs.interrupt = True
            regs.values[module.IC_RAW_INTR_STAT] = raw
            regs.values[module.IC_TX_ABRT_SOURCE] = source
            target.poll()
        exception = KeyboardInterrupt if fault == 'interrupt' else RuntimeError
        with patch.object(module.Target,'serve',serve), redirect_stdout(io.StringIO()), self.assertRaises(exception):
            module.run()
        bus.assert_stopped()
        self.assertEqual(regs.values[module.IC_ENABLE],0)
        self.assertTrue(all(bus.pins[p].mode == bus.Pin.IN for p in (20,21)))

    def test_listen_timeout_and_tick_wrap_are_bounded(self):
        bus = BusModel()
        module, host, regs = load(bus)
        board = module.RevCBus()
        target = module.Target()
        counter = (1 << 30) - 2
        def ticks():
            nonlocal counter
            counter += 1
            return counter % (1 << 30)
        try:
            target.prepare()
            module.time = types.SimpleNamespace(ticks_ms=ticks,ticks_diff=bus.ticks_diff)
            with patch.object(module,'WAIT_MS',3), self.assertRaisesRegex(RuntimeError,'timed out'):
                target.serve()
        finally:
            target.close()
            board.close()

    def test_host_failure_releases_only_host_gp0_gp1(self):
        module, host, regs = load(BusModel())
        pins = {}
        class HostPin:
            IN = 0
            def __init__(self,gpio,mode=None,**kwargs):
                pins[gpio] = mode
        host.Pin = HostPin
        host.SoftI2C = lambda **kwargs: types.SimpleNamespace(scan=lambda:[])
        host.time = types.SimpleNamespace(sleep_ms=lambda ms:None)
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'No target'):
            host.run()
        self.assertEqual(pins,{0:HostPin.IN,1:HostPin.IN})

    def test_import_does_not_access_gpio_or_peripheral(self):
        bus = BusModel()
        module, host, regs = load(bus)
        self.assertEqual(bus.pins,{})
        self.assertEqual(regs.accesses,[])


if __name__ == '__main__':
    unittest.main()
