# SPDX-License-Identifier: MIT
"""OTHER Pico only. Run while the C MIDI page holds the six-voice chord."""
from machine import I2C, Pin
import time
import binascii
import struct
from ym2203_revc_stream import RevCStream, ProtocolError


def main():
    print('Rev C C MIDI / I2C handover HOST v1 / OTHER Pico only')
    print('First click MIDI page button1 and wait for the held six-voice chord')
    bus = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000, timeout=100000)
    player = None
    success = False
    try:
        with open('/music/recovery.bin', 'rb') as source:
            score = source.read(1163)
        if len(score) != 1162 or binascii.crc32(score) & 0xffffffff != 0xe5df0948:
            raise ValueError('Upload the original 191-event /music/recovery.bin first')
        player = RevCStream(bus)  # Read-only attach, does not stop MIDI.
        try:
            player.command(2, score[:16] + struct.pack('<I', 0xe5df0948))
        except ProtocolError as error:
            if not str(error).startswith('BEGIN rejected:code4 '):
                raise
        else:
            raise ProtocolError('Expected MIDI ownership rejection; start the held chord before RUN')
        print('PASS: BEGIN rejected while MIDI owns the chip; chord must keep sounding')
        time.sleep_ms(2000)
        player.stop()
        print('STOP: MIDI chord muted; 3 seconds quiet, then I2C diagnostic')
        time.sleep_ms(3000)
        print('I2C PLAY: click MIDI page button2 within 5 seconds; hear only the I2C score')
        result = player.play_file('/music/recovery.bin')
        if result['executed'] != 191 or result['crc32'] != 0xe5df0948:
            raise ProtocolError('I2C diagnostic completion mismatch')
        print('PASS: I2C score completed all191 events; no automatic MIDI replay; 3 seconds quiet')
        time.sleep_ms(3000)
        status = player.status()
        if status['state'] != 3 or status['error']:
            raise ProtocolError('Expected I2C DONE after quiet interval')
        success = True
        print('HOST PASS: MIDI BEGIN rejection, global I2C STOP and I2C completion')
        print('DONE: now click MIDI page button3; verify six voices resume only on new Note On, then MIDI panic')
    finally:
        try:
            if player is not None and not success:
                player.stop()
        finally:
            try:
                bus.deinit()
            finally:
                Pin(0, Pin.IN)
                Pin(1, Pin.IN)
            print('HOST SAFE: GP0/GP1 inputs')


if __name__ == '__main__':
    main()
