# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Bounded live FM TL/MULTI presets controlled over external I2C."""
import gc
import rev_c_i2c_fm_staged_target as staged
import rev_c_fm_timbre_check as timbre


control = staged.control
SIGNATURE = b"RCTIM01!"
TL_BASE, MULTI_BASE = 0x60, 0x70
SELECTION = 0x14  # TL preset 0..3, MULTI preset 0..2; software record


class TimbreBus(timbre.TimbreBus):
    def __init__(self):
        self.timbre_ready = False
        super().__init__()

    def write_fm(self, register, value):
        if not self.timbre_ready:
            # Leave the proven quiet one-operator preflight unchanged.
            return super().write_fm(register, value)
        if (type(register) is not int or type(value) is not int or
                register != 0x28 or value not in (0, 1, 2, 0x10)):
            raise ValueError("After timbre setup only bounded key control is allowed here")
        # Existing controller's one-operator key-on becomes four-operator CH1.
        self._write_tone(register, 0xF0 if value == 0x10 else value)


class TimbreResources(staged.MixerResources):
    def setup(self, phase):
        super().setup(phase)
        if phase == 5:
            # Full 4-op setup happens once, with capture stopped and gates off.
            self.board.configure("serial")
            self.board.timbre_ready = True


class TimbreTarget(control.ControlTarget):
    def __init__(self, board):
        if not board.timbre_ready:
            raise RuntimeError("Quiet serial timbre must be prepared before I2C control")
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.window.data[SELECTION] = 2  # TL 40, configured above
        self.window.data[SELECTION + 1] = 0  # MULTI 1

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Timbre command must be an integer")
        tl = TL_BASE <= command < TL_BASE + len(timbre.MOD_LEVELS)
        multi = MULTI_BASE <= command < MULTI_BASE + len(timbre.MULTIPLES)
        if not tl and not multi:
            if command not in (control.STOP, control.FM, control.KEEP, control.FINISH, control.START):
                raise ValueError("Only solo FM and bounded TL/MULTI commands are used")
            return control.ControlTarget.apply(self, command)
        if not self.live_started or self.window.data[control.STATUS + 3]:
            raise RuntimeError("Timbre change requires START and a non-expired session")
        if self.mode not in (control.STOP, control.FM):
            raise ValueError("Timbre change requires STOP or solo FM")
        index = command - (TL_BASE if tl else MULTI_BASE)
        if tl:
            self.board.modulation(timbre.MOD_LEVELS[index])
        else:
            self.board.multiple(timbre.MULTIPLES[index])
        data = self.window.data
        data[SELECTION + (0 if tl else 1)] = index
        if self.mode:
            self.last_keep = control.live.time.ticks_ms()
        data[control.STATUS] = (data[control.STATUS] + 1) & 255
        data[control.STATUS + 1] = command
        data[control.STATUS + 2] = self.mode


def start_live(board, resources):
    print("STARTUP PASS: quiet four-operator timbre prepared; I2C TL/MULTI control follows")
    control.sequence(board, resources.stream, resources.pcm, resources.audio,
                     resources.silence, sources_prepared=True, target_factory=TimbreTarget)
    print("PASS: timbre sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        staged.startup.run(bus_factory=TimbreBus, resource_factory=TimbreResources,
            phase_names=staged.PHASES[:5] + ("QUIET FOUR-OPERATOR TIMBRE PREPARED",),
            after_phases=start_live,
            title="YM2203 Rev C / staged I2C live FM timbre target v1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
