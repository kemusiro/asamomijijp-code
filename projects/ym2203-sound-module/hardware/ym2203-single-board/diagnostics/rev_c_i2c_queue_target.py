# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Nine uploaded notes at fixed 500ms times; a bounded diagnostic scheduler."""
import gc
import rev_c_i2c_voice_pitch_target as pitch

control = pitch.control
six = pitch.six
SIGNATURE = b"RCQUE01!"
APPEND, CLEAR, PLAY_FM, PLAY_SSG = 0xA0, 0xA5, 0xA6, 0xA7
CAPACITY, RUN_LIMIT, NOTE_MS, MAX_LATE_MS = 9, 3, 500, 100
FM_DRAIN_MS = 135
Q_COUNT, Q_STATE, Q_NEXT, Q_VOICE, SCORE = 0x1C, 0x1D, 0x1E, 0x1F, 0x30
IDLE, ARMING, PLAYING, DRAINING, DONE, ABORTED = range(6)


class QueueTarget(pitch.PitchTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.window.data[Q_VOICE] = 255
        self.score = bytearray(CAPACITY)
        self.count = self.state = self.next_note = 0
        self.voice = 255
        self.pair_step = self.prime_left_q = self.epoch = self.off_at = 0
        self.first_ready = False
        self.runs = self.completed = self.aborted = self.events = self.note_writes = 0
        self.partial_cancels = self.max_late_ms = self.max_note_write_us = 0
        self.times = [-1] * (CAPACITY * RUN_LIMIT)
        self.run_voices = bytearray(RUN_LIMIT)
        self.run_states = bytearray(RUN_LIMIT)
        self.run_notes = bytearray(RUN_LIMIT)
        self.run_off = [-1] * RUN_LIMIT
        self.run_end = [-1] * RUN_LIMIT

    def active(self):
        return ARMING <= self.state <= DRAINING

    def state_to(self, state):
        self.state = state
        self.window.data[Q_STATE] = state
        if self.runs:
            self.run_states[self.runs - 1] = state

    def ack(self, command):
        data = self.window.data
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = command
        data[control.STATUS + 2] = self.mode

    def cancel(self):
        if self.active():
            if self.pair_step:
                self.partial_cancels += 1
            self.pair_step = 0
            self.run_end[self.runs - 1] = (control.live.time.ticks_diff(
                control.live.time.ticks_ms(), self.epoch) if self.next_note else 0)
            self.state_to(ABORTED)
            self.aborted += 1

    def set_mode(self, mode):
        self.cancel()
        pitch.PitchTarget.set_mode(self, mode)

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Queue command must be an integer")
        if command in (control.STOP, control.FINISH):
            self.cancel()
            return pitch.PitchTarget.apply(self, command)
        if command == control.KEEP:
            if self.active():
                # Autonomous events NEVER renew this host-owned lease.
                self.last_keep = control.live.time.ticks_ms()
            return pitch.PitchTarget.apply(self, command)
        if self.active():
            raise RuntimeError("Queue active; only KEEP/STOP/FINISH allowed")
        if command == control.START:
            return pitch.PitchTarget.apply(self, command)
        if command not in (CLEAR, PLAY_FM, PLAY_SSG) and not APPEND <= command < APPEND + 5:
            raise ValueError("Unsupported queue diagnostic command")
        if self.job != six.IDLE or self.pitch_command >= 0 or self.mode or self.mask or self.applied:
            raise RuntimeError("Queue setup requires fully stopped sources")
        if self.window.data[control.STATUS + 3]:
            raise RuntimeError("Clear the expired lease with explicit STOP")
        data = self.window.data
        if command == CLEAR:
            self.count = self.next_note = 0
            self.voice = 255
            data[Q_COUNT] = data[Q_NEXT] = 0
            data[Q_VOICE] = 255
            self.state = IDLE
            data[Q_STATE] = IDLE
        elif APPEND <= command < APPEND + 5:
            if self.state != IDLE or self.count >= CAPACITY:
                raise ValueError("Clear first; queue holds at most nine notes")
            note = command - APPEND
            self.score[self.count] = data[SCORE + self.count] = note
            self.count += 1
            data[Q_COUNT] = self.count
        else:
            if not self.live_started or self.count != CAPACITY or self.runs >= RUN_LIMIT:
                raise RuntimeError("PLAY requires START,nine notes,and fewer than three runs")
            self.voice = 0 if command == PLAY_FM else 3
            self.run_voices[self.runs] = self.voice
            self.runs += 1
            self.next_note = self.pair_step = self.prime_left_q = 0
            self.first_ready = False
            data[Q_NEXT], data[Q_VOICE] = 0, self.voice
            self.last_keep = control.live.time.ticks_ms()
            self.state_to(ARMING)
        self.ack(command)

    def write_note(self, index):
        before = control.live.time.ticks_us()
        self.board.pitch_step(self.voice, self.score[index], self.pair_step)
        self.max_note_write_us = max(self.max_note_write_us,
            control.live.time.ticks_diff(control.live.time.ticks_us(), before))
        self.note_writes += 1
        self.pair_step += 1
        if self.pair_step == 2:
            self.pair_step = 0
            self.window.data[pitch.PITCH_STATUS + self.voice] = self.score[index]
            return True
        return False

    def write_voice(self, enabled):
        before = control.live.time.ticks_us()
        self.board.voice(self.voice, enabled)
        self.max_write_us = max(self.max_write_us,
            control.live.time.ticks_diff(control.live.time.ticks_us(), before))
        self.writes += 1

    def record_note(self, elapsed):
        late = elapsed - self.next_note * NOTE_MS
        self.max_late_ms = max(self.max_late_ms, late)
        self.times[(self.runs - 1) * CAPACITY + self.next_note] = elapsed
        self.next_note += 1
        self.events += 1
        self.run_notes[self.runs - 1] = self.next_note
        self.window.data[Q_NEXT] = self.next_note

    def late_check(self, elapsed, due):
        if elapsed - due > MAX_LATE_MS:
            self.set_mode(0)
            raise RuntimeError("Queued event late by more than100ms; audio stopped")

    def poll(self):
        now = control.live.time.ticks_ms()
        if self.state == ARMING and control.live.time.ticks_diff(now, self.last_keep) >= control.LEASE_MS:
            self.set_mode(0)
            self.expirations += 1
            self.window.data[control.STATUS + 2] = 0
            self.window.data[control.STATUS + 3] = 1
        pitch.PitchTarget.poll(self)
        if self.job != six.IDLE or self.pitch_command >= 0 or not self.active():
            return
        idle = not control.link.mem32[control.link.IC_STATUS] & 0x40
        now = control.live.time.ticks_ms()
        if self.state == ARMING:
            if not self.first_ready:
                if idle and self.write_note(0):
                    self.first_ready = True
                    self.prime_left_q = six.poly.PRIME_BLOCKS
            elif self.prime_left_q:
                # Prime SILENCE before key-on, not the first sounding C.
                self.prime_left_q -= 1
            elif idle:
                self.write_voice(1)
                self.mask = self.applied = 1 << self.voice
                self.mode = 1
                self.window.data[six.VOICE_STATUS] = self.mask
                self.window.data[control.STATUS + 2] = 1
                self.board.dac_allow.value(1 if self.voice < 3 else 0)
                self.board.line_allow.value(1)
                self.epoch = control.live.time.ticks_ms()
                self.state_to(PLAYING)
                self.record_note(0)
            return
        elapsed = control.live.time.ticks_diff(now, self.epoch)
        if self.state == PLAYING:
            due = self.next_note * NOTE_MS
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
            else:
                self.write_voice(0)
                self.applied = self.mask = 0
                self.window.data[six.VOICE_STATUS] = 0
                self.off_at = control.live.time.ticks_ms()
                self.run_off[self.runs - 1] = control.live.time.ticks_diff(self.off_at, self.epoch)
                self.state_to(DRAINING)
        if self.state == DRAINING:
            drain = FM_DRAIN_MS if self.voice < 3 else 0
            if control.live.time.ticks_diff(control.live.time.ticks_ms(), self.off_at) >= drain:
                self.board.line_allow.value(0)
                self.board.dac_allow.value(0)
                self.mode = 0
                self.window.data[control.STATUS + 2] = 0
                self.run_end[self.runs - 1] = control.live.time.ticks_diff(control.live.time.ticks_ms(), self.epoch)
                self.completed += 1
                self.state_to(DONE)

    def report(self):
        print("QUEUE: runs=%d completed=%d aborted=%d events=%d pitch_writes=%d partial_cancels=%d max_late_ms=%d max_write_us=%d" %
              (self.runs, self.completed, self.aborted, self.events, self.note_writes,
               self.partial_cancels, self.max_late_ms, self.max_note_write_us))
        for run in range(self.runs):
            start = run * CAPACITY
            print("QUEUE RUN %d: voice=%d state=%d notes=%d times_ms=%r note_off_ms=%d end_ms=%d" %
                  (run + 1, self.run_voices[run], self.run_states[run], self.run_notes[run],
                   self.times[start:start + CAPACITY], self.run_off[run], self.run_end[run]))


def start_live(board, resources):
    if resources.stream.running:
        raise RuntimeError("Heap preflight requires capture stopped")
    pitch.check_bus_heap(board)
    print("STARTUP PASS: nine-note upload/queue control follows")
    target = QueueTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
            resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        print("SIX I2C: jobs=%d writes=%d pending=%d applied=%d" %
              (target.jobs, target.writes, target.job, target.applied))
        target.report()
    print("PASS: queued sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        six.staged.startup.run(bus_factory=pitch.PitchBus, resource_factory=six.SixResources,
            phase_names=six.staged.PHASES[:5] + ("QUIET SIX VOICES PREPARED",), after_phases=start_live,
            title="YM2203 Rev C / staged I2C nine-note queue target v1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
