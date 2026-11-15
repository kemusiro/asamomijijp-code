# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Fixed six-voice masks; one voice register per poll, then muted priming."""
import gc
import rev_c_i2c_fm_staged_target as staged
import rev_c_six_voice_check as poly


control = staged.control
SIGNATURE = b"RCSIX01!"
MASK_BASE = 0x40
VOICE_STATUS, BUSY_STATUS = 0x14, 0x15
IDLE, EXPIRED = -1, -2


class SixBus(poly.SixVoiceBus):
    def voice(self, index, enabled):
        if type(index) is not int or not 0 <= index < 6 or type(enabled) is not int or enabled not in (0, 1):
            raise ValueError("Choose voice0..5 and enabled0/1")
        if index < 3:
            self._write_three(0x28, index | (0x10 if enabled else 0))
        else:
            self.checked(8 + index - 3, poly.BASS_LEVEL if enabled else 0)


class SixResources(staged.startup.Resources):
    def setup(self, phase):
        if phase == 5:
            self.board.configure_three()
            self.board.bass()
            for register in (8, 9, 10):
                self.board.checked(register, 0)
            control.live._send(self.audio, self.silence, 200)
        else:
            super().setup(phase)


class SixTarget(control.ControlTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.applied = self.desired = self.cursor = self.prime_left = 0
        self.job = IDLE
        self.jobs = self.writes = self.max_write_us = 0

    def _begin(self, mask, command):
        self.board.line_allow.value(0)
        self.board.dac_allow.value(0)
        self.mode = 0
        self.desired, self.job = mask, command
        self.cursor = self.prime_left = 0
        self.window.data[BUSY_STATUS] = 1

    def set_mode(self, mode):
        # Called by the inherited lease check. Close gates immediately; chip
        # key/volume cleanup is subsequently split across audio blocks.
        if type(mode) is not int or mode != 0:
            raise ValueError("Use a bounded voice-mask command")
        self._begin(0, EXPIRED)
        self.mask = 0
        self.window.data[VOICE_STATUS] = 0

    def _gates(self):
        self.board.dac_allow.value(1 if self.mask & 7 and self.mode != control.DAC_MUTE else 0)
        self.board.line_allow.value(1 if self.mask and self.mode != control.LINE_MUTE else 0)

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Six-voice command must be an integer")
        if self.job != IDLE:
            raise RuntimeError("Voice update pending; wait for its ACK")
        if command in (control.START, control.KEEP):
            return control.ControlTarget.apply(self, command)
        if command in (control.STOP, control.FINISH):
            self._begin(0, command)
            return
        if MASK_BASE <= command < MASK_BASE + 64:
            if not self.live_started or self.window.data[control.STATUS + 3]:
                raise RuntimeError("Voice mask requires START and a non-expired session")
            self._begin(command - MASK_BASE, command)
            return
        if command not in (control.BOTH, control.DAC_MUTE, control.LINE_MUTE):
            raise ValueError("Unsupported six-voice diagnostic command")
        if not self.live_started or not self.mask or self.window.data[control.STATUS + 3]:
            raise RuntimeError("Mute/restore requires active unexpired voices")
        self.board.line_allow.value(0)
        self.mode = 1 if command == control.BOTH else command
        self._gates()
        self.last_keep = control.live.time.ticks_ms()
        data = self.window.data
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = command
        data[control.STATUS + 2] = self.mode

    def _commit(self):
        data = self.window.data
        command = self.job
        self.mask = self.desired
        self.mode = 1 if self.mask else 0
        data[VOICE_STATUS] = self.mask
        data[BUSY_STATUS] = 0
        if command != EXPIRED:
            data[control.STATUS + 3] = 0
            data[control.STATUS] = (data[control.STATUS] + 1) & 255
            data[control.STATUS + 1] = command
            data[control.STATUS + 2] = self.mode
        if self.mode:
            self.last_keep = control.live.time.ticks_ms()
        self._gates()
        if command == control.FINISH:
            self.window.finish_pending = self.window.finished = True
        self.job = IDLE
        self.jobs += 1

    def poll(self):
        control.ControlTarget.poll(self)
        if self.job == IDLE:
            return
        idle = not control.link.mem32[control.link.IC_STATUS] & 0x40
        if self.cursor < 6:
            if not idle:
                return
            # Skip unchanged voices; at most one changed register per poll.
            while self.cursor < 6:
                index = self.cursor
                bit = 1 << index
                if (self.applied ^ self.desired) & bit:
                    before = control.live.time.ticks_us()
                    self.board.voice(index, 1 if self.desired & bit else 0)
                    elapsed = control.live.time.ticks_diff(control.live.time.ticks_us(), before)
                    self.max_write_us = max(self.max_write_us, elapsed)
                    self.applied = (self.applied | bit) if self.desired & bit else (self.applied & ~bit)
                    self.writes += 1
                    self.cursor += 1
                    break
                self.cursor += 1
            if self.cursor == 6:
                self.prime_left = poly.PRIME_BLOCKS if self.desired else 0
        elif self.prime_left:
            # Count audio-loop opportunities even while the host reads status.
            self.prime_left -= 1
        if self.cursor == 6 and self.prime_left == 0 and idle:
            self._commit()


def start_live(board, resources):
    print("STARTUP PASS: quiet six-voice notes prepared; I2C voice masks follow")
    target = SixTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
            resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        print("SIX I2C: jobs=%d writes=%d max_write_us=%d pending=%d applied=%d prime_left=%d" %
              (target.jobs, target.writes, target.max_write_us, target.job, target.applied, target.prime_left))
    print("PASS: six-voice sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        staged.startup.run(bus_factory=SixBus, resource_factory=SixResources,
            phase_names=staged.PHASES[:5] + ("QUIET SIX VOICES PREPARED",), after_phases=start_live,
            title="YM2203 Rev C / staged I2C six-voice target v1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
