# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Four FM scales, with silent timbre setup and a separate C onset for each."""
import time
import rev_c_i2c_timbre_host as timbre


mixer = timbre.mixer
SIGNATURE = b"RCCMB01!"
MELODY = (0, 1, 2, 3, 4, 3, 2, 1, 0)
NAMES = ("C4", "D4", "E4", "F4", "G4")
PRESETS = ((0, 0), (2, 0), (2, 1), (2, 2))  # TL96/M1, TL40/M1, TL40/M2, TL40/M3


def verify(i2c, remote, opcode, mode, selected):
    actual = mixer.read_at(i2c, 0x10, 7)
    expected = bytes((remote.ack, opcode, mode, 0, selected[0], selected[1], selected[2]))
    if actual != expected:
        raise RuntimeError("Combined state mismatch: expected=%r actual=%r" % (expected, actual))


def select(i2c, remote, opcode, mode, selected):
    # Only fixed presets; rejected input must not reach the wire.
    if type(opcode) is not int:
        raise ValueError("Combined selection must be an integer")
    if 0x40 <= opcode <= 0x44:
        slot, index = 2, opcode - 0x40
    elif 0x60 <= opcode <= 0x63:
        slot, index = 0, opcode - 0x60
    elif 0x70 <= opcode <= 0x72:
        slot, index = 1, opcode - 0x70
    else:
        raise ValueError("Unsupported combined preset")
    remote.command(opcode, mode)
    selected[slot] = index
    verify(i2c, remote, opcode, mode, selected)


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=timbre.Remote)
    selected = [2, 0, 255]
    verify(i2c, remote, mixer.KEEP, 0, selected)
    remote.command(mixer.START, 0)
    verify(i2c, remote, mixer.START, 0, selected)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: combined START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Four FM scales with different timbres; 1 second silence between scales. SSG off.")
    print("Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    last = mixer.KEEP
    for round_index, (tl_index, multi_index) in enumerate(PRESETS):
        verify(i2c, remote, last, 0, selected)
        print("SCALE %d/4 / TL=%d MULTI=%d / prepare while silent" %
              (round_index + 1, timbre.TL_VALUES[tl_index], timbre.MULTI_VALUES[multi_index]))
        # Keep the previous final C separate from this initial C. All setup
        # and its ACK/readback time happen with sources and output gates off.
        select(i2c, remote, 0x60 + tl_index, 0, selected)
        select(i2c, remote, 0x70 + multi_index, 0, selected)
        select(i2c, remote, 0x40, 0, selected)
        last = 0x40
        for position, note in enumerate(MELODY):
            print("SCALE %d/4 NOTE %d/9 / %s" % (round_index + 1, position + 1, NAMES[note]))
            if position == 0:
                verify(i2c, remote, last, 0, selected)
                remote.command(mixer.FM, mixer.FM)
                verify(i2c, remote, mixer.FM, mixer.FM, selected)
            else:
                verify(i2c, remote, last, mixer.FM, selected)
                select(i2c, remote, 0x40 + note, mixer.FM, selected)
            for unused in range(2):
                time.sleep_ms(200)
                remote.command(mixer.KEEP, mixer.FM)
                verify(i2c, remote, mixer.KEEP, mixer.FM, selected)
            last = mixer.KEEP
        remote.command(mixer.STOP, 0)
        verify(i2c, remote, mixer.STOP, 0, selected)
        last = mixer.STOP
        print("SCALE %d/4 PASS / ack=%d" % (round_index + 1, remote.ack))
        print("STOP / 1 second silence")
        time.sleep_ms(1000)
    print("LEASE TEST / short final FM C4; auto-mute after about 1 second")
    remote.command(mixer.FM, mixer.FM)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 7)
    expected = bytes((remote.ack, mixer.FM, 0, 1, selected[0], selected[1], selected[2]))
    if actual != expected:
        raise RuntimeError("Combined lease mute mismatch: %r" % actual)
    print("PASS: final lease mute; pitch and timbre selections retained")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: four scales, silent timbre setup, separate C starts and final lease mute")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    timbre.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for combined-control READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C combined FM pitch + timbre HOST v1.2 / OTHER Pico only")


if __name__ == "__main__":
    run()
