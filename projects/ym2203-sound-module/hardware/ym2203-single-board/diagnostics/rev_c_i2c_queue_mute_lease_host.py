# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""A muted queue lease cancels all voices;explicit STOP then PLAY recovers."""
import time
import rev_c_i2c_queue_mute_host as muted
import rev_c_i2c_queue_stop_host as stop

queue, mixer = muted.queue, muted.mixer
NO_TRAFFIC_MS = 1800


def verify_expired(i2c, remote, voice, progress, mask):
    queue.verify(i2c, remote, queue.ABORTED, progress, voice, expired=1)
    muted.check_gates(i2c, 0)
    if mixer.read_at(i2c, 0x30, 9) != bytes(queue.pitch.MELODY):
        raise RuntimeError("Muted lease changed uploaded score")
    if mixer.read_at(i2c, 0x28, 1) != bytes((mask,)):
        raise RuntimeError("Muted lease changed planned mask")


def mute_then_expire(i2c, remote, voice, mask, mute, pitches):
    started = time.ticks_ms()
    keeps = previous = 0
    time.sleep_ms(40)
    if mixer.read_at(i2c, 0x28, 1) != bytes((mask,)):
        raise RuntimeError("Muted lease planned mask mismatch")
    while time.ticks_diff(time.ticks_ms(), started) < 5000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        state, progress = status[0], status[1]
        if state not in (1, 2) or not previous <= progress < 9:
            raise RuntimeError("Muted lease playback progress mismatch: %r" % status)
        previous = progress
        if state != 2:
            continue
        time.sleep_ms(40)
        if mixer.read_at(i2c, 0x14, 1) != bytes((mask,)):
            raise RuntimeError("Muted lease changed active voice mask")
        muted.check_gates(i2c, 3)
        if progress >= 3:
            print("QUEUE MUTE / %s / progress=%d;host will stop all I2C traffic" %
                  ("DAC: only SSG chord remains" if mute == mixer.DAC_MUTE else "LINE: all voices disappear", progress))
            remote.command(mute, 1)
            muted.check_gates(i2c, 2 if mute == mixer.DAC_MUTE else 1)
            print("NO I2C / %d ms / no KEEP,STOP or reads;lease must mute every source" % NO_TRAFFIC_MS)
            time.sleep_ms(NO_TRAFFIC_MS)
            status = mixer.read_at(i2c, 0x1D, 2)
            if status[0] != queue.ABORTED or not progress < status[1] < 9:
                raise RuntimeError("Muted lease cancellation/progress mismatch: %r" % status)
            progress = status[1]
            verify_expired(i2c, remote, voice, progress, mask)
            print("LEASE verified / notes=%d / expect%d ms silence;reads must not resume playback" % (progress, stop.QUIET_MS))
            time.sleep_ms(stop.QUIET_MS)
            verify_expired(i2c, remote, voice, progress, mask)
            print("PASS: muted lease cancelled all voices and remaining notes;four-second quiet and score intact")
            remote.command(mixer.STOP, 0)
            stop.verify_cancelled(i2c, remote, voice, pitches, expected_progress=progress)
            muted.check_gates(i2c, 0)
            print("RECOVERY STOP acknowledged / lease flag cleared;still silent until explicit PLAY")
            return keeps, progress
    raise RuntimeError("Muted lease observation timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=muted.SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    pitches = bytearray(queue.pitch.INITIAL)
    queue.upload(i2c, remote)
    print("Lease during DAC mute,explicit FM replay,then lease during LINE mute. Sound starts in5 seconds.")
    time.sleep_ms(5000)
    remote.command(queue.PLAY_FM, None)
    keeps, first = mute_then_expire(i2c, remote, 0, 57, mixer.DAC_MUTE, pitches)
    print("RECOVERY PLAY / same stored FM score+SSG chord / no RESTORE or reupload / all9 notes from C")
    remote.command(queue.PLAY_FM, None)
    keeps += muted.accomp.wait_run(i2c, remote, 0, 57)
    pitches[0] = 0
    remote.command(mixer.STOP, 0)
    queue.verify(i2c, remote, queue.DONE, 9, 0)
    muted.check_gates(i2c, 0)
    time.sleep_ms(1000)
    remote.command(queue.PLAY_SSG, None)
    extra, last = mute_then_expire(i2c, remote, 3, 15, mixer.LINE_MUTE, pitches)
    keeps += extra
    final = (remote.ack + 1) & 255
    if final != (61 + keeps) & 255:
        raise RuntimeError("Muted lease ACK accounting mismatch")
    events = first + 9 + last
    print("EXPECTED QUEUE: runs=3 completed=1 aborted=2 events=%d pitch_writes=%d..%d partial_cancels=0..2" %
          (events, 2*events, 2*events+2))
    print("EXPECTED QUEUE GATES: commands=2 dac_mutes=1 line_mutes=1 restores=0 gates=0")
    print("EXPECTED ACCOMP: run_masks=[57,57,15] applied=0 / SIX I2C jobs=7 writes=24 / lease_expirations=2")
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: DAC/LINE muted lease cancellation,quiet readback,explicit STOP/PLAY recovery and unchanged score")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C lease while queued output muted HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
