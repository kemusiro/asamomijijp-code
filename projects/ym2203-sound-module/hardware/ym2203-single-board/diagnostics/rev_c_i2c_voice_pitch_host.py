# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Move each of six melodies independently over a held opposite-family chord."""
import time
import rev_c_i2c_six_host as six


mixer = six.mixer
SIGNATURE = b"RCPOL01!"
INITIAL = (0, 2, 4, 0, 2, 4)
MELODY = (0, 1, 2, 3, 4, 3, 2, 1, 0)
NAMES = ("C", "D", "E", "F", "G")
VOICES = ("FM CH1", "FM CH2", "FM CH3", "SSG A", "SSG B", "SSG C")


class Remote(six.Remote):
    max_opcode = 0x9D


def verify(i2c, remote, last, mode, mask, pitches, expired=0):
    actual = mixer.read_at(i2c, 0x10, 12)
    expected = bytes((remote.ack, last, mode, expired, mask, 0)) + bytes(pitches)
    if actual != expected:
        raise RuntimeError("Per-voice state mismatch: expected=%r actual=%r" % (expected, actual))


def select(i2c, remote, voice, note, mode, mask, pitches):
    command = 0x80 + 5 * voice + note
    remote.command(command, mode)
    pitches[voice] = note
    verify(i2c, remote, command, mode, mask, pitches)
    return command


def reset_pitches(i2c, remote, pitches, melody_voice=-1):
    for voice in range(6):
        select(i2c, remote, voice, 0 if voice == melody_voice else INITIAL[voice], 0, 0, pitches)


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    pitches = bytearray(INITIAL)
    verify(i2c, remote, mixer.KEEP, 0, 0, pitches)
    remote.command(mixer.START, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    verify(i2c, remote, mixer.KEEP, 0, 0, pitches)
    print("PASS: per-voice START, eight KEEP commands and all six pitch indices")
    print("Six scales: one melody plus the opposite-family chord. Sound follows after 5 seconds.")
    time.sleep_ms(5000)
    for voice in range(6):
        # Prepare everything muted, including the first C. Never send a
        # redundant C command after opening the output gates.
        reset_pitches(i2c, remote, pitches, melody_voice=voice)
        mask = (1 << voice) | (56 if voice < 3 else 7)
        print("SECTION %d/6 / %s melody / %s held chord" %
              (voice + 1, VOICES[voice], "SSG C3-E3-G3" if voice < 3 else "FM C4-E4-G4"))
        command = 0x40 + mask
        remote.command(command, 1)
        verify(i2c, remote, command, 1, mask, pitches)
        for index, note in enumerate(MELODY):
            print("  NOTE %d/9 / %s%d" % (index + 1, NAMES[note], 4 if voice < 3 else 3))
            if index:
                select(i2c, remote, voice, note, 1, mask, pitches)
            # Note commands refresh the lease; add KEEP for the bounded hold.
            # ACK/state verification makes this a diagnostic, not a sequencer.
            time.sleep_ms(450)
            remote.command(mixer.KEEP, 1)
            verify(i2c, remote, mixer.KEEP, 1, mask, pitches)
        remote.command(mixer.STOP, 0)
        verify(i2c, remote, mixer.STOP, 0, 0, pitches)
        print("SECTION %d/6 PASS / STOP / 1 second silence" % (voice + 1))
        time.sleep_ms(1000)
    reset_pitches(i2c, remote, pitches)
    print("LEASE TEST / original six-voice chord; auto-mute after about 1 second")
    remote.command(0x7F, 1)
    time.sleep_ms(1600)
    verify(i2c, remote, 0x7F, 0, 0, pitches, expired=1)
    print("PASS: all six sources lease-muted; pitch indices retained")
    remote.command(mixer.STOP, 0)
    verify(i2c, remote, mixer.STOP, 0, 0, pitches)
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % ((remote.ack + 1) & 255))
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: six independent melodies over held chords, all pitch readbacks and final lease cleanup")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    six.staged.startup.check(i2c)
    print("STARTUP PASS: wait 3 seconds for per-voice pitch READY")
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C per-voice pitch HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
