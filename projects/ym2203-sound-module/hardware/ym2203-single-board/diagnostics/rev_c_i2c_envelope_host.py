# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Six envelope/key comparisons with output gates open during key-off."""
import time
import rev_c_i2c_timbre_host as timbre


mixer = timbre.mixer
SIGNATURE = b"RCENV02!"
KEY_ON, KEY_OFF = 0x30, 0x31
SUSTAIN, DECAY = 0x80, 0x81


class Remote(timbre.Remote):
    max_opcode = DECAY


def verify(i2c, remote, opcode, mode, preset, keyed):
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, opcode, mode, 0, preset, keyed))
    if actual != expected:
        raise RuntimeError("Envelope state mismatch: expected=%r actual=%r" % (expected, actual))


def hold(i2c, remote, opcode, preset, keyed, label):
    verify(i2c, remote, opcode, mixer.FM, preset, keyed)
    print(label + " / about 2 seconds")
    remote.hold(mixer.FM)
    verify(i2c, remote, mixer.KEEP, mixer.FM, preset, keyed)


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    verify(i2c, remote, mixer.KEEP, 0, 1, 0)
    remote.command(mixer.START, 0)
    verify(i2c, remote, mixer.START, 0, 1, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("PASS: envelope START and eight live KEEP commands; ACK idle gap=40 ms")
    print("Six envelope/key comparisons. SSG off. Sound starts in 5 seconds.")
    time.sleep_ms(5000)
    remote.command(SUSTAIN, 0)
    verify(i2c, remote, SUSTAIN, 0, 0, 0)
    remote.command(mixer.FM, mixer.FM)
    hold(i2c, remote, mixer.FM, 0, 1, "1/6 SUSTAIN / steady FM")
    remote.command(KEY_OFF, mixer.FM)
    hold(i2c, remote, KEY_OFF, 0, 0, "2/6 KEY OFF / release then quiet / DAC+LINE remain on")
    remote.command(KEY_ON, mixer.FM)
    hold(i2c, remote, KEY_ON, 0, 1, "3/6 RETRIGGER / steady FM again")
    remote.command(mixer.STOP, 0)
    verify(i2c, remote, mixer.STOP, 0, 0, 0)
    print("STOP / 1 second silence; envelope setup follows while muted")
    time.sleep_ms(1000)
    remote.command(DECAY, 0)
    verify(i2c, remote, DECAY, 0, 1, 0)
    remote.command(mixer.FM, mixer.FM)
    hold(i2c, remote, mixer.FM, 1, 1, "4/6 DECAY 1 / attack then quieter while key remains on")
    remote.command(KEY_OFF, mixer.FM)
    hold(i2c, remote, KEY_OFF, 1, 0, "5/6 KEY OFF / quiet / DAC+LINE remain on")
    remote.command(KEY_ON, mixer.FM)
    hold(i2c, remote, KEY_ON, 1, 1, "6/6 DECAY 2 / repeat attack and decay")
    remote.command(mixer.STOP, 0)
    verify(i2c, remote, mixer.STOP, 0, 1, 0)
    print("STOP / 1 second silence")
    time.sleep_ms(1000)
    # A sustained final tone makes the one-second watchdog cutoff unambiguous.
    remote.command(SUSTAIN, 0)
    verify(i2c, remote, SUSTAIN, 0, 0, 0)
    print("LEASE TEST / short sustained FM; auto-mute after about 1 second")
    remote.command(mixer.FM, mixer.FM)
    time.sleep_ms(1600)
    actual = mixer.read_at(i2c, 0x10, 6)
    expected = bytes((remote.ack, mixer.FM, 0, 1, 0, 0))
    if actual != expected:
        raise RuntimeError("Envelope lease mute mismatch: %r" % actual)
    print("PASS: lease mute cleared mode/key state and closed output gates")
    time.sleep_ms(400)
    remote.command(mixer.STOP, 0)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: sustain, open-gate key-off, two decay attacks and final lease mute")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    timbre.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for envelope-control READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C FM envelope HOST v1.1 / OTHER Pico only")


if __name__ == "__main__":
    run()
