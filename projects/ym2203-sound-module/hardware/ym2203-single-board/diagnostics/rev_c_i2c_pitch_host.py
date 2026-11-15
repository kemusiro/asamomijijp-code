# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Play C D E F G F E D C on FM alone, then SSG alone, twice each."""
import time
import rev_c_i2c_fm_staged_host as staged


mixer = staged.mixer
SIGNATURE = b"RCPIT01!"
MELODY = (0, 1, 2, 3, 4, 3, 2, 1, 0)
NAMES = ("C4", "D4", "E4", "F4", "G4")


class Remote(mixer.Remote):
    max_opcode = 0x54


def verify(i2c, remote, opcode, mode, selected):
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, opcode, mode, 0, selected[0], selected[1]))
    if actual != expected:
        raise RuntimeError("Pitch state mismatch: expected=%r actual=%r" % (expected, actual))


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    selected = [255, 255]
    verify(i2c, remote, mixer.KEEP, 0, selected)
    remote.command(mixer.START, 0)
    verify(i2c, remote, mixer.START, 0, selected)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: pitch target START and eight live KEEP commands; ACK idle gap=40 ms")
    print("FM scale twice, then SSG scale twice. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    last = mixer.KEEP
    for source, mode, base in ((0, mixer.FM, 0x40), (1, mixer.SSG, 0x50)):
        for repetition in range(2):
            verify(i2c, remote, last, 0, selected)
            remote.command(base, 0)  # select C before opening the output
            selected[source] = 0
            verify(i2c, remote, base, 0, selected)
            for position, note in enumerate(MELODY):
                print("%s %d/2 NOTE %d/9 / %s" %
                      ("FM" if source == 0 else "SSG", repetition + 1, position + 1, NAMES[note]))
                if position == 0:
                    # C was selected while STOPped; start the note here and
                    # avoid an extra pitch command/ACK after opening the gate.
                    verify(i2c, remote, base, 0, selected)
                    remote.command(mode, mode)
                    verify(i2c, remote, mode, mode, selected)
                else:
                    verify(i2c, remote, last, mode, selected)
                    remote.command(base + note, mode)
                    selected[source] = note
                    verify(i2c, remote, base + note, mode, selected)
                # Two short KEEP intervals per note; every reply must retain
                # the selected pitch and the unexpired solo mode.
                for unused in range(2):
                    time.sleep_ms(200)
                    remote.command(mixer.KEEP, mode)
                    verify(i2c, remote, mixer.KEEP, mode, selected)
                last = mixer.KEEP
            remote.command(mixer.STOP, 0)
            last = mixer.STOP
            verify(i2c, remote, last, 0, selected)
            print("STOP / 1 second silence")
            time.sleep_ms(1000)
    print("LEASE TEST / short SSG C4; auto-mute after about 1 second")
    remote.command(mixer.SSG, mixer.SSG)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, mixer.SSG, 0, 1, selected[0], selected[1]))
    if actual != expected:
        raise RuntimeError("Pitch lease mute mismatch: %r" % actual)
    print("PASS: final lease mute; pitch selection retained")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: two FM scales, two SSG scales, pitch readbacks and final lease mute")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for pitch-control READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C FM + SSG pitch HOST v1.1 / OTHER Pico only")


if __name__ == "__main__":
    run()
