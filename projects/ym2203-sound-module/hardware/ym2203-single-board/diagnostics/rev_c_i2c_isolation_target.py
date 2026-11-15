# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Silent, staged isolation of I2C failure after FM/I2S initialization."""
import gc
import time
from machine import Pin, I2S
import rev_c_fm_live as live
import rev_c_i2c_target_check as link
from rev_c_bus_check import _check_platform, _diagnose, _emergency_stop


SIGNATURE = b"RCISO01!"
PHASES = ("BUS ONLY", "FM REGISTERS", "FM RX ALLOCATED",
          "I2S RUNNING", "FM PREFLIGHT STOPPED", "I2S CLOSED")
WAIT_MS = 300000
ADVANCE_REGISTER = 0x7E
FINISH_REGISTER = 0x7F
TOKEN = 0xA5


class ProbeWindow(link.Window):
    def __init__(self, phase):
        super().__init__()
        self.data[:8] = SIGNATURE
        self.data[8] = phase
        self.data[9] = phase ^ 255
        self.phase = phase
        self.advance = False
        self.control_frame = False
        self.control_bytes = 0

    def receive(self, word):
        value = word & 255
        if word & link.FIRST_BYTE:
            self.control_frame = value in (ADVANCE_REGISTER, FINISH_REGISTER)
            self.control_bytes = 0
        elif self.control_frame:
            if self.control_bytes or value != TOKEN:
                raise ValueError("Expected one isolation control token")
            self.control_bytes = 1
            if self.pointer == ADVANCE_REGISTER:
                if self.phase == len(PHASES) - 1:
                    raise ValueError("Cannot advance past last isolation phase")
                self.advance = True
                self.received += 1
                self.pointer = FINISH_REGISTER
                return
            if self.phase != len(PHASES) - 1:
                raise ValueError("Cannot finish before last isolation phase")
        super().receive(word)


class ProbeTarget(link.Target):
    def __init__(self, phase):
        if getattr(link, "TRANSPORT_VERSION", None) != "1.1":
            raise RuntimeError("Install transport 1.1 and soft reset")
        super().__init__()
        self.window = ProbeWindow(phase)

    def report_config(self):
        # Read-only observations, made with capture stopped. No GPIO remuxing.
        values = [link.mem32[address] for address in
                  (link.IC_CON, link.IC_SAR, link.IC_ENABLE, link.IC_ENABLE_STATUS,
                   link.IC_SLV_DATA_NACK_ONLY, link.IC_STATUS, link.IC_RAW_INTR_STAT,
                   0x40038054, 0x40038058)]
        mux = [link.mem32[0x40028004 + 8 * pin] & 31 for pin in range(30)]
        levels = (link.mem32[0xD0000004] >> 20) & 3
        print("I2C CONFIG:", values)
        print("GPIO0..29 FUNCSEL:", mux)
        print("SDA/SCL INPUT BITS:", levels)
        if values[:5] != [0x324, 0x42, 1, 1, 0] or mux[20:22] != [3, 3]:
            raise RuntimeError("Isolation I2C configuration mismatch")


class Resources:
    def __init__(self, board):
        self.board = board
        self.stream = self.audio = None
        self.pcm = bytearray(live.OUTPUT_FRAMES * 4)
        self.silence = bytearray(live.RATE // 100 * 4)

    def setup(self, phase):
        if phase == 1:
            self.board.prepare()
        elif phase == 2:
            self.stream = live.Stream()
            self.stream.open()
        elif phase == 3:
            self.audio = I2S(0, sck=Pin(11), ws=Pin(12), sd=Pin(10), mode=I2S.TX,
                             bits=16, format=I2S.STEREO, rate=live.RATE, ibuf=live.IBUF)
            live._send(self.audio, self.silence, 200)
        elif phase == 4:
            self.preflight()
        elif phase == 5:
            self.board.close()
            self.close_i2s()

    def preflight(self):
        stream, board = self.stream, self.board
        peak = 0
        gc.collect()
        try:
            stream.start()
            for unused in range(4):
                if live.step(stream, self.pcm, self.audio) > 64:
                    raise RuntimeError("Isolation FM key-off is not near zero")
            board.write_fm(0x28, 0x10)
            for unused in range(12):
                peak = max(peak, live.step(stream, self.pcm, self.audio))
            if peak < 512:
                raise RuntimeError("Isolation FM key-on signal missing")
            board.write_fm(0x28, 0)
            for index in range(40):
                level = live.step(stream, self.pcm, self.audio)
                if index >= 30 and level > 64:
                    raise RuntimeError("Isolation FM did not return to zero")
        finally:
            stream.stop()
        live._send(self.audio, self.silence, 200)
        print("SILENT PREFLIGHT: peak=%d blocks=%d max_conversion_us=%d deadline_misses=%d" %
              (peak, stream.sequence, stream.max_convert_us, stream.deadline_misses))

    def close_i2s(self):
        if self.audio is not None:
            self.audio.deinit()
            self.audio = None
        for pin in (10, 11, 12):
            Pin(pin, Pin.OUT, pull=None, value=0)

    def close(self):
        try:
            if self.stream is not None:
                self.stream.close()
        finally:
            self.close_i2s()


def listen(target):
    started = time.ticks_ms()
    while True:
        target.poll()
        if (target.window.advance or target.window.finished) and not link.mem32[link.IC_STATUS] & 0x40:
            return
        if time.ticks_diff(time.ticks_ms(), started) >= WAIT_MS:
            raise RuntimeError("Isolation timeout; save both logs")


def run(bus_factory=None, resource_factory=None, phase_names=None, after_phases=None, title=None):
    _check_platform()
    print(title or "YM2203 Rev C / silent I2C initialization isolation target v1")
    if after_phases is None:
        print("LINE/DAC remain muted throughout. Run ISOLATION HOST on the OTHER Pico.")
    else:
        print("Phases 0..5 stay muted; later FM/SSG WILL sound. Both volumes low; run STAGED FM MIXER HOST.")
    board = resources = target = reserve = None
    mute = disarm = None
    phase = -1
    in_after_phases = False
    try:
        reserve = bytearray(4096)
        board = live.RevCFMBus() if bus_factory is None else bus_factory()
        mute, disarm = board.line_allow.value, board.arm.value
        _diagnose(board)
        resources = Resources(board) if resource_factory is None else resource_factory(board)
        names = PHASES if phase_names is None else phase_names
        if len(names) != len(PHASES):
            raise ValueError("Expected exactly six diagnostic phase names")
        for phase in range(len(PHASES)):
            print("PHASE %d SETUP / %s" % (phase, names[phase]))
            resources.setup(phase)
            gc.collect()  # continuous capture is stopped between all phases
            target = ProbeTarget(phase)
            target.prepare()  # initialize I2C AFTER this phase's resources
            target._enable(1)
            target.report_config()
            print("PHASE %d READY / %s / address=0x42" % (phase, names[phase]))
            listen(target)
            target.close()
            print("PHASE %d END / received=%d sent=%d ignored=%d stale_flushes=%d" %
                  (phase, target.window.received, target.window.sent,
                   target.window.ignored, target.flushes))
            target = None
        if after_phases is not None:
            in_after_phases = True
            after_phases(board, resources)
    except BaseException:
        if mute is not None:
            mute(0)
        if disarm is not None:
            disarm(0)
        if resources is not None and resources.stream is not None:
            resources.stream.stop()
        reserve = None
        gc.collect()
        if in_after_phases:
            print("FAIL or interrupted / live-control after phase=%d; save both FULL logs" % phase)
        else:
            print("FAIL or interrupted / phase=%d; save both FULL logs" % phase)
        raise
    finally:
        if mute is not None:
            mute(0)
        if disarm is not None:
            disarm(0)
        reserve = None
        try:
            if board is not None:
                board.close()
            else:
                _emergency_stop()
        finally:
            try:
                if resources is not None:
                    resources.close()
            finally:
                if target is not None:
                    target.close()
                    print("LAST PHASE %d / received=%d sent=%d stale_flushes=%d" %
                          (phase, target.window.received, target.window.sent, target.flushes))
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 capture/I2S/I2C=stopped")
    if after_phases is None:
        print("DONE: six silent initialization phases complete; compare HOST PASS and no test sound.")
    else:
        print("DONE: staged live FM/I2C check complete; report both logs and all nine sound sections.")


if __name__ == "__main__":
    run()
