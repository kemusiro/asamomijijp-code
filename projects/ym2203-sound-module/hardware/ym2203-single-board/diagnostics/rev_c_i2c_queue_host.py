# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Upload once,then vary KEEP pacing without sending notes during playback."""
import time
import rev_c_i2c_voice_pitch_host as pitch

mixer = pitch.mixer
SIGNATURE = b"RCQUE01!"
APPEND, CLEAR, PLAY_FM, PLAY_SSG = 0xA0, 0xA5, 0xA6, 0xA7
DONE, ABORTED = 4, 5
KEEP_GAPS = (80, 160, 240, 120)


class Remote(pitch.Remote):
    max_opcode = PLAY_SSG

    def command(self, command, wanted=0):
        # The queue changes mode autonomously; PLAY/KEEP may ACK mode0 or1.
        mixer.checked_write(self.i2c, bytes((0x20, command)))
        started = time.ticks_ms()
        while True:
            time.sleep_ms(self.ack_wait_ms)
            data = mixer.read_at(self.i2c, 0x10, 4)
            changed = data[0] != self.ack
            if (data[1] > PLAY_SSG or data[2] not in (0, 1) or data[3] or
                    (changed and (data[0] != (self.ack + 1) & 255 or data[1] != command or
                                  (wanted is not None and data[2] != wanted)))):
                raise RuntimeError("Queue command/status mismatch: %r" % data)
            if changed:
                self.ack, self.last = data[0], command
                return
            if time.ticks_diff(time.ticks_ms(), started) >= 1000:
                raise RuntimeError("Queue command acknowledgement timeout")


def verify(i2c, remote, state, progress, voice, expired=0):
    actual = mixer.read_at(i2c, 0x10, 16)
    pitches = bytearray(pitch.INITIAL)
    if expired and progress:
        pitches[voice] = pitch.MELODY[progress - 1]
    expected = bytes((remote.ack, remote.last, 0, expired, 0, 0)) + bytes(pitches) + bytes((9, state, progress, voice))
    if actual != expected:
        raise RuntimeError("Queue final state mismatch: expected=%r actual=%r" % (expected, actual))


def upload(i2c, remote):
    remote.command(CLEAR, 0)
    for note in pitch.MELODY:
        remote.command(APPEND + note, 0)
    if mixer.read_at(i2c, 0x30, 9) != bytes(pitch.MELODY):
        raise RuntimeError("Uploaded score readback mismatch")
    verify(i2c, remote, 0, 0, 255)
    print("PASS: nine uploaded notes read back; sources remain stopped")


def wait_run(i2c, remote, voice):
    started = time.ticks_ms()
    keeps = previous = 0
    while time.ticks_diff(time.ticks_ms(), started) < 8000:
        time.sleep_ms(KEEP_GAPS[keeps % len(KEEP_GAPS)])
        remote.command(mixer.KEEP, None)
        keeps += 1
        # Keep idle audio opportunities between short reads. Large snapshots
        # are read only after playback ends, never at every note deadline.
        time.sleep_ms(40)
        status = mixer.read_at(i2c, 0x1D, 2)
        state, progress = status[0], status[1]
        if not 1 <= state <= DONE or not previous <= progress <= 9:
            raise RuntimeError("Queue playback state/progress mismatch: %r" % status)
        previous = progress
        if state == DONE:
            verify(i2c, remote, DONE, 9, voice)
            print("PASS: queued %s scale complete; KEEP=%d; no note commands during playback" %
                  ("FM" if voice == 0 else "SSG", keeps))
            return keeps
    raise RuntimeError("Queued playback completion timeout")


def check_live(i2c):
    remote = mixer.shared.preflight(i2c, signature=SIGNATURE, remote_factory=Remote)
    remote.command(mixer.START, 0)
    for unused in range(8):
        remote.command(mixer.KEEP, 0)
    print("FM then SSG: upload nine notes,play at target-clock500ms spacing. Both volumes low.")
    time.sleep_ms(5000)
    keeps = 0
    for command, voice in ((PLAY_FM, 0), (PLAY_SSG, 3)):
        upload(i2c, remote)
        print("QUEUE PLAY / %s ONLY / C D E F G F E D C /500ms per note" % ("FM" if voice == 0 else "SSG"))
        remote.command(command, None)
        keeps += wait_run(i2c, remote, voice)
        remote.command(mixer.STOP, 0)
        verify(i2c, remote, DONE, 9, voice)
        time.sleep_ms(1000)
    print("QUEUE LEASE / SSG again without KEEP; should stop after about1 second and stay stopped")
    remote.command(PLAY_SSG, None)
    time.sleep_ms(1800)
    short = mixer.read_at(i2c, 0x1D, 2)
    if short[0] != ABORTED or not 1 <= short[1] < 9:
        raise RuntimeError("Queued lease cancellation mismatch: %r" % short)
    progress = short[1]
    verify(i2c, remote, ABORTED, progress, 3, expired=1)
    time.sleep_ms(700)
    verify(i2c, remote, ABORTED, progress, 3, expired=1)
    print("PASS: queue lease cancelled after%d notes; no subsequent scheduled notes" % progress)
    remote.command(mixer.STOP, 0)
    # STOP clears the flag but retains the aborted queue for inspection.
    actual = mixer.read_at(i2c, 0x10, 4)
    if actual != bytes((remote.ack, mixer.STOP, 0, 0)):
        raise RuntimeError("Queue STOP did not clear expiry")
    final = (remote.ack + 1) & 255
    if final != (69 + keeps) & 255:
        raise RuntimeError("Queue final ACK accounting mismatch")
    print("EXPECTED QUEUE: runs=3 completed=2 aborted=1 events=%d pitch_writes=%d" % (18 + progress, (18 + progress) * 2))
    print("EXPECTED TARGET FINAL ACK: %d / FINISH=7 mode=0 lease_flag=0" % final)
    mixer.checked_write(i2c, bytes((0x20, mixer.FINISH)))
    print("HOST PASS: uploaded FM/SSG queues,variable KEEP pacing,autonomous completion and lease cancellation")


def check(i2c):
    if getattr(mixer.Remote, "ack_wait_ms", None) != 40:
        raise RuntimeError("Install v1.3 FM HOST helpers and soft reset")
    pitch.six.staged.startup.check(i2c)
    time.sleep_ms(3000)
    check_live(i2c)


def run():
    mixer.shared.run(check_fn=check,
        title="YM2203 Rev C / I2C nine-note queue HOST v1 / OTHER Pico only")


if __name__ == "__main__":
    run()
