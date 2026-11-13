# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Five bounded pitch presets over I2C, using the validated live audio loop."""
import gc
import rev_c_i2c_fm_staged_target as staged


control = staged.control
SIGNATURE = b"RCPIT01!"
FM_BASE, SSG_BASE = 0x40, 0x50
PITCH_STATUS = 0x14  # FM index, SSG index; 255 means not selected yet
SSG_PERIODS = (239, 213, 190, 179, 159)  # 62500/period, C4 D4 E4 F4 G4


class PitchTarget(control.ControlTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.window.data[PITCH_STATUS] = self.window.data[PITCH_STATUS + 1] = 255

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Pitch command must be an integer")
        fm = FM_BASE <= command < FM_BASE + 5
        ssg = SSG_BASE <= command < SSG_BASE + 5
        if not fm and not ssg:
            return control.ControlTarget.apply(self, command)
        # A late note cannot clear a lease-expired flag or restart a source.
        # Only STOP or the matching solo mode is allowed; no arbitrary writes.
        if not self.live_started or self.window.data[control.STATUS + 3]:
            raise RuntimeError("Pitch requires START and a non-expired session")
        if self.mode not in (control.STOP, control.FM if fm else control.SSG):
            raise ValueError("Pitch requires STOP or the matching solo source")
        index = command - (FM_BASE if fm else SSG_BASE)
        if fm:
            self.board.pitch(index)  # existing A4 then A0 preset writes
        else:
            period = SSG_PERIODS[index]
            self.board.checked(0, period & 255)
            self.board.checked(1, period >> 8)
        data = self.window.data
        data[PITCH_STATUS + (0 if fm else 1)] = index
        if self.mode:
            self.last_keep = control.live.time.ticks_ms()
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = command
        data[control.STATUS + 2] = self.mode


def start_live(board, resources):
    print("STARTUP PASS: preparing five-note I2C pitch control")
    control.sequence(board, resources.stream, resources.pcm, resources.audio,
                     resources.silence, sources_prepared=True, target_factory=PitchTarget)
    print("PASS: pitch sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        staged.startup.run(bus_factory=control.MixerBus, resource_factory=staged.MixerResources,
            phase_names=staged.PHASES, after_phases=start_live,
            title="YM2203 Rev C / staged I2C FM + SSG pitch target v1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
