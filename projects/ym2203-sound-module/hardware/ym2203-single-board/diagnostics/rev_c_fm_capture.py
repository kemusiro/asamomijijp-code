# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Silent, finite FM digital-path check. No DAC or line unmute, even on success.

Uses unchanged rev_c_bus_check.py. GPIO16/17/18 are only ever inputs.
Samples all three pins together; this is not the real-time FM-to-I2S firmware.
"""
from array import array
import time
from machine import Pin
from rev_c_bus_check import RevCBus, _check_platform, _diagnose, _emergency_stop


SAMPLE_HZ = 16_000_000
WORDS = 16384  # eight 3-bit snapshots per word: 8.192 ms, 64 KiB
SM_ID = 0  # PIO0 SM0; this diagnostic does not instantiate machine.I2S
DREQ_RX = 4  # RP2350 DREQ_PIO0_RX0
FDEBUG = 0x50200008  # RP2350 PIO0_BASE + PIO_FDEBUG_OFFSET
RXSTALL = 1  # PIO_FDEBUG_RXSTALL bit for SM0, write-one-to-clear
TIMEOUT_MS = 500
FNUM = 1038
BLOCK = 4


def _program(rp2):
    @rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT, autopush=True, push_thresh=24)
    def sample():
        wrap_target()
        pull(block)
        mov(x, osr)
        label("sample")
        in_(pins, 3)
        jmp(x_dec, "sample")
        wrap()
    return sample


class Capture:
    def __init__(self):
        self.sm = None
        self.dma = None
        # MicroPython arrays do not implement repetition (array * integer).
        # Use an iterator initializer without a full-size temporary Python list.
        self.words = array("I", (0 for unused in range(WORDS)))
        self.mem32 = None

    def open(self):
        import rp2
        from machine import mem32
        self.mem32 = mem32
        self.sm = rp2.StateMachine(
            SM_ID, _program(rp2), freq=2 * SAMPLE_HZ, in_base=Pin(16)
        )
        self.dma = rp2.DMA()

    def read(self):
        self.sm.active(0)
        self.sm.restart()
        while self.sm.rx_fifo():
            self.sm.get()
        self.mem32[FDEBUG] = RXSTALL
        ctrl = self.dma.pack_ctrl(
            size=2, inc_read=False, inc_write=True, treq_sel=DREQ_RX,
            high_pri=True, bswap=False
        )
        self.dma.config(read=self.sm, write=self.words, count=WORDS, ctrl=ctrl, trigger=True)
        # Two PIO cycles per snapshot. After exactly this many samples, the
        # program blocks on its next pull, rather than overflowing after DMA ends.
        self.sm.put(WORDS * 8 - 1)
        start = time.ticks_ms()
        self.sm.active(1)
        try:
            while self.dma.active():
                if time.ticks_diff(time.ticks_ms(), start) >= TIMEOUT_MS:
                    raise RuntimeError("FM capture DMA timeout")
                time.sleep_ms(1)
        finally:
            self.sm.active(0)
            self.dma.active(0)
        flags = self.dma.unpack_ctrl(self.dma.ctrl)
        if flags["read_err"] or flags["write_err"] or flags["ahb_err"]:
            raise RuntimeError("FM capture DMA bus error")
        if self.mem32[FDEBUG] & RXSTALL:
            raise RuntimeError("PIO RX stalled: capture timing is invalid")
        return self.words

    def close(self):
        try:
            if self.sm is not None:
                self.sm.active(0)
        finally:
            if self.dma is not None:
                self.dma.close()


class RevCFMBus(RevCBus):
    def write_fm(self, register, value):
        # An explicit allow-list for channel 1, one quiet carrier. No prescaler,
        # test, timer, GPIO-port or undocumented register changes.
        allowed = {0x27: (0,), 0x28: (0, 1, 2, 0x10), 0xB0: (7,),
                   0xA4: ((BLOCK << 3) | (FNUM >> 8),), 0xA0: (FNUM & 255,)}
        for offset in (0, 4, 8, 12):
            allowed[0x30 + offset] = (1,)
            allowed[0x40 + offset] = (127, 48) if offset == 0 else (127,)
            allowed[0x50 + offset] = (31,)
            allowed[0x60 + offset] = (0,)
            allowed[0x70 + offset] = (0,)
            allowed[0x80 + offset] = (15,)
            allowed[0x90 + offset] = (0,)
        if type(register) is not int or type(value) is not int:
            raise ValueError("FM register/data must be integers")
        if register not in allowed or value not in allowed[register]:
            raise ValueError("FM write is outside this diagnostic's allow-list")
        self.wait_ready()
        self._write_port(0, register)
        self.wait_ready()
        self._write_port(1, value)
        self.wait_ready()

    def prepare(self):
        self.write_fm(0x27, 0)
        for channel in (0, 1, 2):
            self.write_fm(0x28, channel)
        for offset in (0, 4, 8, 12):
            for register, value in ((0x30, 1), (0x40, 127), (0x50, 31), (0x60, 0),
                                    (0x70, 0), (0x80, 15), (0x90, 0)):
                self.write_fm(register + offset, value)
        self.write_fm(0xB0, 7)  # four independent carriers; only slot 1 keyed on
        self.write_fm(0xA4, (BLOCK << 3) | (FNUM >> 8))
        self.write_fm(0xA0, FNUM & 255)
        self.write_fm(0x40, 48)  # approximately 36 dB total-level attenuation


def analyze(words, keep_frames=False):
    # SHIFT_RIGHT/24-bit auto-push leaves eight snapshots in bits 8..31.
    previous = None
    index = 0
    first_clk = last_clk = None
    first_sh = last_sh = None
    clocks = falls = count = history = 0
    synchronized = False
    frames = []
    bit_counts = {}
    for word in words:
        for shift in range(8, 32, 3):
            pins_now = (word >> shift) & 7  # SD bit0, CLK bit1, SH bit2
            if previous is not None:
                if not previous & 2 and pins_now & 2:
                    clocks += 1
                    if first_clk is None:
                        first_clk = index
                    last_clk = index
                    count += 1
                    # Clock SD on rising edges, as the Yamaha DAC does.
                    history = (history >> 1) | ((pins_now & 1) << 12)
                if previous & 4 and not pins_now & 4:
                    falls += 1
                    if first_sh is None:
                        first_sh = index
                    last_sh = index
                    if synchronized:
                        bit_counts[count] = bit_counts.get(count, 0) + 1
                        if count >= 13:
                            frames.append(history)
                    synchronized = True
                    count = 0
            previous = pins_now
            index += 1
    result = {
        "samples": index, "clk_edges": clocks, "sh_edges": falls,
        "clk_hz": 0 if clocks < 2 else (clocks - 1) * SAMPLE_HZ / (last_clk - first_clk),
        "sh_hz": 0 if falls < 2 else (falls - 1) * SAMPLE_HZ / (last_sh - first_sh),
        "bit_counts": bit_counts, "frames": len(frames),
        "unique": len(set(frames)), "head": frames[:16],
    }
    if keep_frames:
        result["data"] = frames
    return result


def report(name, result):
    print("%s: CLK=%.0f Hz SH=%.0f Hz frames=%d unique=%d" %
          (name, result["clk_hz"], result["sh_hz"], result["frames"], result["unique"]))
    print("  clocks/frame: %s" % result["bit_counts"])
    print("  last13 LSB-first: %s" % " ".join("%04X" % w for w in result["head"]))
    if result["clk_edges"] < 100 or result["sh_edges"] < 16:
        raise RuntimeError("Missing/insufficient FM CLK or SH transitions: " + name)
    counts = result["bit_counts"]
    if not counts or any(bits < 13 or bits > 128 for bits in counts):
        raise RuntimeError("Unexpected serial clock count between SH edges: " + name)
    if max(counts.values()) < sum(counts.values()) * 0.95:
        raise RuntimeError("Inconsistent FM frame timing: " + name)


def run():
    _check_platform()
    print("YM2203 Rev C / silent FM capture v1.1")
    print("DAC_ALLOW and LINE_ALLOW stay 0. No sound is expected.")
    bus = capture = None
    try:
        bus = RevCFMBus()
        _diagnose(bus)
        bus.prepare()
        capture = Capture()
        capture.open()
        results = []
        for name, key in (("KEY OFF 1", 0), ("KEY ON", 0x10), ("KEY OFF 2", 0)):
            bus.write_fm(0x28, key)
            time.sleep_ms(300)
            result = analyze(capture.read())
            report(name, result)
            results.append(result)
        off1, on, off2 = results
        if on["unique"] < 8 or on["unique"] <= max(off1["unique"], off2["unique"]):
            raise RuntimeError("FM data did not change clearly with key-on; report the full log")
    except BaseException:
        print("FAIL or interrupted. Save the full log; do not enable FM audio yet.")
        raise
    finally:
        try:
            if bus is None:
                _emergency_stop()
            else:
                bus.close()
        finally:
            if capture is not None:
                capture.close()
        print("SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 capture=stopped")
    print("PASS: FM clocks/frames/key response detected. Send the FULL log before PCM playback.")


if __name__ == "__main__":
    run()
