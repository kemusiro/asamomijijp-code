# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Replace a completed nine-note score,then reuse it across FM and SSG PLAY."""
import time
import rev_c_i2c_queue_mute_host as muted

queue, mixer = muted.queue, muted.mixer
SCALE = (0, 1, 2, 3, 4, 3, 2, 1, 0)
ALTERNATE = (0, 2, 4, 2, 0, 1, 3, 1, 0)


def verify_score(i2c, score):
    if mixer.read_at(i2c, 0x30, 9) != bytes(score):
        raise RuntimeError("Replacement score readback mismatch")


def upload_score(i2c, remote, score):
    # This diagnostic reuses the existing final-state checker,which expects
    # the melody to end at index0. This is not a general music-file API.
    if len(score) != 9 or any(type(n) is not int or not 0 <= n < 5 for n in score) or score[-1] != 0:
        raise ValueError("Diagnostic score requires nine indices0..4 and final index0")
    remote.command(queue.CLEAR, 0)
    empty = bytes((remote.ack, queue.CLEAR, 0, 0, 0, 0)) + bytes(queue.pitch.INITIAL) + bytes((0, 0, 0, 255))
    if mixer.read_at(i2c, 0x10, 16) != empty:
        raise RuntimeError("CLEAR did not produce stopped empty queue")
    muted.check_gates(i2c, 0)
    for note in score:
        remote.command(queue.APPEND + note, 0)
    verify_score(i2c, score)
    queue.verify(i2c, remote, 0, 0, 255)
    print("PASS: uploaded score=%r;count9,stopped sources and gates0" % (list(score),))


def play(i2c, remote, command, voice, mask, score):
    verify_score(i2c, score)
    remote.command(command, None)
    keeps = muted.accomp.wait_run(i2c, remote, voice, mask)
    verify_score(i2c, score)
    remote.command(mixer.STOP, 0)
    queue.verify(i2c, remote, queue.DONE, 9, voice)
    muted.check_gates(i2c, 0)
    time.sleep_ms(1000)
    return keeps


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=muted.SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    print("Three complete scores:FM scale,FM replacement,then same replacement on SSG. Sound starts in5 seconds.")
    time.sleep_ms(5000)
    upload_score(i2c, remote, SCALE)
    print("SCORE 1/3 / FM melody + SSG low chord / C D E F G F E D C")
    keeps = play(i2c, remote, queue.PLAY_FM, 0, 57, SCALE)
    print("REPLACE / sources stopped;CLEAR then nine new notes;capture stays running")
    upload_score(i2c, remote, ALTERNATE)
    print("SCORE 2/3 / FM melody + SSG low chord / C E G E C D F D C")
    keeps += play(i2c, remote, queue.PLAY_FM, 0, 57, ALTERNATE)
    print("REUSE / no CLEAR,APPEND or START")
    print("SCORE 3/3 / SSG melody + FM high chord / C E G E C D F D C")
    keeps += play(i2c, remote, queue.PLAY_SSG, 3, 15, ALTERNATE)
    final = (remote.ack + 1) & 255
    if final != (69 + keeps) & 255:
        raise RuntimeError("Replacement score ACK accounting mismatch")
    print("EXPECTED QUEUE: runs=3 completed=3 aborted=0 events=27 pitch_writes=54 partial_cancels=0")
    print("EXPECTED ACCOMP: run_masks=[57,57,15] applied=0 / SIX I2C jobs=5 writes=24 / lease_expirations=0")
    print("EXPECTED QUEUE GATES: commands=0 dac_mutes=0 line_mutes=0 restores=0 gates=0;all27 GATE NOTES=3")
    print("EXPECTED FINAL SCORE: [0,2,4,2,0,1,3,1,0] / uploads=2 APPEND=18 capture_START=1")
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: original FM score,replaced FM score,same SSG score,readback integrity and all three normal completions")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C queued score replacement HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
