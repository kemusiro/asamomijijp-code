# SPDX-License-Identifier: MIT
"""Measure first-C and following-D intervals from target command application."""
from contextlib import redirect_stdout
import io
import unittest

from test_rev_c_i2c_combined import fixture as combined_fixture
from test_rev_c_i2c_pitch import fixture as pitch_fixture


class NoteStartTests(unittest.TestCase):
    def test_combined_first_C_has_no_extra_setup_time(self):
        model,module,host,target,board,wire,values=combined_fixture()
        boundaries=[]
        original=target.apply
        def apply(command):
            original(command)
            if len(boundaries)<3 and (command==1 or command in (0x41,0x42)):
                boundaries.append(model.us)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            self.assertEqual(len(boundaries),3)
            first,second=(boundaries[1]-boundaries[0],boundaries[2]-boundaries[1])
            self.assertLessEqual(abs(first-second),22500,
                'first C=%dus; next D=%dus: setup or redundant C extends the first note' % (first,second))
        finally:
            board.close()
            target.close()

    def test_pitch_first_C_has_no_duplicate_pitch_after_gate_on(self):
        model,module,host,target,board,wire,values=pitch_fixture()
        boundaries=[]
        original=target.apply
        def apply(command):
            original(command)
            if len(boundaries)<3 and (command==1 or command in (0x41,0x42)):
                boundaries.append(model.us)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            first,second=(boundaries[1]-boundaries[0],boundaries[2]-boundaries[1])
            self.assertLessEqual(abs(first-second),22500,
                'first C=%dus; next D=%dus: redundant C extends the first note' % (first,second))
        finally:
            board.close()
            target.close()

    def test_all_four_pitch_scale_starts_match_their_following_note(self):
        model,module,host,target,board,wire,values=pitch_fixture()
        starts=[]
        original=target.apply
        def apply(command):
            previous=target.mode
            original(command)
            if command in (1,2) and previous==0 and len(starts)<4:
                starts.append([model.us])
            elif starts and len(starts[-1])<3 and command in (0x41,0x42,0x51,0x52):
                starts[-1].append(model.us)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            self.assertEqual(len(starts),4)
            for times in starts:
                self.assertEqual(len(times),3)
                self.assertLessEqual(abs((times[1]-times[0])-(times[2]-times[1])),22500)
        finally:
            board.close()
            target.close()

    def test_first_combined_pitch_and_timbre_are_ready_before_key_on(self):
        model,module,host,target,board,wire,values=combined_fixture()
        first=[]
        original=target.apply
        def apply(command):
            if command==1 and not first:
                self.assertEqual(target.mode,0)
                self.assertEqual(target.window.data[0x14:0x17],bytes((0,0,0)))
                self.assertEqual(model.level(19),0)
                self.assertEqual(model.level(26),0)
                first.append(True)
            original(command)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            self.assertEqual(first,[True])
        finally:
            board.close()
            target.close()

    def test_every_combined_scale_starts_with_a_separate_equal_length_C(self):
        model,module,host,target,board,wire,values=combined_fixture()
        starts=[]
        original=target.apply
        def apply(command):
            previous=target.mode
            original(command)
            if command==1 and previous==0 and len(starts)<4:
                starts.append([model.us])
            elif starts and len(starts[-1])<3 and command in (0x41,0x42):
                starts[-1].append(model.us)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            self.assertEqual(len(starts),4,'each scale needs a separate C onset')
            for index,times in enumerate(starts):
                self.assertEqual(len(times),3,'missing C/D/E boundary in scale %d' % (index+1))
                self.assertLessEqual(abs((times[1]-times[0])-(times[2]-times[1])),22500)
        finally:
            board.close()
            target.close()

    def test_combined_timbre_changes_are_all_silent_and_scales_have_gaps(self):
        model,module,host,target,board,wire,values=combined_fixture()
        original=target.apply
        stops=[]
        starts=[]
        parameters=[]
        def apply(command):
            previous=target.mode
            if 0x60<=command<=0x63 or 0x70<=command<=0x72:
                self.assertEqual(previous,0,'prepare each new timbre before sound')
                self.assertEqual(model.level(19),0)
                self.assertEqual(model.level(26),0)
                parameters.append(command)
            original(command)
            if command==0 and previous==1: stops.append(model.us)
            if command==1 and previous==0:
                if starts:
                    self.assertGreaterEqual(model.us-stops[-1],1000000)
                if len(starts)<4:
                    tl,multi=host.PRESETS[len(starts)]
                    self.assertEqual(target.window.data[0x14:0x17],bytes((tl,multi,0)))
                starts.append(model.us)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            self.assertEqual(len(starts),5) # four scales + final lease tone
            self.assertEqual(parameters,[c for tl,multi in host.PRESETS for c in (0x60+tl,0x70+multi)])
        finally:
            board.close()
            target.close()


if __name__=='__main__': unittest.main()
