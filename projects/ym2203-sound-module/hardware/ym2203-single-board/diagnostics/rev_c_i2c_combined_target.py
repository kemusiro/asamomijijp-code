# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Combine the validated five FM pitches with bounded TL/MULTI control."""
import gc
import rev_c_i2c_timbre_target as timbre


control = timbre.control
SIGNATURE = b"RCCMB01!"
PITCH_BASE = 0x40
PITCH_STATUS = 0x16  # pitch index 0..4; 255 until a preset is selected


class CombinedTarget(timbre.TimbreTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.window.data[PITCH_STATUS] = 255

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Combined command must be an integer")
        if not PITCH_BASE <= command < PITCH_BASE + 5:
            return timbre.TimbreTarget.apply(self, command)
        if not self.live_started or self.window.data[control.STATUS + 3]:
            raise RuntimeError("Pitch requires START and a non-expired session")
        if self.mode not in (control.STOP, control.FM):
            raise ValueError("Pitch requires STOP or solo FM")
        index = command - PITCH_BASE
        self.board.pitch(index)  # same bounded A4/A0 method as the pitch test
        data = self.window.data
        data[PITCH_STATUS] = index
        if self.mode:
            self.last_keep = control.live.time.ticks_ms()
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = command
        data[control.STATUS + 2] = self.mode


def start_live(board, resources):
    print("STARTUP PASS: combined five-pitch and TL/MULTI I2C control follows")
    control.sequence(board, resources.stream, resources.pcm, resources.audio,
                     resources.silence, sources_prepared=True, target_factory=CombinedTarget)
    print("PASS: combined sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        timbre.staged.startup.run(bus_factory=timbre.TimbreBus,
            resource_factory=timbre.TimbreResources,
            phase_names=timbre.staged.PHASES[:5] + ("QUIET FOUR-OPERATOR TIMBRE PREPARED",),
            after_phases=start_live,
            title="YM2203 Rev C / staged I2C combined FM pitch + timbre target v1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
