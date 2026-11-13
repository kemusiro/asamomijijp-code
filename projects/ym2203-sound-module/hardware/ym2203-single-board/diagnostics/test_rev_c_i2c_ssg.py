# SPDX-License-Identifier: MIT
"""External command acknowledgement, fixed SSG writes and lease mute."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel
from test_rev_c_i2c_check import load as load_link, Registers, Link
from test_rev_c_ssg_check import load_sound


HERE = Path(__file__).resolve().parent


def load(bus):
    link, host_link, regs = load_link(bus,lambda b:Registers(b,allow_ssg=True))
    sound = load_sound(bus)
    def import_file(name,filename):
        spec = importlib.util.spec_from_file_location(name,HERE / filename)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'rev_c_i2c_target_check':link,'rev_c_i2c_host_check':host_link,
                                    'rev_c_ssg_check':sound,'rev_c_bus_check':sound,
                                    'machine':types.SimpleNamespace(Pin=bus.Pin,I2C=object)}):
            spec.loader.exec_module(module)
        return module
    target = import_file('ssg_i2c_target','rev_c_i2c_ssg_target.py')
    host = import_file('ssg_i2c_host','rev_c_i2c_ssg_host.py')
    target.time = bus
    return target, host, link, regs


def host_clock(bus,target):
    def sleep(milliseconds):
        remaining = milliseconds
        while remaining:
            delta = min(10,remaining)
            bus.sleep_ms(delta)
            target.poll()
            remaining -= delta
    return types.SimpleNamespace(sleep_ms=sleep,ticks_ms=bus.ticks_ms,ticks_diff=bus.ticks_diff)


class RemoteSSGTests(unittest.TestCase):
    def test_hardware_host_uses_approved_pins_and_never_scans(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        host_pins = {}
        class HostPin:
            IN = 0
            def __init__(self,gpio,mode=None,**kwargs):
                self.gpio = gpio
                host_pins[gpio] = mode
        host.Pin = HostPin
        constructed = []
        output = io.StringIO()
        def serve(target):
            target._enable(1)
            wire = Link(target,regs)
            # Deliberately provide no scan method: all traffic must be nonempty.
            def hardware(bus_id,**kwargs):
                constructed.append((bus_id,kwargs['sda'].gpio,kwargs['scl'].gpio,kwargs['freq'],kwargs['timeout']))
                return types.SimpleNamespace(writeto=wire.writeto,readfrom=wire.readfrom)
            host.time = host_clock(bus,target)
            with patch.object(host,'I2C',hardware):
                host.run()
            self.assertTrue(target.window.finished)
        with patch.object(module.SoundTarget,'serve',serve), redirect_stdout(output):
            module.run()
        self.assertEqual(constructed,[(0,0,1,10000,500000)])
        self.assertEqual(host_pins,{0:HostPin.IN,1:HostPin.IN})
        self.assertIn('64 stable status reads + 32',output.getvalue())
        self.assertIn('HOST I2C STATS:',output.getvalue())
        bus.assert_stopped()

    def test_reported_ff_response_fails_without_replaying_tone_command(self):
        for response in (b'%\xff\xff\xff',b'\0\xff\xff\xff'):
            with self.subTest(response=response):
                module,host,link,regs = load(BusModel(allow_tone=True))
                sent = []
                host.time = types.SimpleNamespace(sleep_ms=lambda ms:None,ticks_ms=lambda:0)
                with patch.object(host,'read_at',side_effect=[b'\0\0\0\0',response]), patch.object(host,'checked_write',lambda i2c,data:sent.append(data)), self.assertRaisesRegex(RuntimeError,'actual='):
                    host.Remote(object()).command(1,1)
                self.assertEqual(sent,[b'\x20\x01'])

    def test_initial_status_rejects_invalid_bytes_before_commands(self):
        module,host,link,regs = load(BusModel(allow_tone=True))
        with patch.object(host,'read_at',return_value=b'\0\xff\xff\xff'), self.assertRaisesRegex(RuntimeError,'Initial'):
            host.Remote(object())

    def test_mixed_transport_versions_rejected_before_sound(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        board = module.SoundBus()
        try:
            with patch.object(link,'TRANSPORT_VERSION','1'), self.assertRaisesRegex(RuntimeError,'v1.1'):
                module.SoundTarget(board)
            self.assertEqual(bus.tone_windows,[])
        finally:
            board.close()
        bus.assert_stopped()

    def test_arbitration_abort_during_tone_mutes_before_gc(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        def serve(target):
            target._enable(1)
            Link(target,regs).writeto(0x42,b'\x20\x01')
            self.assertEqual(bus.level(19),1)
            regs.values[link.IC_RAW_INTR_STAT] = link.TX_ABRT
            regs.values[link.IC_TX_ABRT_SOURCE] = 0x5000
            target.poll()
        def collect():
            self.assertEqual(bus.level(19),0)
        output = io.StringIO()
        with patch.object(module.SoundTarget,'serve',serve), patch.object(module.gc,'collect',collect), redirect_stdout(output), self.assertRaisesRegex(RuntimeError,'0x5000'):
            module.run()
        bus.assert_stopped()
        self.assertEqual(regs.values[link.IC_ENABLE],0)
        self.assertIn('LAST CONTROL STATE (before reset)',output.getvalue())
        self.assertIn('TARGET: commands=',output.getvalue())

    def test_full_external_sequence_six_tones_then_independent_lease_mute(self):
        bus = BusModel(allow_tone=True)
        module, host, link, regs = load(bus)
        output = io.StringIO()
        def serve(target):
            target._enable(1)
            host.time = host_clock(bus,target)
            host.check(Link(target,regs))
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
        with patch.object(module.SoundTarget,'serve',serve), redirect_stdout(output):
            module.run()
        self.assertEqual([channel for channel,start,end in bus.tone_windows],[0,1,2,0,1,2,0])
        for channel,start,end in bus.tone_windows[:6]:
            self.assertGreaterEqual(end-start,2_000_000)
            self.assertLess(end-start,2_100_000)
        channel,start,end = bus.tone_windows[-1]
        self.assertGreaterEqual(end-start,1_000_000)
        self.assertLess(end-start,1_050_000)
        self.assertIn('HOST PASS:',output.getvalue())
        self.assertIn('lease_expirations=1',output.getvalue())
        self.assertIn('SAFE:',output.getvalue())
        self.assertIn('DONE:',output.getvalue())
        bus.assert_stopped()
        self.assertEqual(regs.values[link.IC_ENABLE],0)

    def test_command_waits_for_stop_and_partial_pointer_never_sounds(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        board = module.SoundBus()
        target = module.SoundTarget(board)
        try:
            board.start()
            target.prepare()
            connection = Link(target,regs)
            connection.writeto(0x42,b'\x20',False)
            self.assertEqual(bus.tone_windows,[])
            connection.writeto(0x42,b'\x20\x01',False)
            self.assertEqual(bus.tone_windows,[])
            regs.values[link.IC_STATUS] = 0
            target.poll()
            self.assertEqual([w[0] for w in bus.tone_windows],[0])
            self.assertEqual(target.window.data[0x10:0x14],b'\x01\x01\x01\x00')
        finally:
            board.close()
            target.close()

    def test_lease_wrap_and_late_keepalive_cannot_reenable_audio(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        board = module.SoundBus()
        target = module.SoundTarget(board)
        try:
            board.start()
            target.prepare()
            bus.us = ((1 << 30)-500)*1000
            connection = Link(target,regs)
            connection.writeto(0x42,b'\x20\x01')
            bus.sleep_ms(999)
            target.poll()
            self.assertEqual(target.active,1)
            bus.sleep_ms(2)
            connection.writeto(0x42,b'\x20\x04')
            self.assertEqual(target.active,0)
            self.assertEqual(target.expirations,1)
            self.assertEqual(target.window.data[0x12:0x14],b'\x00\x01')
            self.assertEqual(bus.level(19),0)
            self.assertEqual(bus.registers[8:11],[0,0,0])
        finally:
            board.close()
            target.close()

    def test_unknown_and_overlong_command_frames_fail_muted(self):
        for frame in (b'\x20\xff',b'\x20\x01\x02'):
            with self.subTest(frame=frame):
                self.run_failure(frame,ValueError)

    def test_interrupt_and_memory_error_mute_before_gc(self):
        for exception in (KeyboardInterrupt,MemoryError):
            with self.subTest(exception=exception):
                bus = BusModel(allow_tone=True)
                module,host,link,regs = load(bus)
                def collect():
                    self.assertEqual(bus.level(19),0)
                    # Preflight collect is allowed while reset is released, but silent.
                def serve(target):
                    target._enable(1)
                    Link(target,regs).writeto(0x42,b'\x20\x01')
                    self.assertEqual(bus.level(19),1)
                    raise exception
                with patch.object(module.SoundTarget,'serve',serve), patch.object(module.gc,'collect',collect), redirect_stdout(io.StringIO()), self.assertRaises(exception):
                    module.run()
                bus.assert_stopped()
                self.assertEqual(regs.values[link.IC_ENABLE],0)

    def test_failed_ssg_readback_never_enables_second_channel(self):
        self.run_failure(b'\x20\x02',RuntimeError,bad_second=True)

    def run_failure(self, frame, exception, bad_second=False):
        bus = BusModel(allow_tone=True,bad_second_tone=bad_second)
        module,host,link,regs = load(bus)
        def serve(target):
            target._enable(1)
            connection = Link(target,regs)
            if bad_second:
                connection.writeto(0x42,b'\x20\x01')
            connection.writeto(0x42,frame)
        with patch.object(module.SoundTarget,'serve',serve), redirect_stdout(io.StringIO()), self.assertRaises(exception):
            module.run()
        bus.assert_stopped()
        self.assertEqual(regs.values[link.IC_ENABLE],0)
        self.assertTrue(all(w[0] == 0 for w in bus.tone_windows))

    def test_host_rejects_bad_ack_and_stale_ack_timeout(self):
        for wrong in (True,False):
            with self.subTest(wrong=wrong):
                module,host,link,regs = load(BusModel(allow_tone=True))
                clock = 0
                def sleep(ms):
                    nonlocal clock
                    clock += ms
                host.time = types.SimpleNamespace(sleep_ms=sleep,ticks_ms=lambda:clock,ticks_diff=lambda a,b:a-b)
                call = 0
                def read(*args):
                    nonlocal call
                    call += 1
                    return b'\x01\xff\x00\x00' if wrong and call > 1 else b'\x00\x00\x00\x00'
                with patch.object(host,'read_at',read), patch.object(host,'checked_write',lambda *args:None), self.assertRaises(RuntimeError):
                    host.Remote(object()).command(1,1)

    def test_keepalive_does_not_retrigger_or_change_tone_registers(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        board = module.SoundBus()
        target = module.SoundTarget(board)
        try:
            board.start()
            target.prepare()
            connection = Link(target,regs)
            connection.writeto(0x42,b'\x20\x01')
            writes = len(bus.writes)
            connection.writeto(0x42,b'\x20\x04')
            self.assertEqual(len(bus.writes),writes)
            self.assertEqual(len(bus.tone_windows),1)
        finally:
            board.close()
            target.close()

    def test_import_has_no_gpio_or_register_side_effect(self):
        bus = BusModel(allow_tone=True)
        module,host,link,regs = load(bus)
        self.assertEqual(bus.pins,{})
        self.assertEqual(regs.accesses,[])


if __name__ == '__main__':
    unittest.main()
