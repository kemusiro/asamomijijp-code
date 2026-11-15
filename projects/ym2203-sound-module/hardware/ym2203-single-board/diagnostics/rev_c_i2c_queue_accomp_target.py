# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Queued solo melody plus three held opposite-family accompaniment voices."""
import gc
import rev_c_i2c_queue_target as queue

pitch, control, six = queue.pitch, queue.control, queue.six
SIGNATURE = b"RCQAC01!"
PLANNED_MASK = 0x28


class AccompaniedTarget(queue.QueueTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.full_mask = self.companions = self.arm_cursor = 0
        self.stop_cursor = -1
        self.all_off = False
        self.run_masks = bytearray(queue.RUN_LIMIT)

    def apply(self, command):
        queue.QueueTarget.apply(self, command)
        if command == queue.PLAY_FM or command == queue.PLAY_SSG:
            self.companions = 56 if self.voice == 0 else 7
            self.full_mask = (1 << self.voice) | self.companions
            self.arm_cursor = 0
            self.stop_cursor = -1
            self.all_off = False
            self.window.data[PLANNED_MASK] = self.full_mask
            self.run_masks[self.runs - 1] = self.full_mask
        elif command == queue.CLEAR:
            self.window.data[PLANNED_MASK] = 0

    def write_at(self, voice, enabled):
        before = control.live.time.ticks_us()
        self.board.voice(voice, enabled)
        self.max_write_us = max(self.max_write_us,
            control.live.time.ticks_diff(control.live.time.ticks_us(), before))
        self.writes += 1
        bit = 1 << voice
        self.applied = self.applied | bit if enabled else self.applied & ~bit

    def arm_step(self, idle):
        if not self.first_ready:
            if idle and self.write_note(0):
                self.first_ready = True
        elif self.arm_cursor < 6:
            if idle:
                while self.arm_cursor < 6 and not self.companions & (1 << self.arm_cursor):
                    self.arm_cursor += 1
                if self.arm_cursor < 6:
                    self.write_at(self.arm_cursor, 1)
                    self.arm_cursor += 1
                if self.arm_cursor == 6:
                    self.prime_left_q = six.poly.PRIME_BLOCKS
        elif self.prime_left_q:
            # FM accompaniment must already be stable in the output queue;
            # the melody itself stays keyed off until the common epoch.
            self.prime_left_q -= 1
        elif idle:
            self.write_at(self.voice, 1)
            self.mask = self.full_mask
            self.mode = 1
            self.window.data[six.VOICE_STATUS] = self.mask
            self.window.data[control.STATUS + 2] = 1
            self.board.dac_allow.value(1)
            self.board.line_allow.value(1)
            self.epoch = control.live.time.ticks_ms()
            self.state_to(queue.PLAYING)
            self.record_note(0)

    def drain_step(self, idle):
        if not self.all_off:
            if not idle:
                return
            if self.stop_cursor < 0:
                # End the melody at its deadline,then stop one companion per
                # poll. Keep the actual applied bits accurate for STOP/lease.
                self.write_at(self.voice, 0)
                self.run_off[self.runs - 1] = control.live.time.ticks_diff(
                    control.live.time.ticks_ms(), self.epoch)
                self.late_check(self.run_off[self.runs - 1], self.count * queue.NOTE_MS)
                self.stop_cursor = 0
            else:
                while self.stop_cursor < 6 and not self.applied & (1 << self.stop_cursor):
                    self.stop_cursor += 1
                if self.stop_cursor < 6:
                    self.write_at(self.stop_cursor, 0)
                    self.stop_cursor += 1
            if not self.applied:
                self.all_off = True
                self.mask = 0
                self.window.data[six.VOICE_STATUS] = 0
                self.off_at = control.live.time.ticks_ms()
            return
        # Both arrangements contain FM,so both need the existing output drain.
        if control.live.time.ticks_diff(control.live.time.ticks_ms(), self.off_at) >= queue.FM_DRAIN_MS:
            self.board.line_allow.value(0)
            self.board.dac_allow.value(0)
            self.mode = 0
            self.window.data[control.STATUS + 2] = 0
            self.run_end[self.runs - 1] = control.live.time.ticks_diff(control.live.time.ticks_ms(), self.epoch)
            self.completed += 1
            self.state_to(queue.DONE)

    def poll(self):
        now = control.live.time.ticks_ms()
        if self.state == queue.ARMING and control.live.time.ticks_diff(now, self.last_keep) >= control.LEASE_MS:
            self.set_mode(0)
            self.expirations += 1
            self.window.data[control.STATUS + 2] = 0
            self.window.data[control.STATUS + 3] = 1
        pitch.PitchTarget.poll(self)
        if self.job != six.IDLE or self.pitch_command >= 0 or not self.active():
            return
        idle = not control.link.mem32[control.link.IC_STATUS] & 0x40
        now = control.live.time.ticks_ms()
        if self.state == queue.ARMING:
            self.arm_step(idle)
            return
        if self.state == queue.PLAYING:
            elapsed = control.live.time.ticks_diff(now, self.epoch)
            due = self.next_note * queue.NOTE_MS
            if elapsed < due:
                return
            self.late_check(elapsed, due)
            if not idle:
                return
            if self.next_note < self.count:
                if self.write_note(self.next_note):
                    elapsed = control.live.time.ticks_diff(control.live.time.ticks_ms(), self.epoch)
                    self.late_check(elapsed, due)
                    self.record_note(elapsed)
                return
            self.state_to(queue.DRAINING)
            self.stop_cursor = -1
        if self.state == queue.DRAINING:
            self.drain_step(idle)

    def report(self):
        queue.QueueTarget.report(self)
        print("ACCOMP: run_masks=%r applied=%d arm_cursor=%d stop_cursor=%d" %
              (list(self.run_masks), self.applied, self.arm_cursor, self.stop_cursor))


def start_live(board, resources):
    if resources.stream.running:
        raise RuntimeError("Heap preflight requires capture stopped")
    pitch.check_bus_heap(board)
    print("STARTUP PASS: queued melody and held opposite-family chord follows")
    target = AccompaniedTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
            resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        print("SIX I2C: jobs=%d writes=%d pending=%d applied=%d" %
              (target.jobs, target.writes, target.job, target.applied))
        target.report()
    print("PASS: accompanied queue sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        six.staged.startup.run(bus_factory=pitch.PitchBus, resource_factory=six.SixResources,
            phase_names=six.staged.PHASES[:5] + ("QUIET SIX VOICES PREPARED",), after_phases=start_live,
            title="YM2203 Rev C / staged I2C accompanied queue target v1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__": run()
