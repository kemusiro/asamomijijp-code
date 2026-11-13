# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Fixed SSG commands over the user-tested I2C target; no FM/DAC playback."""
import gc
import time
import rev_c_i2c_target_check as link
from rev_c_ssg_check import RevCSSGBus, TONE_PERIOD, SSG_LEVEL, MIXERS
from rev_c_bus_check import _check_platform, _diagnose, _emergency_stop


SIGNATURE = b"RCSSG01!"
LEASE_MS = 1000
COMMAND_REGISTER = 0x20
STATUS_REGISTER = 0x10  # ack count, last command, active channel, lease-expired flag
STOP, TONE_A, TONE_B, TONE_C, KEEP, FINISH = range(6)


class SoundBus(RevCSSGBus):
    def select(self, channel):
        if type(channel) is not int or not 1 <= channel <= 3:
            raise ValueError("Select fixed SSG channel 1, 2 or 3")
        self.silence()
        index = channel - 1
        self.checked(index * 2, TONE_PERIOD & 255)
        self.checked(index * 2 + 1, TONE_PERIOD >> 8)
        self.checked(7, MIXERS[index])
        self.checked(8 + index, SSG_LEVEL)
        time.sleep_ms(50)
        self.line_allow.value(1)


class Commands(link.Window):
    def __init__(self):
        super().__init__()
        self.data[:8] = SIGNATURE
        self.pending = -1
        self.command_frame = False
        self.frame_bytes = 0

    def receive(self, word):
        value = word & 255
        self.received += 1
        if word & link.FIRST_BYTE:
            self.pointer = value
            self.command_frame = value == COMMAND_REGISTER
            self.frame_bytes = 0
            return
        if self.command_frame:
            if self.frame_bytes or self.pending >= 0:
                raise ValueError("Expected one command byte, with no pending command")
            self.pending = value
            self.frame_bytes = 1
        else:
            self.ignored += 1
        self.pointer = (self.pointer + 1) & 255


class SoundTarget(link.Target):
    def __init__(self, board):
        if getattr(link, "TRANSPORT_VERSION", None) != "1.1":
            raise RuntimeError("Install v1.1 rev_c_i2c_target_check.py and soft reset")
        super().__init__()
        self.window = Commands()
        self.board = board
        self.active = 0
        self.last_keep = 0
        self.expirations = 0

    def apply(self, command):
        # Validate before any enable. Arbitrary register writes are not exposed.
        if command not in (STOP, TONE_A, TONE_B, TONE_C, KEEP, FINISH):
            raise ValueError("Unsupported SSG diagnostic command")
        data = self.window.data
        if command in (TONE_A, TONE_B, TONE_C):
            self.board.select(command)
            self.active = command
            data[STATUS_REGISTER + 3] = 0
            self.last_keep = time.ticks_ms()
        elif command == KEEP:
            if self.active:
                self.last_keep = time.ticks_ms()
        else:
            self.board.silence()
            self.active = 0
            data[STATUS_REGISTER + 3] = 0
            if command == FINISH:
                self.window.finish_pending = True
                self.window.finished = True  # apply is only called while bus idle
        data[STATUS_REGISTER] = (data[STATUS_REGISTER] + 1) & 255
        data[STATUS_REGISTER + 1] = command
        data[STATUS_REGISTER + 2] = self.active

    def poll(self):
        if self.active and time.ticks_diff(time.ticks_ms(), self.last_keep) >= LEASE_MS:
            self.board.silence()
            self.active = 0
            self.expirations += 1
            self.window.data[STATUS_REGISTER + 2] = 0
            self.window.data[STATUS_REGISTER + 3] = 1
        super().poll()
        # A whole one-byte command is received first; execute only after STOP.
        # A pointer-only/partial write has no audible effect.
        if self.window.pending >= 0 and not link.mem32[link.IC_STATUS] & 0x40:
            command = self.window.pending
            self.window.pending = -1
            self.apply(command)


def run():
    _check_platform()
    print("YM2203 Rev C / I2C SSG target check v1.2")
    print("External I2C commands WILL produce SSG. Start both volumes low.")
    board = target = reserve = None
    mute = disarm = None
    try:
        reserve = bytearray(4096)
        board = SoundBus()
        mute, disarm = board.line_allow.value, board.arm.value
        _diagnose(board)
        board.silence()
        target = SoundTarget(board)
        target.prepare()
        gc.collect()
        print("READY: address=0x42 transport=1.1; run I2C SSG HOST on the OTHER Pico within 5 minutes.")
        target.serve()
    except BaseException:
        if mute is not None:
            mute(0)
        if disarm is not None:
            disarm(0)
        reserve = None
        gc.collect()
        print("FAIL or interrupted. Save both logs before retrying.")
        raise
    finally:
        if mute is not None:
            mute(0)
        if disarm is not None:
            disarm(0)
        reserve = None
        gc.collect()
        try:
            if target is not None:
                target.close()
        finally:
            if board is None:
                _emergency_stop()
            else:
                board.close()
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 I2C=disabled")
        if target is not None:
            print("TARGET: commands=%d lease_expirations=%d received=%d sent=%d stale_flushes=%d" %
                  (target.window.data[STATUS_REGISTER], target.expirations,
                   target.window.received, target.window.sent, target.flushes))
            print("LAST CONTROL STATE (before reset): %r" %
                  bytes(target.window.data[STATUS_REGISTER:STATUS_REGISTER + 4]))
    print("DONE: report six SSG tones, one short watchdog tone, final silence and HOST PASS.")


if __name__ == "__main__":
    run()
