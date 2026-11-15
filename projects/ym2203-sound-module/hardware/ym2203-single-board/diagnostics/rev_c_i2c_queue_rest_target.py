# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Nine500ms slots: melody-only rests preserve the three held companions."""
import gc
import rev_c_i2c_queue_mute_target as muted

queue, pitch, control, six = muted.queue, muted.pitch, muted.control, muted.six
SIGNATURE = b"RCQRS01!"
REST, APPEND_REST = 5, 9
REST_STATUS = 0x2A  # cumulative committed rest slots,then tone slots


class RestQueueTarget(muted.MutedQueueTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.rest_slots = self.tone_slots = self.rest_key_offs = self.resume_key_ons = 0
        self.played_score = bytearray(255 for unused in range(queue.CAPACITY * queue.RUN_LIMIT))
        self.slot_masks = bytearray(queue.CAPACITY * queue.RUN_LIMIT)

    def apply(self, command):
        if type(command) is int and command == APPEND_REST:
            if (self.active() or self.job != six.IDLE or self.pitch_command >= 0 or
                    self.mode or self.mask or self.applied or self.window.data[control.STATUS + 3]):
                raise RuntimeError("Rest upload requires fully stopped unexpired sources")
            if self.state != queue.IDLE or self.count >= queue.CAPACITY:
                raise ValueError("Clear first;rest score holds at most nine slots")
            self.score[self.count] = self.window.data[queue.SCORE + self.count] = REST
            self.count += 1
            self.window.data[queue.Q_COUNT] = self.count
            self.ack(command)
            return
        if type(command) is int and (command == queue.PLAY_FM or command == queue.PLAY_SSG):
            if self.count == queue.CAPACITY and (self.score[0] != 0 or self.score[-1] != 0):
                raise ValueError("Rest diagnostic requires first and last slot index0")
        muted.MutedQueueTarget.apply(self, command)

    def melody_mask(self):
        self.mask = self.applied
        self.window.data[six.VOICE_STATUS] = self.mask

    def write_note(self, index):
        note = self.score[index]
        if note == REST:
            self.write_at(self.voice, 0)
            self.melody_mask()
            self.rest_key_offs += 1
            return True
        if self.pair_step < 2:
            before = control.live.time.ticks_us()
            self.board.pitch_step(self.voice, note, self.pair_step)
            self.max_note_write_us = max(self.max_note_write_us,
                control.live.time.ticks_diff(control.live.time.ticks_us(), before))
            self.note_writes += 1
            self.pair_step += 1
            if self.pair_step < 2:
                return False
            # ARM must prime silence/companions before the inherited key-on.
            # A sounding legato note needs only its two pitch writes.
            if self.state == queue.ARMING or self.applied & (1 << self.voice):
                self.pair_step = 0
                self.window.data[pitch.PITCH_STATUS + self.voice] = note
                return True
            return False
        # After a rest,the two pitch writes and this key-on use separate
        # polls,so the existing one-register audio budget is maintained.
        self.write_at(self.voice, 1)
        self.melody_mask()
        self.resume_key_ons += 1
        self.pair_step = 0
        self.window.data[pitch.PITCH_STATUS + self.voice] = note
        return True

    def record_note(self, elapsed):
        muted.MutedQueueTarget.record_note(self, elapsed)
        slot = (self.runs - 1) * queue.CAPACITY + self.next_note - 1
        note = self.score[self.next_note - 1]
        self.played_score[slot] = note
        self.slot_masks[slot] = self.applied
        if note == REST: self.rest_slots += 1
        else: self.tone_slots += 1
        self.window.data[REST_STATUS] = self.rest_slots
        self.window.data[REST_STATUS + 1] = self.tone_slots

    def report(self):
        muted.MutedQueueTarget.report(self)
        print("REST QUEUE: tones=%d rests=%d rest_key_offs=%d resume_key_ons=%d pair_step=%d" %
              (self.tone_slots, self.rest_slots, self.rest_key_offs, self.resume_key_ons, self.pair_step))
        for run in range(self.runs):
            start = run * queue.CAPACITY
            print("REST SLOTS %d: score=%r masks=%r" %
                  (run + 1, list(self.played_score[start:start + queue.CAPACITY]),
                   list(self.slot_masks[start:start + queue.CAPACITY])))


def start_live(board, resources):
    if resources.stream.running:
        raise RuntimeError("Heap preflight requires capture stopped")
    pitch.check_bus_heap(board)
    print("STARTUP PASS: queued melody rests with held companions follows")
    target = RestQueueTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
            resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        print("SIX I2C: jobs=%d writes=%d pending=%d applied=%d" %
              (target.jobs, target.writes, target.job, target.applied))
        target.report()
    print("PASS: queued rests sent;max conversion=%d us,deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        six.staged.startup.run(bus_factory=pitch.PitchBus, resource_factory=six.SixResources,
            phase_names=six.staged.PHASES[:5] + ("QUIET SIX VOICES PREPARED",), after_phases=start_live,
            title="YM2203 Rev C / staged I2C queued melody rest target v1")
    finally:
        if not was_enabled: gc.disable()


if __name__ == "__main__": run()
