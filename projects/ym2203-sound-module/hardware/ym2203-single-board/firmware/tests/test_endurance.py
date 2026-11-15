# SPDX-License-Identifier: MIT
"""Finite target-time score and actual host-main integration;physical audio modelled."""
from contextlib import redirect_stdout
import io
import sys
import types
import unittest
from unittest.mock import patch
from test_firmware import ROOT,Wire,host,load


def load_program(wire):
    machine = types.SimpleNamespace(Pin=lambda n:n,I2C=lambda *a,**k:wire)
    with patch.dict(sys.modules,{'machine':machine,'ym2203_revc':host}):
        return load('firmware_endurance',ROOT/'host/endurance.py')


class EnduranceTests(unittest.TestCase):
    def test_score_duration_boundaries_rests_and_companions(self):
        program = load_program(Wire())
        score = list(program.events())
        self.assertEqual(len(score),726)
        self.assertEqual(sum(delay for delay,reg,value in score),180000)
        self.assertEqual(score[:3],[(0,8,7),(0,9,7),(0,10,7)])
        self.assertEqual(score[-3:],[(500,8,0),(0,9,0),(0,10,0)])
        self.assertEqual(sum(reg==0x28 and value==0 for delay,reg,value in score),144)
        self.assertEqual(sum(reg==0x28 and value==0x10 for delay,reg,value in score),144)
        self.assertFalse(any(reg in (8,9,10) for delay,reg,value in score[3:-3]))
        self.assertEqual(sum(delay==500 for delay,reg,value in score),360)

    def test_full_HOST_main_streams726_events_and_reports_only_after_elapsed_time(self):
        for stretch in (5000,30000):
            with self.subTest(stretch_us=stretch):
                class StretchedWire(Wire):
                    def service(self,idle):
                        before = len(self.board.calls)
                        super().service(idle)
                        if len(self.board.calls)!=before:self.clock.us+=4400
                    def writeto(self,address,data):
                        self.clock.advance(stretch,False)
                        return super().writeto(address,data)
                    def readfrom(self,address,count):
                        self.clock.advance(stretch,False)
                        return super().readfrom(address,count)
                wire = StretchedWire();program = load_program(wire);program.time=wire.clock
                with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
                    program.main()
                report = output.getvalue()
                self.assertIn('STREAM COMPLETE events=726 score_ms=180000',report)
                self.assertIn('HOST PASS:',report);self.assertIn('DONE:',report)
                for n in range(1,7):
                    self.assertEqual(report.count('STREAM %d/6 ' % n),1)
                self.assertEqual(wire.engine.executed,726)
                self.assertEqual((wire.engine.expirations,wire.engine.gates),(0,0))
                self.assertFalse(wire.engine.failed);self.assertLessEqual(wire.engine.max_late,100)
                self.assertEqual(wire.engine.status[1:],bytes((0,1,0)))
                self.assertEqual(wire.board.regs[8:11],bytes((0,0,0)))
                frames = [d for d in wire.transfers if len(d)==17 and d[0]==0x40]
                seqs = [d[2] for d in frames]
                self.assertGreater(len(frames),256)
                self.assertIn((255,0),list(zip(seqs,seqs[1:])))

    def test_HOST_interruption_or_transfer_failure_stops_without_replay_or_success_banner(self):
        for failure in (KeyboardInterrupt,OSError):
            with self.subTest(failure=failure):
                class FailingWire(Wire):
                    raised = False
                    def readfrom(self,address,count):
                        if not self.raised and self.engine.executed>=50:
                            self.raised=True
                            raise failure('injected transfer/interruption')
                        return super().readfrom(address,count)
                wire=FailingWire();program=load_program(wire);program.time=wire.clock
                with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
                    with self.assertRaises(failure):program.main()
                self.assertTrue(wire.raised)
                self.assertNotIn('HOST PASS:',output.getvalue())
                self.assertNotIn('STREAM COMPLETE',output.getvalue())
                self.assertEqual(wire.engine.queue.count,0)
                self.assertEqual(wire.engine.gates,0)
                self.assertEqual(wire.board.regs[8:11],bytes((0,0,0)))
                plays=[d for d in wire.transfers if len(d)==17 and d[0]==0x40 and d[3]==host.PLAY]
                self.assertEqual(len(plays),1)


if __name__ == '__main__':unittest.main()
