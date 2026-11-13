# SPDX-License-Identifier: MIT
"""Preset changes must yield to the unchanged native FM deadline checks."""
from collections import deque
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

from test_rev_c_fm_ssg_check import MixerModel
from test_rev_c_i2c_fm import ClockedStream, command_events
from test_rev_c_i2c_envelope import fixture, load


class EnvelopeBudgetTests(unittest.TestCase):
    def test_preset_ACK_is_deferred_and_at_most_one_register_written_per_poll(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            before=bytes(target.window.data[0x10:0x16])
            start=len(model.writes)
            target.apply(0x80)
            self.assertEqual(bytes(target.window.data[0x10:0x16]),before,
                             'preset must not ACK before its split work completes')
            self.assertEqual(len(model.writes),start)
            for step in range(8):
                previous=len(model.writes)
                target.poll()
                self.assertLessEqual(len(model.writes)-previous,1)
                if step<7: self.assertEqual(bytes(target.window.data[0x10:0x16]),before)
            self.assertEqual(len(model.writes)-start,8)
            self.assertEqual(bytes(target.window.data[0x10:0x16]),bytes((1,0x80,0,0,0,0)))
        finally:
            board.close(); target.close()

    def test_register_cost_plus_I2C_overhead_keep_native_guard_and_finish_all_updates(self):
        model=MixerModel(); module,host,values=load(model)
        staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
        def listen(endpoint): endpoint.window.finished=True
        original_prepare=module.EnvelopeTarget.prepare
        def prepare(endpoint):
            original_prepare(endpoint)
            commands=(8,0x80,1,0x31,0x30,0,0x81,1,0x31,0x30,0,0x80,7)
            regs.events=deque(event for command in commands for event in command_events(command,40))
        original_write=module.EnvelopeBus._write_tone
        original_poll=control.ControlTarget.poll
        def poll(endpoint):
            if model.stream and model.stream.running:
                model.us+=4000 # modeled I2C service/jitter, not a hardware measurement
            original_poll(endpoint)
        writes=[]
        def write(bus,register,value):
            if model.stream and model.stream.running:
                model.us+=2300 # artificial cost; not a measured hardware write latency
                writes.append(register)
            original_write(bus,register,value)
        with patch.object(startup,'listen',listen),patch.object(live,'Stream',lambda:ClockedStream(model,guard)),patch.object(module.EnvelopeTarget,'prepare',prepare),patch.object(module.EnvelopeBus,'_write_tone',write),patch.object(control.ControlTarget,'poll',poll),redirect_stdout(io.StringIO()) as output:
            module.run()
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertEqual(model.stream.deadline_misses,0)
        self.assertIn('DONE:',output.getvalue())
        self.assertEqual(sum(r in (0x60,0x80,0x64,0x84,0x68,0x88,0x6C,0x8C) for r in writes),24)
        model.assert_stopped()

    def test_preset_job_rejects_new_commands_before_its_single_ACK(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            target.apply(0x80)
            for command in (0x80,0x81,1,0x30,0x31,6,7):
                with self.assertRaisesRegex(RuntimeError,'pending'): target.apply(command)
            for unused in range(8): target.poll()
            self.assertEqual(target.window.data[0x10],1)
            self.assertEqual((target.preset_updates,target.preset_writes),(1,8))
            self.assertEqual(target.preset_command,-1)
        finally:
            board.close(); target.close()

    def test_active_I2C_frame_defers_last_register_and_ACK_commit(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            target.apply(0x80)
            for unused in range(7): target.poll()
            transport,regs=values[-3],values[-2]
            regs.values[transport.IC_STATUS]=0x40
            before=bytes(target.window.data[0x10:0x16])
            writes=len(model.writes)
            for unused in range(3): target.poll()
            self.assertEqual(bytes(target.window.data[0x10:0x16]),before)
            self.assertEqual(len(model.writes),writes)
            regs.values[transport.IC_STATUS]=0
            target.poll()
            self.assertEqual((target.preset_updates,target.preset_writes),(1,8))
            self.assertEqual(target.window.data[0x10],1)
        finally:
            board.close(); target.close()

    def test_split_register_policy_rejects_out_of_range_steps_without_writes(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            before=len(model.writes)
            for preset,index in ((-1,0),(2,0),(True,0),(0,-1),(0,8),(0,True),(1,1.0)):
                with self.assertRaises(ValueError): board.envelope_step(preset,index)
            self.assertEqual(len(model.writes),before)
        finally:
            board.close(); target.close()


if __name__=='__main__': unittest.main()
