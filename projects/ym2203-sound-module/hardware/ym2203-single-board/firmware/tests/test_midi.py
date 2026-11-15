# SPDX-License-Identifier: MIT
"""Real MIDI planner/USB adapter with a register/USB/SOF model,not physical USB."""
import math
import io
from contextlib import redirect_stdout
import sys
import types
import unittest
from unittest.mock import patch
from test_firmware import ROOT,fw,host,Clock,Board,load,frame,command,event

pitch=load('firmware_pitch',ROOT/'src/ym2203_pitch.py')
with patch.dict(sys.modules,{'ym2203_fw':fw,'ym2203_pitch':pitch}):
    midi=load('firmware_midi',ROOT/'src/ym2203_midi.py')

class FakeUSB:
    def __init__(self):self.pending=False;self.requests=0;self.transport=None
    def submit_xfer(self,ep,buffer):
        if self.pending:raise AssertionError('same endpoint rearmed before completion')
        self.pending=True;self.requests+=1;self.buffer=buffer;return True
    def receive(self,data,result=0,size=None):
        assert self.pending
        self.buffer[:len(data)]=data
        self.pending=False
        self.transport.xfer_cb(self.transport.ep,result,len(data) if size is None else size)

with patch.dict(sys.modules,{'machine':types.SimpleNamespace(USBDevice=FakeUSB,mem32={})}):
    usb=load('firmware_usb',ROOT/'src/ym2203_usb.py')

class Registers:
    def __init__(self,clock):self.clock=clock;self.frozen=None
    def __getitem__(self,address):
        assert address==usb.SOF_RD
        return (self.clock.us//1000)&2047 if self.frozen is None else self.frozen

class Harness:
    def __init__(self):
        self.clock=Clock();self.board=Board(self.clock)
        self.engine=midi.Engine(self.board,self.clock)
        self.device=FakeUSB();self.regs=Registers(self.clock)
        self.transport=usb.Transport(self.device,2,3,self.clock,self.regs)
        self.device.transport=self.transport
        self.control=midi.Controller(self.engine,self.transport,self.clock)
        self.transport.open_cb(bytes((9,4,2,0,0,1,1,0,0)))
        self.transport.start()
        self.clock.service=self.service
        self.clock.sleep_ms(12)
    def service(self,idle):
        before=len(self.board.calls)
        self.engine.poll(idle)
        self.control.poll()
        assert len(self.board.calls)-before<=1,'shared one-register budget exceeded'
    def send(self,data,wait=12):
        if not self.device.pending:self.clock.sleep_ms(12)
        self.device.receive(bytes(data))
        if wait:self.clock.sleep_ms(wait)
    def on(self,channel=0,note=60):self.send((9,0x90|channel,note,100))
    def off(self,channel=0,note=60):self.send((8,0x80|channel,note,0))


class DescriptorTests(unittest.TestCase):
    def test_CDC_prefix_interfaces_endpoints_jacks_lengths_and_strings(self):
        # CDC layout retained verbatim in the composite model,not just header.
        prefix=bytes.fromhex('09 02 4B 00 02 01 00 80 FA '
          '08 0B 00 02 02 02 00 04 09 04 00 00 01 02 02 00 04 '
          '05 24 00 20 01 05 24 01 00 01 04 24 02 02 05 24 06 00 01 '
          '07 05 81 03 08 00 10 09 04 01 00 02 0A 00 00 00 '
          '07 05 02 02 40 00 00 07 05 82 02 40 00 00')
        dev=bytes((18,1,0,2,239,2,1,64,0x8A,0x2E,5,0,0,1,1,2,3,1))
        builtin=types.SimpleNamespace(desc_dev=dev,desc_cfg=prefix,itf_max=2,ep_max=3,str_max=5)
        device,cfg,strings=usb.descriptors(builtin)
        self.assertEqual(device[8:12],dev[8:12]);self.assertEqual(device[:8],dev[:8])
        self.assertEqual(len(cfg),175);self.assertEqual(cfg[2]|cfg[3]<<8,len(cfg))
        self.assertEqual(cfg[4],4);self.assertEqual(cfg[5:9],prefix[5:9])
        self.assertEqual(cfg[9:len(prefix)],prefix[9:])
        records=[];index=len(prefix)
        while index<len(cfg):
            record=cfg[index:index+cfg[index]];self.assertTrue(record)
            records.append(record);index+=record[0]
        self.assertEqual(index,len(cfg))
        self.assertEqual(records[0],bytes((8,11,2,2,1,0,0,5)))
        self.assertEqual([r[2] for r in records if r[1]==4],[2,3])
        self.assertEqual([r[2] for r in records if r[1]==5],[3,131])
        self.assertTrue(all(r[4:6]==bytes((64,0)) for r in records if r[1]==5))
        header=next(r for r in records if r[0]==7 and r[1]==0x24)
        self.assertEqual(header[5]|header[6]<<8,65)
        self.assertEqual(strings[2],'YM2203 Rev C MIDI')

    def test_configure_keeps_CDC_and_callbacks_do_not_submit_transfers(self):
        builtin=types.SimpleNamespace(desc_dev=bytes((18,1,0,2,239,2,1,64,0x8A,0x2E,5,0,0,1,1,2,3,1)),desc_cfg=bytes((9,2,9,0,2,1,0,128,50)),itf_max=2,ep_max=3,str_max=5)
        class Device(FakeUSB):
            BUILTIN_DEFAULT=BUILTIN_CDC=builtin
            def active(self,state):self.active_value=state
            def config(self,*args,**kwargs):self.configuration=(args,kwargs)
        device=Device()
        with patch.object(usb,'USBDevice',lambda:device),patch.object(usb,'_transport',None),patch.object(usb,'_requested',False),patch.object(usb,'time',Clock()):
            transport=usb.configure()
            self.assertIs(device.builtin_driver,builtin);self.assertTrue(device.active_value)
            self.assertIs(usb.configure(),transport);self.assertEqual(device.requests,0)
            transport.open_cb(bytes((9,4,2,0,0,1,1,0,0)))
            self.assertEqual(device.requests,0)
            self.assertFalse(transport.enabled)


class BootTests(unittest.TestCase):
    def test_boot_USB_before_main_and_disable_file_skips_both(self):
        for disabled in (False,True):
            events=[]
            def stat(path):
                if not disabled:raise OSError(2)
                return (0,)*10
            modules={'os':types.SimpleNamespace(stat=stat),
              'time':types.SimpleNamespace(sleep_ms=lambda ms:events.append(('wait',ms))),
              'ym2203_usb':types.SimpleNamespace(configure=lambda:events.append(('usb',0))),
              'ym2203_hw':types.SimpleNamespace(run=lambda:events.append(('run',0)))}
            with patch.dict(sys.modules,modules),redirect_stdout(io.StringIO()):
                exec(compile((ROOT/'src/boot.py').read_text(),'target/boot.py','exec'),{})
                exec(compile((ROOT/'src/main.py').read_text(),'target/main.py','exec'),{})
            self.assertEqual(events,[] if disabled else [('usb',0),('wait',2000),('run',0)])

    def test_boot_storage_failure_is_not_mistaken_for_missing_disable_file(self):
        called=[]
        def stat(path):raise OSError(5)
        with patch.dict(sys.modules,{'os':types.SimpleNamespace(stat=stat),'ym2203_usb':types.SimpleNamespace(configure=lambda:called.append(1))}):
            with self.assertRaises(OSError):
                exec(compile((ROOT/'src/boot.py').read_text(),'target/boot.py','exec'),{})
        self.assertEqual(called,[])


class MidiTests(unittest.TestCase):
    def test_default_preset_is_quiet_and_all_registers_are_permitted(self):
        regs=list(midi.default_registers())
        self.assertEqual(len(regs),88)
        self.assertTrue(all(fw.valid_register(r,v) for r,v in regs))
        self.assertFalse(any(r==0x28 or r in (8,9,10) for r,v in regs))
        self.assertEqual([v for r,v in regs if r in (0x40,0x41,0x42)],[0,0,0])

    def test_pitch_tables_4MHz_A440_common_range_and_unsupported_edges(self):
        high,low,period=midi.pitch_tables()
        for note in range(24,97):
            fnum=((high[note]&7)<<8)|low[note];block=high[note]>>3
            hz=fnum*(4000000/144)*2**(block-20)
            expected=440*2**((note-69)/12)
            self.assertLess(abs(1200*math.log2(hz/expected)),3)
            self.assertTrue(1<=period[note]<=4095)
        self.assertEqual(high[127],255);self.assertEqual(period[0],0)

    def test_note_on_off_all_six_channels_and_one_write_budget(self):
        for voice in range(6):
            with self.subTest(voice=voice):
                h=Harness();h.on(voice);h.clock.sleep_ms(400)
                self.assertEqual(h.engine.midi_mask,1<<voice)
                self.assertTrue(h.control.owned);self.assertEqual(h.engine.gates,3)
                if voice<3:self.assertIn((0x28,0xF0|voice),[(r,v) for t,r,v in h.board.calls])
                else:self.assertEqual(h.board.regs[8+voice-3],7)
                h.off(voice);h.clock.sleep_ms(300)
                self.assertFalse(h.control.owned);self.assertEqual(h.engine.gates,0)
                self.assertEqual(h.engine.midi_mask,0)

    def test_USB_packet_buffer_is_not_rearmed_until_one_event_per_poll_consumed(self):
        h=Harness();data=[]
        for voice in range(6):data.extend((9,0x90|voice,60+voice,100))
        before=len(h.board.calls);requests=h.device.requests
        h.send(data,wait=0)
        self.assertEqual(len(h.board.calls),before)
        self.assertEqual(h.device.requests,requests)
        h.clock.sleep_ms(45)
        self.assertEqual(h.device.requests,requests)
        self.assertEqual(h.transport.count,24)
        h.clock.sleep_ms(600)
        self.assertEqual(h.engine.midi_mask,63)
        self.assertEqual(h.transport.count,0)
        self.assertGreater(h.device.requests,requests)
        self.assertEqual(len(h.transport.buffer),64)

    def test_long_note_does_not_require_MIDI_keepalive_and_SOF_wrap_is_safe(self):
        h=Harness();h.on();h.clock.sleep_ms(5000)
        self.assertTrue(h.control.owned);self.assertEqual(h.engine.gates,3)
        self.assertFalse(h.engine.expired)
        self.assertEqual(h.engine.expirations,0)

    def test_velocity_zero_and_stale_note_off_last_note_priority(self):
        h=Harness();h.on(note=60);h.clock.sleep_ms(400)
        h.on(note=64);h.off(note=60);h.clock.sleep_ms(150)
        self.assertEqual(h.control.notes[0],64);self.assertEqual(h.engine.midi_mask,1)
        h.send((9,0x90,64,0));h.clock.sleep_ms(300)
        self.assertEqual(h.engine.midi_mask,0);self.assertEqual(h.engine.gates,0)

    def test_I2C_busy_rejects_MIDI_without_replay_and_MIDI_busy_rejects_I2C(self):
        h=Harness();command(h.engine,fw.GATES,b'\x03')
        h.on();self.assertFalse(h.control.owned);self.assertEqual(h.control.rejected,1)
        command(h.engine,fw.STOP);h.clock.sleep_ms(300)
        self.assertFalse(h.control.owned)
        h.on();h.clock.sleep_ms(400)
        command(h.engine,fw.WRITE,b'\xA0\x01')
        self.assertEqual(h.engine.result,fw.BUSY)
        self.assertTrue(h.control.owned)
        command(h.engine,fw.STOP);h.clock.sleep_ms(150)
        self.assertFalse(h.control.owned);self.assertEqual(h.engine.gates,0)
        self.assertEqual(h.engine.result,fw.OK)

    def test_I2C_prefill_preserved_and_final_I2C_write_cannot_double_budget(self):
        h=Harness();command(h.engine,fw.PUSH,event(500,0xA0,1))
        h.on();self.assertEqual(h.engine.queue.count,1);self.assertFalse(h.control.owned)
        command(h.engine,fw.STOP);h.clock.sleep_ms(150)
        command(h.engine,fw.WRITE,b'\xA0\x01')
        h.send((9,0x90,60,100),wait=0);h.clock.sleep_ms(12)
        self.assertTrue(h.control.owned)  # Harness asserts total<=1

    def test_USB_SOF_loss_and_reset_mute_MIDI_but_not_I2C(self):
        for reset in (False,True):
            h=Harness();h.on();h.clock.sleep_ms(400)
            if reset:h.transport.reset_cb()
            else:h.regs.frozen=h.regs[usb.SOF_RD]
            h.clock.sleep_ms(350)
            self.assertFalse(h.control.owned);self.assertEqual(h.engine.gates,0)
        h=Harness();command(h.engine,fw.GATES,b'\x03')
        h.transport.reset_cb();h.clock.sleep_ms(150)
        self.assertEqual(h.engine.gates,3);self.assertTrue(h.engine.active)

    def test_CC123_channel_off_CC120_and_system_reset_global_panic(self):
        h=Harness();h.on(0);h.on(3);h.clock.sleep_ms(400)
        h.send((11,0xB0,123,0));h.clock.sleep_ms(100)
        self.assertEqual(h.engine.midi_mask,8)
        h.send((11,0xB3,120,0));h.clock.sleep_ms(150)
        self.assertEqual(h.engine.gates,0);self.assertFalse(h.control.owned)
        h.on();h.clock.sleep_ms(400);h.send((15,255,0,0));h.clock.sleep_ms(150)
        self.assertEqual(h.engine.gates,0)

    def test_invalid_packets_fail_closed_and_other_cables_channels_are_ignored(self):
        h=Harness();h.send((0x19,0x90,60,100));h.send((9,0x96,60,100))
        self.assertFalse(h.control.owned)
        h.on();h.clock.sleep_ms(400)
        h.send((9,0x80,60,1));h.clock.sleep_ms(150)
        self.assertEqual(h.engine.gates,0);self.assertEqual(h.control.invalid,1)
        h.on();h.clock.sleep_ms(400)
        h.device.receive(bytes((9,0x90,60)),size=3);h.clock.sleep_ms(150)
        self.assertEqual(h.engine.gates,0)

    def test_BUSY_note_replacement_cancels_address_without_resetting_timeout(self):
        h=Harness();h.on();h.clock.sleep_ms(400)
        h.board.blocked=True
        h.on(note=61);h.clock.sleep_ms(35)
        h.on(note=62);h.clock.sleep_ms(80)
        self.assertTrue(h.engine.failed);self.assertEqual(h.engine.gates,0)
        self.assertGreater(h.board.cancels,0)

    def test_MIDI_lifecycle_across_ticks_ms_wrap(self):
        h=Harness()
        h.clock.us=((1<<30)-100)*1000
        h.clock.next_tick=h.clock.us+11250
        h.on();h.clock.sleep_ms(500)
        self.assertTrue(h.control.owned)
        h.off();h.clock.sleep_ms(300)
        self.assertFalse(h.control.owned);self.assertEqual(h.engine.gates,0)

    def test_hot_stop_readonly_MIDI_extension_and_disabled_server_buffer(self):
        h=Harness();h.on();h.clock.sleep_ms(400)
        window=fw.Window(h.engine);window.receive(0x14,True)
        self.assertEqual(bytes(window.next_byte() for i in range(3)),bytes((1,1,1)))
        self.assertEqual(window.data[8:12],bytes((1,1,0,31)))
        h.transport.stop();h.device.receive(bytes((9,0x90,64,100)))
        self.assertEqual(h.transport.count,0)


if __name__=='__main__':unittest.main()
