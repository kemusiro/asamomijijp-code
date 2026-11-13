# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Cancel queued FM/SSG with STOP and replay the unchanged score from C."""
import time
import rev_c_i2c_queue_host as queue

mixer = queue.mixer
QUIET_MS = 4000


def verify_cancelled(i2c, remote, voice, pitches, expected_progress=None):
    actual = mixer.read_at(i2c, 0x10, 16)
    progress = actual[14]
    if not 3 <= progress < 9 or (expected_progress is not None and progress != expected_progress):
        raise RuntimeError("STOP queue progress changed or cancellation was too late: %r" % actual)
    pitches[voice] = queue.pitch.MELODY[progress - 1]
    expected = bytes((remote.ack, mixer.STOP, 0, 0, 0, 0)) + bytes(pitches) + bytes((9, queue.ABORTED, progress, voice))
    if actual != expected:
        raise RuntimeError("STOP queue state mismatch: expected=%r actual=%r" % (expected, actual))
    if mixer.read_at(i2c, 0x30, 9) != bytes(queue.pitch.MELODY):
        raise RuntimeError("STOP unexpectedly changed uploaded score")
    return progress


def stop_after_three(i2c, remote, voice, pitches):
    started = time.ticks_ms()
    keeps = previous = 0
    while time.ticks_diff(time.ticks_ms(), started) < 5000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        if status[0] not in (1, 2) or not previous <= status[1] < 9:
            raise RuntimeError("Queue cancellation observation mismatch: %r" % status)
        previous = status[1]
        if previous >= 3:
            print("STOP REQUEST / %s / observed notes=%d" % ("FM" if voice == 0 else "SSG", previous))
            remote.command(mixer.STOP, 0)
            progress = verify_cancelled(i2c, remote, voice, pitches)
            print("STOP acknowledged / notes=%d / expect%d ms silence; no KEEP or PLAY" % (progress, QUIET_MS))
            time.sleep_ms(QUIET_MS)
            verify_cancelled(i2c, remote, voice, pitches, expected_progress=progress)
            print("PASS: STOP cancelled remaining notes and preserved score; progress stayed%d" % progress)
            return keeps, progress
    raise RuntimeError("Queue STOP observation timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=queue.SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    pitches = bytearray(queue.pitch.INITIAL)
    queue.upload(i2c, remote)
    print("FM STOP,FM restart from C,then SSG STOP. Sound starts in5 seconds.")
    time.sleep_ms(5000)
    remote.command(queue.PLAY_FM, None)
    keeps, first = stop_after_three(i2c, remote, 0, pitches)
    # No CLEAR,APPEND or START: replay the same stored score from its beginning.
    print("RESTART FM / same uploaded score / full C D E F G F E D C")
    remote.command(queue.PLAY_FM, None)
    keeps += queue.wait_run(i2c, remote, 0)
    pitches[0] = 0
    remote.command(mixer.STOP, 0)
    queue.verify(i2c, remote, queue.DONE, 9, 0)
    time.sleep_ms(1000)
    print("SSG STOP / same score / short C D E then STOP")
    remote.command(queue.PLAY_SSG, None)
    extra, last = stop_after_three(i2c, remote, 3, pitches)
    keeps += extra
    final = (remote.ack + 1) & 255
    if final != (59 + keeps) & 255:
        raise RuntimeError("Queue STOP/restart ACK accounting mismatch")
    events = first + 9 + last
    print("EXPECTED QUEUE: runs=3 completed=1 aborted=2 events=%d pitch_writes=%d..%d partial_cancels=0..2" %
          (events, events*2, events*2+2))
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: queued FM/SSG STOP,quiet beyond old end,unchanged score and explicit FM restart from C")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C queue STOP and restart HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
