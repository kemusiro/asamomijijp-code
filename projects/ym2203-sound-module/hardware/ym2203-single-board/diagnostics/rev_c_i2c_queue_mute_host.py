# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""A muted queued melody advances and restores at its current note,not C."""
import time
import rev_c_i2c_queue_accomp_host as accomp

queue, mixer = accomp.queue, accomp.mixer
SIGNATURE = b"RCQMT01!"


def check_gates(i2c, wanted):
    time.sleep_ms(40)
    if mixer.read_at(i2c, 0x29, 1) != bytes((wanted,)):
        raise RuntimeError("Queued output gate readback mismatch")


def wait_run(i2c, remote, voice, mask, mute):
    started = time.ticks_ms()
    keeps = previous = stage = muted_at = checks = 0
    time.sleep_ms(40)
    if mixer.read_at(i2c, 0x28, 1) != bytes((mask,)):
        raise RuntimeError("Queued mute planned voice mask mismatch")
    while time.ticks_diff(time.ticks_ms(), started) < 8000:
        time.sleep_ms(queue.KEEP_GAPS[keeps % len(queue.KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        state, progress = status[0], status[1]
        if not 1 <= state <= queue.DONE or not previous <= progress <= 9:
            raise RuntimeError("Queued mute state/progress mismatch: %r" % status)
        previous = progress
        if state == 2 and progress < 9:
            time.sleep_ms(40)
            if mixer.read_at(i2c, 0x14, 1) != bytes((mask,)):
                raise RuntimeError("Queued mute changed active voice mask")
            check_gates(i2c, (2 if mute == mixer.DAC_MUTE else 1) if stage == 1 else 3)
            checks += 1
            if stage == 0 and progress >= 3:
                print("QUEUE MUTE / %s / progress=%d / score keeps running" %
                      ("DAC: only SSG chord remains" if mute == mixer.DAC_MUTE else "LINE: all voices disappear", progress))
                remote.command(mute, 1)
                check_gates(i2c, 2 if mute == mixer.DAC_MUTE else 1)
                muted_at, stage = progress, 1
            elif stage == 1 and progress >= 6:
                if progress - muted_at < 2:
                    raise RuntimeError("Insufficient queued progress while muted")
                remote.command(mixer.BOTH, 1)
                check_gates(i2c, 3)
                print("QUEUE RESTORE / progressed from%d to%d / hear current note,not a restart" % (muted_at, progress))
                stage = 2
        if state == queue.DONE:
            if stage != 2 or checks < 3:
                raise RuntimeError("Queued mute/restore coverage incomplete")
            queue.verify(i2c, remote, queue.DONE, 9, voice)
            check_gates(i2c, 0)
            print("PASS: queued %s mute/restore and all9 notes; KEEP=%d" % ("FM DAC" if voice == 0 else "SSG LINE", keeps))
            return keeps
    raise RuntimeError("Queued mute completion timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=queue.Remote)
    remote.command(mixer.START, 0)
    for unused in range(8): remote.command(mixer.KEEP, 0)
    print("Queued FM DAC mute,then SSG LINE mute. Both volumes low. Sound starts after5 seconds and upload.")
    time.sleep_ms(5000)
    keeps = 0
    for command, voice, mask, mute in ((queue.PLAY_FM, 0, 57, mixer.DAC_MUTE), (queue.PLAY_SSG, 3, 15, mixer.LINE_MUTE)):
        queue.upload(i2c, remote)
        print("QUEUE PLAY / %s melody + held chord / all9 register events,including muted notes" % ("FM" if voice == 0 else "SSG"))
        remote.command(command, None)
        keeps += wait_run(i2c, remote, voice, mask, mute)
        remote.command(mixer.STOP, 0)
        queue.verify(i2c, remote, queue.DONE, 9, voice)
        time.sleep_ms(1000)
    print("QUEUE LEASE / short SSG melody + FM chord without KEEP; all voices auto-mute")
    remote.command(queue.PLAY_SSG, None)
    time.sleep_ms(1800)
    status = mixer.read_at(i2c, 0x1D, 2)
    if status[0] != queue.ABORTED or not 1 <= status[1] < 9:
        raise RuntimeError("Queued mute final lease mismatch: %r" % status)
    progress = status[1]
    queue.verify(i2c, remote, queue.ABORTED, progress, 3, expired=1)
    check_gates(i2c, 0)
    time.sleep_ms(700)
    queue.verify(i2c, remote, queue.ABORTED, progress, 3, expired=1)
    remote.command(mixer.STOP, 0)
    final = (remote.ack + 1) & 255
    if final != (73 + keeps) & 255:
        raise RuntimeError("Queued mute ACK accounting mismatch")
    print("EXPECTED QUEUE: runs=3 completed=2 aborted=1 events=%d pitch_writes=%d" % (18+progress, 2*(18+progress)))
    print("EXPECTED QUEUE GATES: commands=4 dac_mutes=1 line_mutes=1 restores=2 gates=0")
    print("EXPECTED ACCOMP: run_masks=[57,15,15] applied=0 / SIX I2C jobs=6 writes=24 / lease_expirations=1")
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: autonomous score advances through DAC/LINE mute,restores without replay,and final all-voice lease mute")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    queue.pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C queued gate mute HOST v1 / OTHER Pico only")


if __name__ == "__main__": run()
