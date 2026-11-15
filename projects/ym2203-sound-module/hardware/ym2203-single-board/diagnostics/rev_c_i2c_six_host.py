# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Fifteen solo/chord/mute comparisons using fixed six-voice masks."""
import time
import rev_c_i2c_fm_staged_host as staged


mixer = staged.mixer
SIGNATURE = b"RCSIX01!"
MASK_BASE = 0x40
SECTIONS = ((1, "1/15 FM CH1 / C4"), (2, "2/15 FM CH2 / E4"),
            (4, "3/15 FM CH3 / G4"), (7, "4/15 FM CHORD / C4 E4 G4"),
            (8, "5/15 SSG A / C3"), (16, "6/15 SSG B / E3"),
            (32, "7/15 SSG C / G3"), (56, "8/15 SSG CHORD / C3 E3 G3"),
            (63, "9/15 SIX VOICES / both chords"))


class Remote(mixer.Remote):
    max_opcode = 0x7F


def verify(i2c, remote, opcode, mode, mask):
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, opcode, mode, 0, mask, 0))
    if actual != expected:
        raise RuntimeError("Six-voice state mismatch: expected=%r actual=%r" % (expected, actual))


def hold(i2c, remote, opcode, mode, mask):
    verify(i2c, remote, opcode, mode, mask)
    remote.hold(mode)
    verify(i2c, remote, mixer.KEEP, mode, mask)


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    verify(i2c, remote, mixer.KEEP, 0, 0)
    remote.command(mixer.START, 0)
    verify(i2c, remote, mixer.START, 0, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: six-voice START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Fifteen comparisons. Mask updates briefly mute and prime output. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    last, mode, mask = mixer.KEEP, 0, 0
    for mask_value, label in SECTIONS:
        verify(i2c, remote, last, mode, mask)
        print(label + " / about 2 seconds")
        remote.command(MASK_BASE + mask_value, 1)
        hold(i2c, remote, MASK_BASE + mask_value, 1, mask_value)
        last, mode, mask = mixer.KEEP, 1, mask_value
    for command, wanted, label in ((4, 4, "10/15 DAC MUTE / only SSG chord remains"),
                                    (3, 1, "11/15 RESTORE / six voices"),
                                    (5, 5, "12/15 LINE MUTE / all voices disappear"),
                                    (3, 1, "13/15 RESTORE / six voices")):
        verify(i2c, remote, last, mode, mask)
        print(label + " / about 2 seconds")
        remote.command(command, wanted)
        hold(i2c, remote, command, wanted, mask)
        last, mode = mixer.KEEP, wanted
    remote.command(mixer.STOP, 0)
    verify(i2c, remote, mixer.STOP, 0, 0)
    print("14/15 STOP / all sources and output gates off / 2 seconds")
    time.sleep_ms(2000)
    print("15/15 LEASE / short six-voice chord; auto-mute after about 1 second")
    remote.command(MASK_BASE + 63, 1)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 6)
    if actual != bytes((remote.ack, MASK_BASE + 63, 0, 1, 0, 0)):
        raise RuntimeError("Six-voice lease mute mismatch: %r" % actual)
    print("PASS: all six voices lease-muted and chip cleanup completed")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: six solo channels, both chords, six voices, independent mutes and lease cleanup")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for six-voice READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C six-voice HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
