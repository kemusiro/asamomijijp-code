# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Per-voice five-note presets; two register writes split across audio polls."""
import gc
import rev_c_i2c_six_target as six


control = six.control
SIGNATURE = b"RCPOL01!"
PITCH_BASE = 0x80  # voice*5 + note, 0x80..0x9D
PITCH_STATUS = 0x16  # six committed note indices, following mask and busy
INITIAL = (0, 2, 4, 0, 2, 4)
SSG_PERIODS = (478, 426, 379, 358, 319)  # C3 D3 E3 F3 G3
HEAP_PAIRS = 16
HEAP_LIMIT = 64  # allow constant call/loop overhead, not per-transfer objects


class PitchBus(six.SixBus):
    def pitch_step(self, voice, note, step):
        if (type(voice) is not int or not 0 <= voice < 6 or
                type(note) is not int or not 0 <= note < 5 or
                type(step) is not int or step not in (0, 1)):
            raise ValueError("Choose voice0..5, note0..4 and step0/1")
        if voice < 3:
            # Reuse the physically tested FM note bytes; expose no arbitrary
            # register/data path and leave TL, operators and key state alone.
            name, high, low = control.live.PITCHES[note]
            register = (0xA4 if step == 0 else 0xA0) + voice
            value = high if step == 0 else low
            self.wait_ready()
            self._write_port(0, register)
            self.wait_ready()
            self._write_port(1, value)
            self.wait_ready()
        else:
            # All five low-octave presets have the same high byte (1).
            # Write it first, then the low byte, keeping other voices untouched.
            period = SSG_PERIODS[note]
            register = 2 * (voice - 3) + (1 if step == 0 else 0)
            self.checked(register, period >> 8 if step == 0 else period & 255)


class PitchTarget(six.SixTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.window.data[PITCH_STATUS:PITCH_STATUS + 6] = bytes(INITIAL)
        self.pitch_command = -1
        self.pitch_voice = self.pitch_note = self.pitch_step = 0
        self.pitch_updates = self.pitch_writes = self.pitch_cancelled = self.max_pitch_write_us = 0

    def set_mode(self, mode):
        # A lease expiry wins over a partially written pitch. It must not
        # later receive a success ACK or reopen either output gate.
        if self.pitch_command >= 0:
            self.pitch_command = -1
            self.pitch_cancelled += 1
        six.SixTarget.set_mode(self, mode)

    def apply(self, command):
        if type(command) is not int:
            raise ValueError("Per-voice pitch command must be an integer")
        if self.pitch_command >= 0:
            raise RuntimeError("Pitch update pending; wait for its ACK")
        if not PITCH_BASE <= command < PITCH_BASE + 30:
            return six.SixTarget.apply(self, command)
        if self.job != six.IDLE:
            raise RuntimeError("Voice update pending; wait for its ACK")
        if not self.live_started or self.window.data[control.STATUS + 3]:
            raise RuntimeError("Pitch requires START and a non-expired session")
        index = command - PITCH_BASE
        self.pitch_voice, self.pitch_note = index // 5, index % 5
        self.pitch_command, self.pitch_step = command, 0
        self.window.data[six.BUSY_STATUS] = 1

    def poll(self):
        six.SixTarget.poll(self)
        if self.pitch_command < 0 or self.job != six.IDLE or control.link.mem32[control.link.IC_STATUS] & 0x40:
            return
        # One bounded register per audio opportunity; ACK only after both.
        before = control.live.time.ticks_us()
        self.board.pitch_step(self.pitch_voice, self.pitch_note, self.pitch_step)
        elapsed = control.live.time.ticks_diff(control.live.time.ticks_us(), before)
        self.max_pitch_write_us = max(self.max_pitch_write_us, elapsed)
        self.pitch_step += 1
        self.pitch_writes += 1
        if self.pitch_step == 2:
            data = self.window.data
            data[PITCH_STATUS + self.pitch_voice] = self.pitch_note
            data[six.BUSY_STATUS] = 0
            data[control.STATUS] = (data[control.STATUS] + 1) & 255
            data[control.STATUS + 1] = self.pitch_command
            data[control.STATUS + 2] = self.mode
            if self.mode:
                self.last_keep = control.live.time.ticks_ms()
            self.pitch_command = -1
            self.pitch_updates += 1


def check_bus_heap(board):
    if getattr(board, "io_version", None) != "1.1":
        raise RuntimeError("Install rev_c_bus_check.py I/O v1.1 and soft reset")
    board.line_allow.value(0)
    board.dac_allow.value(0)
    was_enabled = gc.isenabled()
    try:
        gc.enable()
        for voice in range(6):
            # All scans/collections and this finite GC-disabled probe happen
            # BEFORE live capture. Never do them inside the audio loop.
            board.pitch_step(voice, INITIAL[voice], 0)
            board.pitch_step(voice, INITIAL[voice], 1)
            gc.collect()
            gc.disable()
            before = gc.mem_alloc()
            try:
                repeat = 0
                while repeat < HEAP_PAIRS:
                    board.pitch_step(voice, repeat % 5, 0)
                    board.pitch_step(voice, repeat % 5, 1)
                    repeat += 1
                allocated = gc.mem_alloc() - before
            finally:
                gc.enable()
            board.pitch_step(voice, INITIAL[voice], 0)
            board.pitch_step(voice, INITIAL[voice], 1)
            print("BUS HEAP: voice=%d pairs=%d bytes=%d limit=%d" %
                  (voice, HEAP_PAIRS, allocated, HEAP_LIMIT))
            if allocated > HEAP_LIMIT or allocated < 0:
                raise RuntimeError("GPIO/pitch path heap growth; do not start live capture")
        gc.collect()
    finally:
        if was_enabled:
            gc.enable()
        else:
            gc.disable()
    print("PASS: silent bus heap preflight; GC stays enabled during live capture")


def start_live(board, resources):
    if resources.stream.running:
        raise RuntimeError("Heap preflight requires FM capture stopped")
    check_bus_heap(board)
    print("STARTUP PASS: six quiet voices prepared; independent pitch control follows")
    target = PitchTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
            resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        print("SIX I2C: jobs=%d writes=%d max_write_us=%d pending=%d applied=%d prime_left=%d" %
              (target.jobs, target.writes, target.max_write_us, target.job, target.applied, target.prime_left))
        print("VOICE PITCH: updates=%d writes=%d max_write_us=%d cancelled=%d pending=%d step=%d" %
              (target.pitch_updates, target.pitch_writes, target.max_pitch_write_us,
               target.pitch_cancelled, target.pitch_command, target.pitch_step))
    print("PASS: per-voice pitch sequence sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        six.staged.startup.run(bus_factory=PitchBus, resource_factory=six.SixResources,
            phase_names=six.staged.PHASES[:5] + ("QUIET SIX VOICES PREPARED",), after_phases=start_live,
            title="YM2203 Rev C / staged I2C per-voice pitch target v1.1")
    finally:
        if not was_enabled:
            gc.disable()


if __name__ == "__main__":
    run()
