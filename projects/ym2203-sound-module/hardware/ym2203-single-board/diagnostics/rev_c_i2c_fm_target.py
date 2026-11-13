# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Cooperative I2C control while validated PIO/DMA FM conversion continues."""
import rev_c_fm_live as live
import rev_c_i2c_target_check as link
from rev_c_fm_ssg_check import MixerBus
from rev_c_i2c_ssg_target import Commands


SIGNATURE = b"RCMIX02!"
LEASE_MS = 1000
WAIT_MS = 300000
STOP, FM, SSG, BOTH, DAC_MUTE, LINE_MUTE, KEEP, FINISH = range(8)
START = 8
SOURCE_MASKS = (0, 1, 2, 3, 3, 3)
STATUS = 0x10  # ack, last command, mode (0..5), lease-expired flag
PROBE_REGS = (link.IC_CON, link.IC_SAR, link.IC_ENABLE, link.IC_ENABLE_STATUS,
              link.IC_SLV_DATA_NACK_ONLY, 0x400280A4, 0x400280AC, 0xD0000004)
EXPECTED_CONFIG = (0x324, 0x42, 1, 1, 0, 3, 3)


class ControlTarget(link.Target):
    def __init__(self, board):
        if getattr(link, "TRANSPORT_VERSION", None) != "1.1":
            raise RuntimeError("Install transport 1.1 and soft reset")
        super().__init__()
        self.window = Commands()
        self.window.data[:8] = SIGNATURE
        self.board = board
        self.mode = self.mask = self.last_keep = self.expirations = 0
        self.start_requested = self.live_started = False
        self.before_config = [0] * 8
        self.after_config = [0] * 8
        self.before_recorded = self.after_recorded = False

    def snapshot(self, after_start):
        values = self.after_config if after_start else self.before_config
        for index in range(8):
            value = link.mem32[PROBE_REGS[index]]
            if index == 5 or index == 6:
                value &= 31  # pin function only, no mux writes
            elif index == 7:
                value = (value >> 20) & 3  # SDA/SCL digital input levels
            values[index] = value
        if after_start:
            self.after_recorded = True
        else:
            self.before_recorded = True
        for index in range(7):
            if values[index] != EXPECTED_CONFIG[index]:
                raise RuntimeError("I2C configuration mismatch after_start=%s values=%r" %
                                   (after_start, values))

    def set_mode(self, mode):
        if type(mode) is not int or not STOP <= mode <= LINE_MUTE:
            raise ValueError("Unsupported fixed FM/SSG diagnostic mode")
        if mode and not self.live_started:
            raise RuntimeError("START must complete before enabling sound")
        desired = SOURCE_MASKS[mode]
        self.board.line_allow.value(0)
        if (self.mask ^ desired) & 1:
            self.board.write_fm(0x28, 0x10 if desired & 1 else 0)
        if (self.mask ^ desired) & 2:
            self.board.checked(8, 10 if desired & 2 else 0)
        self.mask = desired
        self.board.dac_allow.value(1 if desired & 1 and mode != DAC_MUTE else 0)
        self.board.line_allow.value(1 if FM <= mode <= DAC_MUTE else 0)
        self.mode = mode

    def apply(self, command):
        if command not in (STOP, FM, SSG, BOTH, DAC_MUTE, LINE_MUTE, KEEP, FINISH, START):
            raise ValueError("Unsupported live FM/SSG diagnostic command")
        data = self.window.data
        if command == START:
            if self.start_requested or self.live_started:
                raise RuntimeError("Live capture was already requested")
            self.start_requested = True
        elif command == KEEP:
            if self.mode:
                self.last_keep = live.time.ticks_ms()
        else:
            self.set_mode(STOP if command == FINISH else command)
            data[STATUS + 3] = 0
            if self.mode:
                self.last_keep = live.time.ticks_ms()
            if command == FINISH:
                self.window.finish_pending = self.window.finished = True
        data[STATUS] = (data[STATUS] + 1) & 255
        data[STATUS + 1] = command
        data[STATUS + 2] = self.mode

    def poll(self):
        if self.mode and live.time.ticks_diff(live.time.ticks_ms(), self.last_keep) >= LEASE_MS:
            self.set_mode(STOP)
            self.expirations += 1
            self.window.data[STATUS + 2] = 0
            self.window.data[STATUS + 3] = 1
        # Avoid allocating a super proxy in the per-audio-block hot loop.
        link.Target.poll(self)
        if self.window.pending >= 0 and not link.mem32[link.IC_STATUS] & 0x40:
            command = self.window.pending
            self.window.pending = -1
            self.apply(command)


def sequence(board, stream, pcm, audio, silence, sources_prepared=False, target_factory=None):
    target = None
    max_poll_us = max_idle_poll_us = peak = 0
    try:
        board.line_allow.value(0)
        board.dac_allow.value(0)
        stream.stop()
        # Fixed 440 Hz FM / 220 Hz SSG, exactly the previous mixer levels.
        # All long setup and heap walks happen before continuous capture starts.
        if not sources_prepared:
            board.ssg("single")
            board.checked(8, 0)
            live._send(audio, silence, 200)
        target = (ControlTarget if target_factory is None else target_factory)(board)
        target.prepare()
        live.gc.collect()
        # A READY banner must never advertise an address that is still disabled.
        target._enable(1)
        target.snapshot(False)
        print("I2C CONFIG BEFORE LIVE:", target.before_config)
        print("READY: I2C enabled, FM capture STOPPED address=0x42 transport=1.1; run matching FM MIXER HOST.")
        print("No target progress logs during capture. Hardware I2C host, both volumes low.")
        started = live.time.ticks_ms()
        while not target.window.finished:
            running = stream.running
            if running:
                stream.check()
            before = live.time.ticks_us()
            target.poll()
            elapsed = live.time.ticks_diff(live.time.ticks_us(), before)
            if running:
                max_poll_us = max(max_poll_us, elapsed)
            else:
                max_idle_poll_us = max(max_idle_poll_us, elapsed)
            if target.start_requested and not target.live_started:
                stream.start()
                target.live_started = True
                target.snapshot(True)
            if stream.running:
                stream.check()
            if target.window.finished:
                break
            if stream.running:
                peak = max(peak, live.step(stream, pcm, audio))
            if live.time.ticks_diff(live.time.ticks_ms(), started) >= WAIT_MS:
                raise RuntimeError("Live I2C diagnostic timeout; reset both boards")
    finally:
        # Mute and stop the short-deadline work before USB output/cleanup.
        board.line_allow.value(0)
        board.dac_allow.value(0)
        board.arm.value(0)
        stream.stop()
        if target is not None:
            target.close()
            print("LIVE I2C: live_started=%d blocks=%d peak=%d max_poll_us=%d max_idle_poll_us=%d commands=%d lease_expirations=%d received=%d sent=%d stale_flushes=%d" %
                  (target.live_started, stream.sequence if target.live_started else 0,
                   peak, max_poll_us, max_idle_poll_us, target.window.data[STATUS],
                   target.expirations, target.window.received, target.window.sent, target.flushes))
            if target.before_recorded:
                print("I2C CONFIG BEFORE LIVE:", target.before_config)
            if target.after_recorded:
                print("I2C CONFIG AFTER LIVE:", target.after_config)
            print("LAST CONTROL STATE (before reset): %r" % bytes(target.window.data[STATUS:STATUS+4]))


def run():
    live.run(
        bus_factory=MixerBus, sequence=sequence,
        title="YM2203 Rev C / I2C + live FM mixer target check v1.1",
        connection_message="Host I2C GP20/21 connected; both volumes low. Live FM/SSG WILL sound on command.",
        description="Silent live preflight passed. I2C READY follows after about 5 seconds.",
        completion="DONE: report FM/SSG modes, independent mutes, lease mute, L/R and HOST PASS."
    )


if __name__ == "__main__":
    run()
