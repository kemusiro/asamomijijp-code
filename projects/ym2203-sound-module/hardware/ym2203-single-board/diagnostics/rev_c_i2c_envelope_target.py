# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Two quiet envelope presets and key-off without closing the audio gates."""
import gc
import rev_c_i2c_timbre_target as timbre


control = timbre.control
SIGNATURE = b"RCENV02!"
KEY_ON, KEY_OFF = 0x30, 0x31
SUSTAIN, DECAY = 0x80, 0x81
SELECTION, KEY_STATE = 0x14, 0x15


class EnvelopeBus(timbre.TimbreBus):
    def envelope_step(self, preset, index):
        if type(preset) is not int or preset not in (0, 1):
            raise ValueError("Choose fixed sustain=0 or decay=1")
        if type(index) is not int or not 0 <= index < 8:
            raise ValueError("Choose envelope register step 0..7")
        slot = timbre.timbre.SLOTS[index >> 1]
        if index & 1:
            self._write_tone(0x80 + slot, 0x8F if preset else 15)
        else:
            self._write_tone(0x60 + slot, 12 if preset else 0)

    def envelope(self, preset):
        if type(preset) is not int or preset not in (0, 1):
            raise ValueError("Choose fixed sustain=0 or decay=1")
        # Startup only: capture is stopped here. Live changes use one step/poll.
        for index in range(8):
            self.envelope_step(preset, index)


class EnvelopeResources(timbre.TimbreResources):
    def setup(self, phase):
        super().setup(phase)
        if phase == 5:
            self.board.envelope(1)  # same previously tested decay preset


class EnvelopeTarget(control.ControlTarget):
    def __init__(self, board):
        if not board.timbre_ready:
            raise RuntimeError("Quiet envelope must be prepared before control")
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.window.data[SELECTION] = 1
        self.keyed = False
        self.preset_command = -1
        self.preset_step = 0
        self.preset_updates = self.preset_writes = self.max_preset_write_us = 0

    def set_mode(self, mode):
        if type(mode) is not int or mode not in (control.STOP, control.FM):
            raise ValueError("Envelope diagnostic only uses STOP or solo FM")
        previous_mask = self.mask
        control.ControlTarget.set_mode(self, mode)
        if mode == control.STOP:
            self.keyed = False
        elif not previous_mask & 1:
            self.keyed = True
        self.window.data[KEY_STATE] = int(self.keyed)

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Envelope command must be an integer")
        if self.preset_command >= 0:
            raise RuntimeError("Envelope preset is pending; wait for its ACK")
        if command not in (KEY_ON, KEY_OFF, SUSTAIN, DECAY):
            if command not in (control.STOP, control.FM, control.KEEP, control.FINISH, control.START):
                raise ValueError("Unsupported envelope diagnostic command")
            return control.ControlTarget.apply(self, command)
        data = self.window.data
        if not self.live_started or data[control.STATUS + 3]:
            raise RuntimeError("Envelope command requires START and a non-expired session")
        if command in (SUSTAIN, DECAY):
            if self.mode != control.STOP:
                raise ValueError("Envelope preset changes require STOP")
            # Leave ACK/opcode/selection unchanged until all writes complete.
            self.preset_command = command
            self.preset_step = 0
            return
        else:
            if self.mode != control.FM:
                raise ValueError("Key commands require open FM mode")
            desired = command == KEY_ON
            if self.keyed == desired:
                raise ValueError("Key command would repeat the current key state")
            self.board.write_fm(0x28, 0x10 if desired else 0)
            self.keyed = desired
            data[KEY_STATE] = int(self.keyed)
            # Keep mode/mask/gates unchanged so the key-off release is audible.
            self.last_keep = control.live.time.ticks_ms()
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = command
        data[control.STATUS + 2] = self.mode

    def _commit_preset(self):
        data = self.window.data
        data[SELECTION] = self.preset_command - SUSTAIN
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = self.preset_command
        data[control.STATUS + 2] = self.mode
        self.preset_command = -1
        self.preset_updates += 1

    def poll(self):
        control.ControlTarget.poll(self)
        # The unchanged control loop calls poll once then services native audio.
        # Do not start a YM write or commit status during an I2C read transaction.
        if self.preset_command < 0 or control.link.mem32[control.link.IC_STATUS] & 0x40:
            return
        if self.preset_step < 8:
            before = control.live.time.ticks_us()
            self.board.envelope_step(self.preset_command - SUSTAIN, self.preset_step)
            elapsed = control.live.time.ticks_diff(control.live.time.ticks_us(), before)
            self.max_preset_write_us = max(self.max_preset_write_us, elapsed)
            self.preset_step += 1
            self.preset_writes += 1
        if self.preset_step == 8:
            self._commit_preset()


def start_live(board, resources):
    print("STARTUP PASS: quiet envelope prepared; I2C key and envelope control follows")
    target = EnvelopeTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
                         resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        # sequence has already muted, stopped capture and disabled I2C.
        print("ENVELOPE: updates=%d writes=%d max_write_us=%d pending=%d step=%d" %
              (target.preset_updates, target.preset_writes, target.max_preset_write_us,
               target.preset_command, target.preset_step))
    print("PASS: envelope sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        timbre.staged.startup.run(bus_factory=EnvelopeBus, resource_factory=EnvelopeResources,
            phase_names=timbre.staged.PHASES[:5] + ("QUIET DECAY ENVELOPE PREPARED",),
            after_phases=start_live,
            title="YM2203 Rev C / staged I2C FM envelope target v1.1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
