# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Final initial-commissioning check:rest STOP,replay,then lease cancellation."""
import time
import rev_c_i2c_queue_rest_host as rest

queue, mixer = rest.queue, rest.mixer
QUIET_MS, NO_TRAFFIC_MS = 4000, 1800


def counts(progress):
    tones = rests = resumes = 0
    for index in range(progress):
        if rest.SCORE[index] == rest.REST: rests += 1
        else:
            tones += 1
            if index and rest.SCORE[index - 1] == rest.REST: resumes += 1
    return tones, rests, resumes


def verify_stopped(i2c, remote, state, progress, voice, expired, pitches, totals):
    for note in rest.SCORE[:progress]:
        if note != rest.REST: pitches[voice] = note
    expected = bytes((remote.ack, remote.last, 0, expired, 0, 0)) + bytes(pitches) + bytes((9, state, progress, voice))
    if mixer.read_at(i2c, 0x10, 16) != expected:
        raise RuntimeError("Final rest state/pitch/lease mismatch")
    rest.verify_score(i2c)
    rest.muted.check_gates(i2c, 0)
    if mixer.read_at(i2c, 0x2A, 2) != bytes((totals[1], totals[0])):
        raise RuntimeError("Final rest cumulative event counts mismatch")


def first_rest(i2c, remote):
    started = time.ticks_ms()
    keeps = 0
    while time.ticks_diff(time.ticks_ms(), started) < 3000:
        time.sleep_ms(80)
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        if status[0] not in (1, 2) or status[1] > 3:
            raise RuntimeError("First melody rest observation missed: %r" % status)
        if status[0] == 2 and status[1] == 3:
            return keeps
    raise RuntimeError("First melody rest observation timeout")


def wait_complete(i2c, remote):
    started = time.ticks_ms()
    keeps = previous = 0
    while time.ticks_diff(time.ticks_ms(), started) < 8000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        if not 1 <= status[0] <= queue.DONE or not previous <= status[1] <= 9:
            raise RuntimeError("Final rest replay progress mismatch")
        previous = status[1]
        if status[0] == queue.DONE:
            if previous != 9: raise RuntimeError("Final rest replay incomplete")
            return keeps
    raise RuntimeError("Final rest replay completion timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=rest.SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    rest.upload(i2c, remote)
    pitches = bytearray(queue.pitch.INITIAL)
    print("FINAL INITIAL COMMISSIONING / rest STOP,full replay,rest lease. Both volumes low. Sound starts in5 seconds.")
    time.sleep_ms(5000)
    remote.command(queue.PLAY_FM, None)
    keeps = first_rest(i2c, remote)
    remote.command(mixer.STOP, 0)
    totals = counts(3)
    verify_stopped(i2c, remote, queue.ABORTED, 3, 0, 0, pitches, totals)
    print("FINAL 1/3 PASS / STOP at first FM rest;SSG chord also stopped;expect4000ms quiet")
    time.sleep_ms(QUIET_MS)
    verify_stopped(i2c, remote, queue.ABORTED, 3, 0, 0, pitches, totals)
    print("FINAL 2/3 / explicit PLAY,same stored FM rest score+SSG chord,from C;no reupload")
    remote.command(queue.PLAY_FM, None)
    keeps += wait_complete(i2c, remote)
    full = counts(9)
    totals = tuple(totals[i] + full[i] for i in range(3))
    verify_stopped(i2c, remote, queue.DONE, 9, 0, 0, pitches, totals)
    remote.command(mixer.STOP, 0)
    verify_stopped(i2c, remote, queue.DONE, 9, 0, 0, pitches, totals)
    print("FINAL 2/3 PASS / all nine slots,six tones+three rests;all voices stopped")
    time.sleep_ms(1000)
    remote.command(queue.PLAY_SSG, None)
    keeps += first_rest(i2c, remote)
    print("FINAL 3/3 / first SSG rest observed;no I2C for1800ms;lease must stop melody and FM chord")
    time.sleep_ms(NO_TRAFFIC_MS)
    status = mixer.read_at(i2c, 0x1D, 2)
    if status[0] != queue.ABORTED or not 4 <= status[1] < 9:
        raise RuntimeError("Final rest lease cancellation mismatch")
    progress = status[1]
    tail = counts(progress)
    totals = tuple(totals[i] + tail[i] for i in range(3))
    verify_stopped(i2c, remote, queue.ABORTED, progress, 3, 1, pitches, totals)
    print("FINAL 3/3 LEASE PASS / progress=%d;expect4000ms quiet,no resumed notes" % progress)
    time.sleep_ms(QUIET_MS)
    verify_stopped(i2c, remote, queue.ABORTED, progress, 3, 1, pitches, totals)
    remote.command(mixer.STOP, 0)
    verify_stopped(i2c, remote, queue.ABORTED, progress, 3, 0, pitches, totals)
    final = (remote.ack + 1) & 255
    if final != (59 + keeps) & 255:
        raise RuntimeError("Final rest ACK accounting mismatch")
    print("EXPECTED QUEUE: runs=3 completed=1 aborted=2 events=%d pitch_writes=%d..%d partial_cancels=0..2" %
          (sum(totals[:2]), totals[0]*2, totals[0]*2+4))
    print("EXPECTED REST QUEUE: tones=%d rests=%d rest_key_offs=%d resume_key_ons=%d pair_step=0" %
          (totals[0], totals[1], totals[1], totals[2]))
    print("EXPECTED ACCOMP: run_masks=[57,57,15] applied=0 / SIX I2C jobs=6 writes=%d / lease_expirations=1" % (24+2*totals[2]))
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: final initial-commissioning rest STOP,replay,lease cleanup and quiet-state integrity")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C rest STOP-replay-lease final HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
