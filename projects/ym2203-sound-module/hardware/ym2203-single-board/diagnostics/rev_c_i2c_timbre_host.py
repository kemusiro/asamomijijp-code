# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Listen to four TL and three MULTI settings without retriggering the FM note."""
import time
import rev_c_i2c_fm_staged_host as staged


mixer = staged.mixer
SIGNATURE = b"RCTIM01!"
TL_BASE, MULTI_BASE = 0x60, 0x70
TL_VALUES, MULTI_VALUES = (96, 64, 40, 24), (1, 2, 3)


class Remote(mixer.Remote):
    max_opcode = 0x72
    max_mode = mixer.FM


def verify(i2c, remote, opcode, mode, selected):
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, opcode, mode, 0, selected[0], selected[1]))
    if actual != expected:
        raise RuntimeError("Timbre state mismatch: expected=%r actual=%r" % (expected, actual))


def select(i2c, remote, command, mode, selected):
    remote.command(command, mode)
    selected[0 if command < MULTI_BASE else 1] = command - (TL_BASE if command < MULTI_BASE else MULTI_BASE)
    verify(i2c, remote, command, mode, selected)


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    selected = [2, 0]
    verify(i2c, remote, mixer.KEEP, 0, selected)
    remote.command(mixer.START, 0)
    verify(i2c, remote, mixer.START, 0, selected)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: timbre START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Four TL settings, then three MULTI settings. SSG stays off. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    select(i2c, remote, TL_BASE, 0, selected)  # softest modulation before sound
    remote.command(mixer.FM, mixer.FM)
    last = mixer.FM
    for index, value in enumerate(TL_VALUES):
        print("%d/8 LIVE TL=%d / about 2 seconds / smaller TL = stronger modulation" % (index + 1, value))
        verify(i2c, remote, last, mixer.FM, selected)
        select(i2c, remote, TL_BASE + index, mixer.FM, selected)
        remote.hold(mixer.FM)
        verify(i2c, remote, mixer.KEEP, mixer.FM, selected)
        last = mixer.KEEP
    select(i2c, remote, TL_BASE + 2, mixer.FM, selected)  # TL 40 for MULTI comparison
    last = TL_BASE + 2
    for index, value in enumerate(MULTI_VALUES):
        print("%d/8 LIVE MULTI=%d / about 2 seconds / carrier remains MULTI=1" % (index + 5, value))
        verify(i2c, remote, last, mixer.FM, selected)
        select(i2c, remote, MULTI_BASE + index, mixer.FM, selected)
        remote.hold(mixer.FM)
        verify(i2c, remote, mixer.KEEP, mixer.FM, selected)
        last = mixer.KEEP
    remote.command(mixer.STOP, 0)
    verify(i2c, remote, mixer.STOP, 0, selected)
    print("STOP / 1 second silence")
    time.sleep_ms(1000)
    select(i2c, remote, TL_BASE + 2, 0, selected)
    select(i2c, remote, MULTI_BASE, 0, selected)
    print("8/8 RETRIGGER / TL=40 MULTI=1 / about 2 seconds")
    remote.command(mixer.FM, mixer.FM)
    remote.hold(mixer.FM)
    verify(i2c, remote, mixer.KEEP, mixer.FM, selected)
    remote.command(mixer.STOP, 0)
    verify(i2c, remote, mixer.STOP, 0, selected)
    print("STOP / 1 second silence")
    time.sleep_ms(1000)
    print("LEASE TEST / short FM tone; auto-mute after about 1 second")
    remote.command(mixer.FM, mixer.FM)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, mixer.FM, 0, 1, selected[0], selected[1]))
    if actual != expected:
        raise RuntimeError("Timbre lease mute mismatch: %r" % actual)
    print("PASS: final lease mute; TL/MULTI selection retained")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: four TL settings, three MULTI settings, retrigger, state readbacks and final lease mute")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for timbre-control READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C live FM timbre HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
