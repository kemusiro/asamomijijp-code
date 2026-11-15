# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Continue the physically successful staged I2C startup into live FM/SSG."""
import gc
import rev_c_i2c_isolation_target as startup
import rev_c_i2c_fm_target as control


PHASES = startup.PHASES[:5] + ("SSG MIXER PREPARED",)


class MixerResources(startup.Resources):
    def setup(self, phase):
        if phase == 5:
            # Keep the already-tested receiver and I2S resources. Unlike the
            # silent diagnostic's final phase, do not reset YM or close I2S.
            self.board.ssg("single")
            self.board.checked(8, 0)
            control.live._send(self.audio, self.silence, 200)
        else:
            super().setup(phase)


def start_live(board, resources):
    print("STARTUP PASS: six silent I2C phases; preparing live-control READY")
    control.sequence(board, resources.stream, resources.pcm, resources.audio,
                     resources.silence, sources_prepared=True)
    print("PASS: live sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_gc_enabled = gc.isenabled()
    gc.enable()
    try:
        startup.run(bus_factory=control.MixerBus, resource_factory=MixerResources,
                    phase_names=PHASES, after_phases=start_live,
                    title="YM2203 Rev C / staged I2C + live FM mixer target v1.3")
    finally:
        if not was_gc_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
