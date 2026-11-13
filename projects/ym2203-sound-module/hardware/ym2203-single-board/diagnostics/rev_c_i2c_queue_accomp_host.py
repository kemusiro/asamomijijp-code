# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Queued FM/SSG melody with held opposite-family triad and lease cleanup."""
import time
import rev_c_i2c_queue_host as queue

mixer = queue.mixer
SIGNATURE = b"RCQAC01!"


def wait_run(i2c, remote, voice, wanted_mask):
    started = time.ticks_ms()
    keeps = previous = mask_checks = 0
    time.sleep_ms(40)
    if mixer.read_at(i2c, 0x28, 1) != bytes((wanted_mask,)):
        raise RuntimeError("Accompaniment planned mask mismatch")
    while time.ticks_diff(time.ticks_ms(), started) < 8000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        state, progress = status[0], status[1]
        if not 1 <= state <= queue.DONE or not previous <= progress <= 9:
            raise RuntimeError("Accompanied queue progress mismatch: %r" % status)
        previous = progress
        if state == 2 and progress < 9:
            time.sleep_ms(40)
            if mixer.read_at(i2c, 0x14, 1) != bytes((wanted_mask,)):
                raise RuntimeError("Held accompaniment voice mask changed")
            mask_checks += 1
        if state == queue.DONE:
            if mask_checks < 2:
                raise RuntimeError("Accompaniment mask coverage incomplete")
            queue.verify(i2c, remote, queue.DONE, 9, voice)
            print("PASS: accompanied %s melody; KEEP=%d held_mask=%d checks=%d" %
                  ("FM" if voice == 0 else "SSG", keeps, wanted_mask, mask_checks))
            return keeps
    raise RuntimeError("Accompanied queue completion timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    print("Queued melody plus held chord. Both volumes low. Sound starts after5 seconds and upload.")
    time.sleep_ms(5000)
    keeps = 0
    for command, voice, mask in ((queue.PLAY_FM, 0, 57), (queue.PLAY_SSG, 3, 15)):
        queue.upload(i2c, remote)
        print("ACCOMP PLAY / %s / C D E F G F E D C" %
              ("FM melody + SSG low chord" if voice == 0 else "SSG melody + FM high chord"))
        remote.command(command, None)
        keeps += wait_run(i2c, remote, voice, mask)
        remote.command(mixer.STOP, 0)
        queue.verify(i2c, remote, queue.DONE, 9, voice)
        time.sleep_ms(1000)
    print("ACCOMP LEASE / SSG melody + FM chord without KEEP; all voices should mute after about1 second")
    remote.command(queue.PLAY_SSG, None)
    time.sleep_ms(1800)
    status = mixer.read_at(i2c, 0x1D, 2)
    if status[0] != queue.ABORTED or not 1 <= status[1] < 9:
        raise RuntimeError("Accompanied lease cancellation mismatch: %r" % status)
    progress = status[1]
    queue.verify(i2c, remote, queue.ABORTED, progress, 3, expired=1)
    time.sleep_ms(700)
    queue.verify(i2c, remote, queue.ABORTED, progress, 3, expired=1)
    print("PASS: melody and all three companions lease-muted and stayed stopped")
    remote.command(mixer.STOP, 0)
    final = (remote.ack + 1) & 255
    if final != (69 + keeps) & 255:
        raise RuntimeError("Accompanied queue ACK accounting mismatch")
    print("EXPECTED QUEUE: runs=3 completed=2 aborted=1 events=%d pitch_writes=%d" % (18+progress, 2*(18+progress)))
    print("EXPECTED ACCOMP: run_masks=[57,15,15] applied=0 / SIX I2C jobs=6 writes=24")
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: queued FM/SSG melodies with held chords,voice mask integrity,normal end and lease cleanup")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C accompanied queue HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
