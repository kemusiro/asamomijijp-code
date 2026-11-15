# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""STOP an accompanied queue,stay quiet,and replay the unchanged score."""
import time
import rev_c_i2c_queue_accomp_host as accomp
import rev_c_i2c_queue_stop_host as stop

queue, mixer = accomp.queue, accomp.mixer


def stop_after_three(i2c, remote, voice, mask, pitches):
    started = time.ticks_ms()
    keeps = previous = checks = 0
    time.sleep_ms(40)
    if mixer.read_at(i2c, 0x28, 1) != bytes((mask,)):
        raise RuntimeError("Accompanied STOP planned mask mismatch")
    while time.ticks_diff(time.ticks_ms(), started) < 5000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        if status[0] not in (1, 2) or not previous <= status[1] < 9:
            raise RuntimeError("Accompanied STOP progress mismatch: %r" % status)
        previous = status[1]
        if status[0] == 2:
            time.sleep_ms(40)
            if mixer.read_at(i2c, 0x14, 1) != bytes((mask,)):
                raise RuntimeError("Accompanied STOP live mask mismatch")
            checks += 1
        if previous >= 3:
            if checks < 2:
                raise RuntimeError("Accompanied STOP mask coverage incomplete")
            print("ACCOMP STOP / %s melody + held chord / observed notes=%d mask=%d checks=%d" %
                  ("FM" if voice == 0 else "SSG", previous, mask, checks))
            remote.command(mixer.STOP, 0)
            progress = stop.verify_cancelled(i2c, remote, voice, pitches)
            print("STOP acknowledged / all four voices off / expect%d ms silence; no KEEP or PLAY" % stop.QUIET_MS)
            time.sleep_ms(stop.QUIET_MS)
            stop.verify_cancelled(i2c, remote, voice, pitches, expected_progress=progress)
            if mixer.read_at(i2c, 0x28, 1) != bytes((mask,)):
                raise RuntimeError("Accompanied STOP changed planned mask")
            print("PASS: accompanied STOP stayed quiet beyond old end; score and progress unchanged")
            return keeps, progress
    raise RuntimeError("Accompanied STOP observation timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=accomp.SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    pitches = bytearray(queue.pitch.INITIAL)
    queue.upload(i2c, remote)
    print("FM+chord STOP,replay same score from C,then SSG+chord STOP. Sound starts in5 seconds.")
    time.sleep_ms(5000)
    remote.command(queue.PLAY_FM, None)
    keeps, first = stop_after_three(i2c, remote, 0, 57, pitches)
    print("RESTART FM + SSG chord / same stored score / full C D E F G F E D C")
    remote.command(queue.PLAY_FM, None)
    keeps += accomp.wait_run(i2c, remote, 0, 57)
    pitches[0] = 0
    remote.command(mixer.STOP, 0)
    queue.verify(i2c, remote, queue.DONE, 9, 0)
    time.sleep_ms(1000)
    remote.command(queue.PLAY_SSG, None)
    extra, last = stop_after_three(i2c, remote, 3, 15, pitches)
    keeps += extra
    final = (remote.ack + 1) & 255
    if final != (59 + keeps) & 255:
        raise RuntimeError("Accompanied STOP ACK accounting mismatch")
    events = first + 9 + last
    print("EXPECTED QUEUE: runs=3 completed=1 aborted=2 events=%d pitch_writes=%d..%d partial_cancels=0..2" %
          (events, 2*events, 2*events+2))
    print("EXPECTED ACCOMP: run_masks=[57,57,15] applied=0 / SIX I2C jobs=5 writes=24 / lease_expirations=0")
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: accompanied FM/SSG STOP,all-voice quiet beyond old end,unchanged score and FM restart from C")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C accompanied queue STOP HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
