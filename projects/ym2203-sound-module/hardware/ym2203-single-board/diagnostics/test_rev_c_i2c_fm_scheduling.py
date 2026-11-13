# SPDX-License-Identifier: MIT
"""Sample target polling at 11.25 ms; never inject a poll at host STOP.

This models scheduling/clock stretching, not electrical timing or native audio.
The prior Link helper calls poll synchronously at every STOP, which concealed
the possibility that repeated status reads hide all idle samples.
"""
from contextlib import redirect_stdout
import io
import types
import unittest
from unittest.mock import patch

from test_rev_c_fm_ssg_check import MixerModel
from test_rev_c_i2c_fm import load


class SampledLink:
    def __init__(self,model,target,regs,transport,offset_us=11250):
        self.model, self.target, self.regs, self.transport = model,target,regs,transport
        self.next_tick = model.us + offset_us
        self.command_writes = 0

    def advance(self,until):
        while self.next_tick <= until:
            self.model.us = max(self.model.us,self.next_tick)
            self.next_tick += 11250
            self.target.poll()
            if self.target.start_requested:
                self.target.live_started = True
        self.model.us = max(self.model.us,until)

    def sleep_ms(self,ms):
        self.advance(self.model.us + ms*1000)

    def writeto(self,address,data,stop=True):
        assert address == 0x42
        self.regs.values[self.transport.IC_STATUS] = 0x40
        for index,value in enumerate(data):
            self.regs.rx.append(value | (0x800 if index == 0 else 0))
        if len(data) == 2 and data[0] == 0x20:
            self.command_writes += 1
        self.advance(self.next_tick)
        # A frame can finish just after a target sample. Do not call poll here.
        self.advance(self.model.us + 100)
        if stop:
            self.regs.values[self.transport.IC_STATUS] = 0
            self.regs.values[self.transport.IC_RAW_INTR_STAT] |= 0x200
        return len(data)

    def readfrom(self,address,count):
        assert address == 0x42
        self.regs.values[self.transport.IC_STATUS] = 0x40
        data = bytearray(count)
        for index in range(count):
            self.regs.values[self.transport.IC_RAW_INTR_STAT] |= 0x20
            self.advance(self.next_tick)
            data[index] = self.regs.tx.popleft()
            # At 10 kHz, nine clocks per data byte take 900 us.
            self.advance(self.model.us + 900)
        self.advance(self.model.us + 100)
        self.regs.values[self.transport.IC_STATUS] = 0
        self.regs.values[self.transport.IC_RAW_INTR_STAT] |= 0x280
        return bytes(data)


def fixture(offset_us=11250):
    model = MixerModel()
    module,host,shared,live,machine,transport,regs,guard = load(model)
    board = module.MixerBus()
    board.start()
    board.prepare()
    board.ssg('single')
    board.checked(8,0)
    model.stream = types.SimpleNamespace(starts=2)
    target = module.ControlTarget(board)
    target.prepare()
    target._enable(1)
    wire = SampledLink(model,target,regs,transport,offset_us)
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    host.time = shared.time = clock
    return model,module,host,target,board,wire


class SchedulingTests(unittest.TestCase):
    def active_remote(self,host,target,wire):
        remote = host.Remote(wire)
        target.live_started = True
        target.apply(3)
        for unused in range(63):
            target.apply(6)
        remote.ack = 64
        return remote

    def test_short_wait_starves_pending_keep_then_it_executes_after_host_stops(self):
        model,module,host,target,board,wire = fixture()
        try:
            remote = self.active_remote(host,target,wire)
            remote.ack_wait_ms = 10
            with self.assertRaisesRegex(RuntimeError,'acknowledgement timeout'):
                remote.command(6,3)
            self.assertEqual(bytes(target.window.data[0x10:0x14]),b'@\x06\x00\x01')
            self.assertEqual(target.window.pending,6)
            self.assertEqual(target.expirations,1)
            self.assertEqual(wire.command_writes,1)  # no replay of the command
            wire.sleep_ms(30)
            self.assertEqual(bytes(target.window.data[0x10:0x14]),b'A\x06\x00\x01')
            self.assertEqual(target.mode,0)  # a late KEEP cannot restart sound
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_default_live_wait_allows_pending_keep_without_lease_expiry(self):
        for offset in (100,1000,5000,10000,11250):
            with self.subTest(offset=offset):
                model,module,host,target,board,wire = fixture(offset)
                try:
                    remote = self.active_remote(host,target,wire)
                    remote.command(6,3)
                    self.assertEqual(remote.ack,65)
                    self.assertEqual(target.mode,3)
                    self.assertEqual(target.expirations,0)
                    self.assertEqual(wire.command_writes,1)
                finally:
                    board.close()
                    target.close()
                model.assert_stopped()

    def test_whole_host_sequence_with_independent_idle_sampling(self):
        model,module,host,target,board,wire = fixture()
        try:
            with redirect_stdout(io.StringIO()):
                host.check(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)  # only the deliberate last test
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_old_shared_host_helper_rejected_before_bus_access(self):
        model,module,host,target,board,wire = fixture()
        try:
            with patch.object(host.shared.Remote,'ack_wait_ms',None), self.assertRaisesRegex(RuntimeError,'updated rev_c_i2c_ssg_host'):
                host.check(object())
            self.assertEqual(wire.command_writes,0)
        finally:
            board.close()
            target.close()


if __name__ == '__main__':
    unittest.main()
