# SPDX-License-Identifier: MIT
"""Final HOST-main integration with actual alpha.2 engine;GPIO/audio modelled."""
from contextlib import redirect_stdout
import io
import sys
import types
import unittest
from unittest.mock import patch
from test_firmware import ROOT,Wire,host,load


class RecoveryWire(Wire):
    def __init__(self,stretch=5000):
        super().__init__()
        self.stretch=stretch;self.binds=[];self.pins=[];self.traffic=[]
    def service(self,idle):
        before=len(self.board.calls)
        super().service(idle)
        if len(self.board.calls)!=before:self.clock.us+=4400
    def writeto(self,address,data):
        self.traffic.append((self.clock.us,'w',bytes(data)))
        self.clock.advance(self.stretch,False)
        return super().writeto(address,data)
    def readfrom(self,address,count):
        self.traffic.append((self.clock.us,'r',count))
        self.clock.advance(self.stretch,False)
        return super().readfrom(address,count)


def load_program(wire):
    class Pin:
        IN=0
        def __init__(self,n,mode=None,pull=None):
            if mode is not None:wire.pins.append((wire.clock.us,n,mode,pull))
    def bind(*args,**kwargs):
        wire.binds.append(wire.clock.us)
        return wire
    machine=types.SimpleNamespace(Pin=Pin,I2C=bind)
    with patch.dict(sys.modules,{'machine':machine,'ym2203_revc':host}):
        program=load('firmware_recovery',ROOT/'host/recovery.py')
    program.time=wire.clock
    return program


class RecoveryTests(unittest.TestCase):
    def test_full_main_STOP_readonly_quiet_rebind_expiry_and_recovery(self):
        for stretch in (5000,30000):
            with self.subTest(stretch=stretch):
                wire=RecoveryWire(stretch);program=load_program(wire)
                with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
                    program.main()
                report=output.getvalue()
                for label in ('1/4 PASS','2/4 PASS','3/4 PASS','4/4 PASS','HOST PASS:','DONE:'):
                    self.assertIn(label,report)
                self.assertIn('result=5 flags=33 queued=0',report)
                self.assertEqual(len(wire.binds),2)
                self.assertEqual([(n,mode,pull) for t,n,mode,pull in wire.pins],[(0,0,None),(1,0,None)])
                released=wire.pins[0][0];rebound=wire.binds[1]
                self.assertEqual(rebound-released,1800000)
                self.assertFalse(any(released<=t<rebound for t,k,d in wire.traffic))
                commits=[(t,d) for t,k,d in wire.traffic if k=='w' and len(d)==17 and d[0]==0x40]
                self.assertEqual(sum(d[3]==host.PLAY for t,d in commits),4)
                stop_before=max(t for t,d in commits if t<released and d[3]==host.STOP)
                stop_after=min(t for t,d in commits if t>rebound and d[3]==host.STOP)
                self.assertGreaterEqual(stop_after-rebound,4000000)
                # No command,including KEEP or STOP,can hide the lease on rebind.
                self.assertFalse(any(released<=t<stop_after for t,d in commits))
                plays=[t for t,d in commits if d[3]==host.PLAY]
                stop_one=min(t for t,d in commits if plays[0]<t<plays[1] and d[3]==host.STOP)
                writes_after_stop=[t for t,d in commits if stop_one<t<plays[1] and d[3] in (host.WRITE,host.PUSH)]
                self.assertGreaterEqual(min(writes_after_stop)-stop_one,4000000)
                self.assertEqual((wire.engine.expirations,wire.engine.gates,wire.engine.queue.count),(1,0,0))
                self.assertFalse(wire.engine.failed)
                self.assertEqual(wire.engine.status[1:],bytes((0,1,0)))
                self.assertEqual(wire.board.regs[8:11],bytes((0,0,0)))
                # Both full plays must reproduce the entire registered score.
                for start,end in ((plays[1],plays[2]),(plays[3],wire.clock.us)):
                    actual=[(r,v) for t,r,v in wire.board.calls if start<t<end]
                    expected=[(r,v) for d,r,v in program.events()]
                    self.assertEqual(actual[:len(expected)],expected)

    def test_corrupt_reattachment_identity_expiry_or_sequence_never_replays(self):
        for corruption in ('identity','expiry','sequence'):
            with self.subTest(corruption=corruption):
                class CorruptWire(RecoveryWire):
                    corrupted=False
                    def readfrom(self,address,count):
                        data=super().readfrom(address,count)
                        if len(self.binds)==2 and not self.corrupted and ((corruption=='identity' and count==8) or (corruption!='identity' and count==4)):
                            data=bytearray(data)
                            if corruption=='identity':data[0]^=1
                            elif corruption=='expiry':data[2]&=~32
                            else:data[0]^=1
                            self.corrupted=True
                            return bytes(data)
                        return data
                wire=CorruptWire();program=load_program(wire)
                with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
                    with self.assertRaises(RuntimeError):program.main()
                self.assertTrue(wire.corrupted)
                self.assertNotIn('HOST PASS:',output.getvalue())
                plays=[d for d in wire.transfers if len(d)==17 and d[0]==0x40 and d[3]==host.PLAY]
                self.assertEqual(len(plays),3)
                self.assertEqual((wire.engine.gates,wire.engine.queue.count),(0,0))

    def test_interruption_while_HOST_pins_released_rebinds_and_stops_without_replay(self):
        wire=RecoveryWire();program=load_program(wire)
        original_sleep=wire.clock.sleep_ms
        def interrupted_sleep(ms):
            if ms==program.RELEASE_MS:
                original_sleep(300)
                raise KeyboardInterrupt('injected HOST interruption during release')
            original_sleep(ms)
        wire.clock.sleep_ms=interrupted_sleep
        with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(KeyboardInterrupt):program.main()
        self.assertEqual(len(wire.binds),2)
        self.assertEqual((wire.engine.gates,wire.engine.queue.count),(0,0))
        self.assertEqual(wire.engine.expirations,0)
        self.assertNotIn('HOST PASS:',output.getvalue())


if __name__ == '__main__':unittest.main()
