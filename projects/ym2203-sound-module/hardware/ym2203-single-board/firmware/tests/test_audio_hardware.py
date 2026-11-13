# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
from collections import deque

from test_firmware import Clock, fw, ROOT


def load_audio(clock):
    class Base:
        def __init__(self):
            self.running = False; self.sequence = self.deadline_misses = self.max_convert_us = 0
        def start(self): self.running = True; self.sequence = 0; self.started = clock.ticks_us()
    verified = types.SimpleNamespace(Stream=Base,BLOCK_US=11250,FDEBUG=0x50200008,RXSTALL=1,INPUT_FRAMES=625)
    spec = importlib.util.spec_from_file_location('firmware_audio',ROOT/'src/ym2203_audio.py')
    module = importlib.util.module_from_spec(spec); module.ptr32 = module.ptr16 = object
    with patch.dict(sys.modules,{'micropython':types.SimpleNamespace(viper=lambda f:f),'rev_c_fm_live':verified}):
        spec.loader.exec_module(module)
    module.time = clock
    return module


class DMA:
    def __init__(self): self.on = False; self.ctrl = 0
    def active(self): return self.on
    def config(self,**kwargs): pass


class AudioTests(unittest.TestCase):
    def test_complete_input_float_range_stays_inside_commissioned_output_cap(self):
        module = load_audio(Clock()); output = [0]*1080
        for exponent in range(1,8):
            for mantissa in (-512,-511,-257,-1,0,1,255,510,511):
                word = ((exponent << 10) | (mantissa+512)) << 19
                result = module.convert([word]*625,output)
                expected = (mantissa << (exponent-1)) // 8
                self.assertEqual(result >> 16,0); self.assertEqual(result & 65535,abs(expected))
                self.assertTrue(all(output[i] == expected & 65535 for i in range(0,1080,2)))
                self.assertTrue(all(output[i] == 0 for i in range(1,1080,2)))

    def test_invalid_exponent_and_random_interpolation_bounds(self):
        module = load_audio(Clock()); output = [0]*1080
        self.assertEqual(module.convert([0]*625,output) >> 16,1)
        rng = random.Random(2203)
        words = [((rng.randrange(1,8) << 10) | rng.randrange(1024)) << 19 for i in range(625)]
        result = module.convert(words,output)
        self.assertEqual(result >> 16,0)
        signed = [n if n < 32768 else n-65536 for n in output[::2]]
        self.assertTrue(all(-4096 <= n <= 4096 for n in signed))

    def test_rolling_deadline_and_DMA_parity_through24h_of_virtual_audio_blocks(self):
        clock = Clock(); module = load_audio(clock); stream = module.Stream()
        stream.mem32 = {module.verified.FDEBUG:0}; stream.dmas = [DMA(),DMA()]; stream.buffers = [None,None]
        stream.start()
        #7,680,000 blocks*11.25ms=24h. This executes deadline/release logic,
        # not physical audio or a24h wall-clock soak.
        for block in range(7680000):
            clock.us += 11250
            index = stream.sequence & 1
            stream.dmas[index].on = False; stream.dmas[1-index].on = True
            stream.release()
        self.assertEqual(clock.us,86400000000)
        self.assertEqual(stream.deadline_misses,0)
        self.assertEqual(stream.sequence,7680000 & 65535)

    def test_independent_YM_clock_drift_does_not_accumulate_false_deadlines(self):
        for period in (11240,11260):
            clock=Clock();module=load_audio(clock);stream=module.Stream()
            stream.mem32={module.verified.FDEBUG:0};stream.dmas=[DMA(),DMA()];stream.buffers=[None,None]
            stream.start()
            for unused in range(10000):
                clock.us+=period
                index=stream.sequence&1
                stream.dmas[index].on=False;stream.dmas[1-index].on=True
                stream.release()
            self.assertEqual(stream.deadline_misses,0)

    def test_deadline_DMA_stall_and_lost_ownership_fail_closed(self):
        clock = Clock(); module = load_audio(clock); stream = module.Stream()
        stream.mem32 = {module.verified.FDEBUG:0}; stream.dmas = [DMA(),DMA()]; stream.buffers = [None,None]
        stream.start(); clock.us = 22000
        with self.assertRaisesRegex(RuntimeError,'deadline'): stream.check()
        stream.start(); stream.mem32[module.verified.FDEBUG] = 1
        with self.assertRaisesRegex(RuntimeError,'stalled'): stream.check()
        stream.mem32[module.verified.FDEBUG] = 0; stream.dmas[0].ctrl = 1 << 29
        with self.assertRaisesRegex(RuntimeError,'DMA bus'): stream.check()
        stream.dmas[0].ctrl = 0
        with self.assertRaisesRegex(RuntimeError,'ownership'): stream.release()


def load_hardware():
    base = types.SimpleNamespace(RevCBus=object,I2S_OUTPUT_GPIO=(10,11,12),_check_platform=lambda:None,_emergency_stop=lambda:None)
    link = types.SimpleNamespace(Target=object,FIRST_BYTE=0x800,FIFO_ERRORS=0x0B,TX_ABRT=0x40,RD_REQ=0x20,RX_DONE=0x80,STOP_DET=0x200,RESTART_DET=0x1000)
    for i,name in enumerate(('IC_RAW_INTR_STAT','IC_TX_ABRT_SOURCE','IC_CLR_TX_ABRT','IC_RXFLR','IC_DATA_CMD','IC_CLR_RD_REQ','IC_CLR_RX_DONE','IC_CLR_STOP_DET','IC_CLR_RESTART_DET')): setattr(link,name,i)
    link.mem32 = {}
    spec = importlib.util.spec_from_file_location('firmware_hardware',ROOT/'src/ym2203_hw.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'machine':types.SimpleNamespace(Pin=object,I2S=object),'rev_c_bus_check':base,'rev_c_i2c_target_check':link,'rev_c_dac_check':object(),'rev_c_fm_live':object(),'ym2203_audio':object(),'ym2203_fw':fw,'ym2203_usb':types.SimpleNamespace(get_transport=lambda:None),'ym2203_midi':object()}):
        spec.loader.exec_module(module)
    return module,link


class HardwareTests(unittest.TestCase):
    def test_nonblocking_busy_address_latch_cancel_and_data_order(self):
        module,link = load_hardware(); bus = object.__new__(module.Board); bus.latched = -1
        states = iter((128,0,128,0,0,0)); calls = []
        bus.status = lambda:next(states); bus._write_port = lambda p,v:calls.append((p,v))
        self.assertFalse(bus.write_register(0xA0,1)); self.assertEqual(calls,[])
        self.assertFalse(bus.write_register(0xA0,1)); self.assertEqual(calls,[(0,0xA0)])
        self.assertTrue(bus.write_register(0xA0,1)); self.assertEqual(calls,[(0,0xA0),(1,1)])
        bus.latched = 0xA0; bus.cancel_write(); self.assertEqual(bus.latched,-1)
        self.assertTrue(bus.write_register(8,0)); self.assertEqual(calls[-2:],[(0,8),(1,0)])

    def test_status_burst_queued_before_RD_REQ_clear_and_RX_budget(self):
        module,link = load_hardware(); target = object.__new__(module.Target)
        from test_firmware import harness
        clock,board,engine = harness(); target.window = fw.Window(engine); target.flushes = 0
        target.window.receive(0x10,True)
        class Registers:
            def __init__(self): self.ops = []; self.rx = deque()
            def __getitem__(self,r):
                self.ops.append(('r',r))
                if r == link.IC_RAW_INTR_STAT: return link.RD_REQ
                if r == link.IC_RXFLR: return len(self.rx)
                if r == link.IC_DATA_CMD: return self.rx.popleft()
                return 0
            def __setitem__(self,r,v): self.ops.append(('w',r,v))
        regs = Registers(); link.mem32 = regs; target.poll()
        writes = [op for op in regs.ops if op[0] == 'w']
        self.assertEqual(len(writes),4)
        clear = regs.ops.index(('r',link.IC_CLR_RD_REQ))
        self.assertTrue(all(regs.ops.index(w) < clear for w in writes))
        regs.ops.clear(); regs.rx.extend([0x800]*40); target.poll()
        self.assertEqual(len(regs.rx),8)
        self.assertFalse(any(op[0] == 'w' for op in regs.ops))

    def test_application_boot_is_muted_and_interrupt_or_OOM_closes_every_resource(self):
        for failure in (KeyboardInterrupt,MemoryError):
            module,link = load_hardware(); events = []
            from test_firmware import Board,Clock
            clock = Clock(); board = Board(clock)
            board.arm = types.SimpleNamespace(value=lambda v:events.append(('arm',v)))
            board.initialize = lambda:events.append(('initialize',0))
            def close_board():
                events.append(('board-close',0))
                board.line_allow.value(0); board.dac_allow.value(0)
            board.close = close_board
            class Stream:
                def open(self): events.append(('stream-open',0))
                def start(self): events.append(('stream-start',0))
                def stop(self): events.append(('stream-stop',0))
                def close(self): events.append(('stream-close',0))
                def check(self): pass
            class Audio:
                TX,STEREO = 0,1
                def __init__(self,*args,**kwargs):
                    self.assert_muted = board.line_allow.level == board.dac_allow.level == 0
                    events.append(('audio-open',int(self.assert_muted)))
                def deinit(self): events.append(('audio-close',0))
            class Target:
                def __init__(self,engine):
                    self.engine = engine; self.window = fw.Window(engine)
                def prepare(self): events.append(('prepare',0))
                def _enable(self,n): events.append(('enable',n))
                def poll(self):
                    self.engine.set_gates(3)
                    raise failure('injected runtime failure')
                def close(self): events.append(('target-close',0))
            module.verified = types.SimpleNamespace(OUTPUT_FRAMES=540)
            module.dac = types.SimpleNamespace(_send=lambda *args:None)
            module.audio_core = types.SimpleNamespace(Stream=Stream,step=lambda *args:0)
            with patch.object(module,'Board',lambda:board),patch.object(module,'Pin',lambda n:n),patch.object(module,'I2S',Audio),patch.object(module,'Target',Target),redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(failure): module.run()
            self.assertIn(('audio-open',1),events)
            self.assertLess(events.index(('arm',0)),events.index(('board-close',0)))
            self.assertTrue(all((name,0) in events for name in ('stream-close','target-close','audio-close')))
            self.assertEqual((board.line_allow.level,board.dac_allow.level),(0,0))
            self.assertIn('SAFE:',output.getvalue())

    def test_application_MIDI_path_stops_USB_receive_on_interrupt(self):
        from test_midi import midi,usb,FakeUSB,Registers
        from test_firmware import Board,Clock
        module,link=load_hardware();clock=Clock();board=Board(clock);events=[]
        board.arm=types.SimpleNamespace(value=lambda v:events.append(('arm',v)))
        board.initialize=lambda:None
        def close_board():board.line_allow.value(0);board.dac_allow.value(0)
        board.close=close_board
        device=FakeUSB();transport=usb.Transport(device,2,3,clock,Registers(clock));device.transport=transport
        transport.open_cb(bytes((9,4,2,0,0,1,1,0,0)))
        class Stream:
            def open(self):pass
            def start(self):pass
            def stop(self):pass
            def close(self):events.append(('stream-close',0))
            def check(self):pass
        class Audio:
            TX,STEREO=0,1
            def __init__(self,*args,**kwargs):pass
            def deinit(self):events.append(('audio-close',0))
        class Target:
            def __init__(self,engine):self.window=fw.Window(engine);self.count=0
            def prepare(self):pass
            def _enable(self,n):pass
            def poll(self):
                self.count+=1
                if self.count==2:device.receive(bytes((9,0x90,60,100)))
                if self.count==35:raise KeyboardInterrupt('injected MIDI run interruption')
            def close(self):events.append(('target-close',0))
        def step(*args):clock.us+=11250;return 0
        module.verified=types.SimpleNamespace(OUTPUT_FRAMES=540)
        module.dac=types.SimpleNamespace(_send=lambda *args:None)
        module.audio_core=types.SimpleNamespace(Stream=Stream,step=step)
        module.usb_core=types.SimpleNamespace(get_transport=lambda:transport)
        module.midi_core=types.SimpleNamespace(Engine=lambda b:midi.Engine(b,clock),Controller=lambda e,t:midi.Controller(e,t,clock))
        link.IC_STATUS=999;link.mem32[999]=0
        with patch.object(module,'Board',lambda:board),patch.object(module,'Pin',lambda n:n),patch.object(module,'I2S',Audio),patch.object(module,'Target',Target),redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(KeyboardInterrupt):module.run()
        self.assertTrue(any(r==0x28 and v==0xF0 for t,r,v in board.calls))
        self.assertFalse(transport.enabled)
        self.assertEqual((board.line_allow.level,board.dac_allow.level),(0,0))
        self.assertTrue(all((name,0) in events for name in ('stream-close','target-close','audio-close')))
        self.assertIn('SAFE:',output.getvalue())


if __name__ == '__main__': unittest.main()
