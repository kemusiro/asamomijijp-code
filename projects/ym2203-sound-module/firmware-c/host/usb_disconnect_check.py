# SPDX-License-Identifier: MIT
"""OTHER Pico: I2C diagnostic while the user removes Rev C's USB cable.

HOST PASS verifies I2C completion/quiet state only. Physical USB removal and
audible continuity must be confirmed by the user. Keep external 5V on.
"""
import binascii
import time
from ym2203_revc_stream import RevCStream, ProtocolError


def healthy(status):
    if not status['flags'] & 2 or status['error']:
        raise ProtocolError('Target audio/I2C error during USB disconnect check')


def run_check(bind, release, path='/music/recovery.bin'):
    with open(path, 'rb') as source:
        score = source.read(1163)
    if len(score) != 1162 or binascii.crc32(score) & 0xffffffff != 0xe5df0948:
        raise ValueError('Use original 191-event /music/recovery.bin CRC=e5df0948')
    bus = bind()
    player = None
    try:
        player = RevCStream(bus)
        healthy(player.last)
        player.stop()
        print('READY: target STOP; 3 seconds quiet. Keep external5V and HOST USB connected.')
        time.sleep_ms(3000)
        print('PLAY: unplug ONLY Rev C Pico USB within5 seconds; leave it unplugged until DONE.')
        print('Expect full13s FM scale,SSG scale,six-voice chord without gaps. No progress prints.')
        result = player.play_file(path)
        healthy(result)
        if result['received'] != 191 or result['executed'] != 191 or result['crc32'] != 0xe5df0948:
            raise ProtocolError('Incomplete I2C diagnostic after USB removal')
        print('PASS: I2C all191 events,CRC=e5df0948; 4 seconds quiet with read-only checks.')
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 4000:
            s = player.status()
            healthy(s)
            if s['state'] != 3 or s['executed'] != 191 or s['queued']:
                raise ProtocolError('I2C completion/quiet state changed after playback')
            time.sleep_ms(100)
        player.stop()
        s = player.status()
        healthy(s)
        if s['state'] != 4 or s['queued']:
            raise ProtocolError('Final STOP failed')
        print('HOST PASS: I2C diagnostic completion and four-second quiet state verified')
        print('USB removal and uninterrupted sound require your observation;HOST cannot sense the cable.')
        print('DONE: reconnect Rev C USB;wait4 seconds without notes,then verify explicit MIDI restart and panic.')
        return s
    except BaseException:
        if player is not None:
            try:
                player.stop()
            except Exception:
                pass  # The target's1s lease remains the fallback.
        raise
    finally:
        release(bus)


def main():
    from machine import I2C, Pin

    def bind():
        return I2C(0, sda=Pin(0), scl=Pin(1), freq=100000, timeout=100000)

    def release(bus):
        try:
            bus.deinit()
        finally:
            Pin(0, Pin.IN)
            Pin(1, Pin.IN)
        print('HOST SAFE: GP0/GP1 inputs')

    print('Rev C C USB disconnect / I2C continuity HOST v1.1 / OTHER Pico only')
    print('Target C0.5.0-alpha.3; external5V ON; start both volumes low; MIDI stopped.')
    run_check(bind, release)


if __name__ == '__main__':
    main()
