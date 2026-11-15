# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Output-gate mute leaves the accompanied queue,keys,and clock running."""
import gc
import rev_c_i2c_queue_accomp_target as accomp

queue, pitch, control, six = accomp.queue, accomp.pitch, accomp.control, accomp.six
SIGNATURE = b"RCQMT01!"
GATE_STATUS = 0x29  # Commanded gates: bit0=DAC_ALLOW,bit1=LINE_ALLOW


class MutedQueueTarget(accomp.AccompaniedTarget):
    def __init__(self, board):
        super().__init__(board)
        self.window.data[:8] = SIGNATURE
        self.gate_commands = self.dac_mutes = self.line_mutes = self.restores = 0
        self.gate_setting = 3
        self.gate_notes = bytearray(255 for unused in range(queue.CAPACITY * queue.RUN_LIMIT))

    def gates(self):
        # Pin.value() reads on OUT pins have undefined semantics. Publish
        # controller intent; the register model separately checks pin levels.
        return self.gate_setting if self.mode == 1 and queue.PLAYING <= self.state <= queue.DRAINING else 0

    def apply(self, command):
        if type(command) is int and command in (control.DAC_MUTE, control.LINE_MUTE, control.BOTH):
            if (self.state != queue.PLAYING or self.mode != 1 or
                    self.job != six.IDLE or self.window.data[control.STATUS + 3]):
                raise RuntimeError("Queue gate mute requires active unexpired playback")
            # Queue mode stays1: these commands control only output gates.
            # No chip key/volume/pitch writes,no new epoch,no event replay.
            if command == control.LINE_MUTE:
                self.board.line_allow.value(0)
                self.board.dac_allow.value(1)
                self.gate_setting = 1
                self.line_mutes += 1
            elif command == control.DAC_MUTE:
                self.board.dac_allow.value(0)
                self.board.line_allow.value(1)
                self.gate_setting = 2
                self.dac_mutes += 1
            else:
                self.board.dac_allow.value(1)
                self.board.line_allow.value(1)
                self.gate_setting = 3
                self.restores += 1
            self.last_keep = control.live.time.ticks_ms()
            self.window.data[GATE_STATUS] = self.gates()
            self.gate_commands += 1
            self.ack(command)
            return
        accomp.AccompaniedTarget.apply(self, command)
        if command == queue.PLAY_FM or command == queue.PLAY_SSG:
            self.gate_setting = 3
        self.window.data[GATE_STATUS] = self.gates()

    def record_note(self, elapsed):
        accomp.AccompaniedTarget.record_note(self, elapsed)
        self.gate_notes[(self.runs - 1) * queue.CAPACITY + self.next_note - 1] = self.gates()

    def poll(self):
        accomp.AccompaniedTarget.poll(self)
        self.window.data[GATE_STATUS] = self.gates()

    def report(self):
        accomp.AccompaniedTarget.report(self)
        print("QUEUE GATES: commands=%d dac_mutes=%d line_mutes=%d restores=%d gates=%d" %
              (self.gate_commands, self.dac_mutes, self.line_mutes, self.restores, self.gates()))
        for run in range(self.runs):
            start = run * queue.CAPACITY
            print("GATE NOTES %d: %r" % (run + 1, list(self.gate_notes[start:start + queue.CAPACITY])))


def start_live(board, resources):
    if resources.stream.running:
        raise RuntimeError("Heap preflight requires capture stopped")
    pitch.check_bus_heap(board)
    print("STARTUP PASS: accompanied queue with independent output gate control follows")
    target = MutedQueueTarget(board)
    try:
        control.sequence(board, resources.stream, resources.pcm, resources.audio,
            resources.silence, sources_prepared=True, target_factory=lambda unused: target)
    finally:
        print("SIX I2C: jobs=%d writes=%d pending=%d applied=%d" %
              (target.jobs, target.writes, target.job, target.applied))
        target.report()
    print("PASS: queued gate mute sent; max conversion=%d us, deadline misses=%d" %
          (resources.stream.max_convert_us, resources.stream.deadline_misses))


def run():
    was_enabled = gc.isenabled()
    gc.enable()
    try:
        six.staged.startup.run(bus_factory=pitch.PitchBus, resource_factory=six.SixResources,
            phase_names=six.staged.PHASES[:5] + ("QUIET SIX VOICES PREPARED",), after_phases=start_live,
            title="YM2203 Rev C / staged I2C queued gate mute target v1")
    finally:
        if not was_enabled: gc.disable()


if __name__ == "__main__": run()
