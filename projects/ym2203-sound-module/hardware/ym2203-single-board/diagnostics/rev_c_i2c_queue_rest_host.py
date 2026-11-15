# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""FM,SSG,FM: six tone slots plus three melody-only rests over a held chord."""
import time
import rev_c_i2c_queue_mute_host as muted

queue, mixer = muted.queue, muted.mixer
SIGNATURE = b"RCQRS01!"
REST, APPEND_REST = 5, 9
SCORE = (0, 2, REST, 4, REST, 2, 1, REST, 0)


def verify_score(i2c):
    if mixer.read_at(i2c, 0x30, 9) != bytes(SCORE):
        raise RuntimeError("Rest score readback mismatch")


def upload(i2c, remote):
    remote.command(queue.CLEAR, 0)
    for note in SCORE:
        remote.command(APPEND_REST if note == REST else queue.APPEND + note, 0)
    verify_score(i2c)
    queue.verify(i2c, remote, 0, 0, 255)
    muted.check_gates(i2c, 0)
    print("PASS: uploaded nine slots [C,E,REST,G,REST,E,D,REST,C];all sources stopped")


def wait_run(i2c, remote, voice, mask, run):
    started = time.ticks_ms()
    keeps = previous = 0
    time.sleep_ms(40)
    if mixer.read_at(i2c, 0x28, 1) != bytes((mask,)):
        raise RuntimeError("Rest queue planned mask mismatch")
    while time.ticks_diff(time.ticks_ms(), started) < 8000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        state, progress = status[0], status[1]
        if not 1 <= state <= queue.DONE or not previous <= progress <= 9:
            raise RuntimeError("Rest queue progress mismatch: %r" % status)
        previous = progress
        if state == queue.DONE:
            queue.verify(i2c, remote, queue.DONE, 9, voice)
            muted.check_gates(i2c, 0)
            verify_score(i2c)
            if mixer.read_at(i2c, 0x2A, 2) != bytes((run*3, run*6)):
                raise RuntimeError("Rest/tone event counts mismatch")
            print("PASS: run%d complete;six melody tones,three rests;KEEP=%d" % (run, keeps))
            return keeps
    raise RuntimeError("Rest queue completion timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    upload(i2c, remote)
    print("FM,SSG,FM melody over held opposite chord. Each rest removes only melody. Sound starts in5 seconds.")
    time.sleep_ms(5000)
    keeps = 0
    for run, command, voice, mask in ((1, queue.PLAY_FM, 0, 57), (2, queue.PLAY_SSG, 3, 15), (3, queue.PLAY_FM, 0, 57)):
        verify_score(i2c)
        print("REST SCORE %d/3 / %s melody / C E REST G REST E D REST C /500ms per slot" %
              (run, "FM" if voice == 0 else "SSG"))
        remote.command(command, None)
        keeps += wait_run(i2c, remote, voice, mask, run)
        remote.command(mixer.STOP, 0)
        queue.verify(i2c, remote, queue.DONE, 9, voice)
        time.sleep_ms(1000)
    final = (remote.ack + 1) & 255
    if final != (59 + keeps) & 255:
        raise RuntimeError("Rest queue ACK accounting mismatch")
    print("EXPECTED QUEUE: runs=3 completed=3 aborted=0 events=27 pitch_writes=36 partial_cancels=0")
    print("EXPECTED REST QUEUE: tones=18 rests=9 rest_key_offs=9 resume_key_ons=9 pair_step=0")
    print("EXPECTED ACCOMP: run_masks=[57,15,57] applied=0 / SIX I2C jobs=5 writes=42 / lease_expirations=0")
    print("EXPECTED REST SLOTS: score=[0,2,5,4,5,2,1,5,0];rest masks=56 for FM,7 for SSG")
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: three queued scores,six tones plus three rests each,held companions and all-source normal end")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C queued melody rest HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
