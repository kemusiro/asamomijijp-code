# SPDX-License-Identifier: MIT
"""Handover HOST with actual I2C engine,MIDI planner and USB receive model."""
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from test_firmware import ROOT,Wire,fw,host,load
from test_midi import midi,usb,FakeUSB,Registers


class CombinedWire(Wire):
    def __init__(self,stretch=5000,recover=True):
        super().__init__()
        self.engine=midi.Engine(self.board,self.clock);self.window=fw.Window(self.engine)
        self.device=FakeUSB();self.regs=Registers(self.clock)
        self.transport=usb.Transport(self.device,2,3,self.clock,self.regs);self.device.transport=self.transport
        self.control=midi.Controller(self.engine,self.transport,self.clock)
        self.transport.open_cb(bytes((9,4,2,0,0,1,1,0,0)));self.transport.start()
        self.stretch=stretch;self.actor=False;self.attempted=False;self.recovered=False
        self.recover=recover;self.recover_at=None;self.events=[]
        self.clock.sleep_ms(12)
    def chord(self,offset=0):
        data=[]
        for channel,note in enumerate((60,64,67,48,52,55)):
            data.extend((9,0x90|channel,note+offset,100))
        self.device.receive(bytes(data))
    def service(self,idle):
        before=len(self.board.calls)
        super().service(idle)
        self.control.poll()
        assert len(self.board.calls)-before<=1
        if len(self.board.calls)!=before:self.clock.us+=4400
        if self.actor and self.engine.active and not self.attempted and self.device.pending:
            self.events.append((self.clock.us,'MIDI during I2C'))
            self.chord(2);self.attempted=True
        if self.actor and self.attempted and not self.engine.active:
            if self.recover_at is None:self.recover_at=self.clock.us+6000000
            if self.recover and not self.recovered and self.clock.us>=self.recover_at and self.device.pending:
                self.events.append((self.clock.us,'explicit MIDI recovery'))
                self.chord();self.recovered=True
    def writeto(self,address,data):
        self.clock.advance(self.stretch,False)
        return super().writeto(address,data)
    def readfrom(self,address,count):
        self.clock.advance(self.stretch,False)
        return super().readfrom(address,count)


def program(wire):
    with patch.dict(sys.modules,{'machine':types.SimpleNamespace(Pin=lambda n:n,I2C=lambda *a,**k:wire),'ym2203_revc':host}):
        module=load('handover_program',ROOT/'host/midi_handover.py')
    module.time=wire.clock
    return module


class HandoverTests(unittest.TestCase):
    def test_full_HOST_attaches_without_STOP_then_exercises_both_source_directions(self):
        for stretch in (5000,30000):
            with self.subTest(stretch=stretch):
                wire=CombinedWire(stretch);wire.chord();wire.clock.sleep_ms(500);wire.actor=True
                module=program(wire)
                with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:module.main()
                report=output.getvalue()
                self.assertIn('I2C WRITE rejected BUSY',report)
                self.assertIn('4s read-only quiet',report)
                self.assertIn('explicit six-voice MIDI recovery',report)
                self.assertIn('HOST PASS:',report);self.assertIn('DONE:',report)
                frames=[data for data in wire.transfers if len(data)==17 and data[0]==0x40]
                self.assertEqual(frames[0][3],host.WRITE)  # constructor must not hide MIDI ownership
                self.assertNotIn((0xA0,0),[(r,v) for t,r,v in wire.board.calls])
                self.assertTrue(wire.attempted and wire.recovered)
                self.assertEqual(wire.control.rejected,6)
                self.assertEqual((wire.engine.expirations,wire.engine.gates,wire.engine.midi_mask),(0,0,0))
                self.assertFalse(wire.control.owned);self.assertFalse(wire.engine.failed)
                self.assertEqual(wire.board.regs[8:11],bytes((0,0,0)))

    def test_missing_explicit_MIDI_recovery_times_out_without_success_or_replay(self):
        wire=CombinedWire(recover=False);wire.chord();wire.clock.sleep_ms(500);wire.actor=True
        module=program(wire)
        with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError,'timed out'):module.main()
        self.assertTrue(wire.attempted);self.assertFalse(wire.recovered)
        self.assertNotIn('HOST PASS:',output.getvalue())
        self.assertEqual((wire.engine.gates,wire.engine.midi_mask),(0,0))

    def test_wrong_identity_sends_no_commands_and_missing_initial_MIDI_fails_closed(self):
        for wrong_identity in (False,True):
            with self.subTest(wrong_identity=wrong_identity):
                wire=CombinedWire()
                if wrong_identity:wire.window.data[0]=0
                module=program(wire)
                with patch.object(host,'time',wire.clock),redirect_stdout(io.StringIO()) as output:
                    with self.assertRaises(RuntimeError):module.main()
                frames=[data for data in wire.transfers if len(data)==17 and data[0]==0x40]
                self.assertEqual(len(frames),0 if wrong_identity else 1)
                self.assertTrue(all(data[3]==host.STOP for data in frames))
                self.assertNotIn('HOST PASS:',output.getvalue())
                self.assertEqual(wire.engine.gates,0)


if __name__=='__main__':unittest.main()
