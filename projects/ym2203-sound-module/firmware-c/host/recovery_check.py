# SPDX-License-Identifier: MIT
"""OTHER Pico only: physical STOP/lease/rebind check for C I2C v2.

Uses the original 13-second diagnostic score, not Ys II. Does not change the
accepted host library or target firmware. Main is deliberately not auto-saved.
"""
import binascii
import struct
import time
from ym2203_revc_stream import RevCStream, ProtocolError

SCORE_PATH = '/music/recovery.bin'
SCORE_EVENTS = 191
SCORE_PERIOD_MS = 13000
SCORE_CRC32 = 0xe5df0948


def require(condition, message):
    if not condition:
        raise ProtocolError('RECOVERY: ' + message)


def load_score(path):
    # Fixed small original score; reject an accidental full-song file before
    # allocating it or issuing BEGIN. No filesystem writes on the Pico.
    with open(path, 'rb') as source:
        data = source.read(16 + 6 * SCORE_EVENTS + 1)
    require(len(data) == 16 + 6 * SCORE_EVENTS, 'wrong diagnostic score length')
    require(data[:16] == struct.pack('<4sIII', b'WYM1', SCORE_EVENTS,
                                    SCORE_PERIOD_MS, 4000000), 'wrong score header')
    require(binascii.crc32(data) & 0xffffffff == SCORE_CRC32, 'wrong score CRC')
    return data


def healthy(status):
    require(status['flags'] & 2, 'target audio is not healthy; save Rev C log')


def begin_score(player, data):
    # Re-upload explicitly: v2 STOP/lease discards the event ring. PLAY alone
    # must never restart it. Full score fits in the existing 1024-event ring.
    player.stop()
    player.command(2, data[:16] + struct.pack('<I', SCORE_CRC32))
    for offset in range(16, len(data), 32 * 6):
        player.command(3, data[offset:offset + 32 * 6])
    player.command(6)
    status = player.command(4)
    healthy(status)
    require(status['state'] == 2 and status['received'] == SCORE_EVENTS,
            'score did not start')


def advance(player, until_ms, complete=False):
    started = time.ticks_ms()
    last_keep = started
    while time.ticks_diff(time.ticks_ms(), started) < SCORE_PERIOD_MS + 3000:
        status = player.status()
        healthy(status)
        if status['state'] == 3:
            require(complete, 'unexpected early completion')
            require(status['received'] == status['executed'] == SCORE_EVENTS
                    and status['total'] == SCORE_EVENTS
                    and status['period_ms'] == SCORE_PERIOD_MS
                    and status['crc32'] == SCORE_CRC32
                    and status['error'] == 0
                    and status['queued'] == 0
                    and status['flags'] & 8
                    and not status['flags'] & (4 | 16 | 32),
                    'invalid completed state')
            return status
        require(status['state'] == 2 and status['error'] == 0,
                'playback stopped before requested position')
        if not complete and status['elapsed_ms'] >= until_ms:
            # At 11s the original score has all FM/SSG voices keyed on; the
            # natural key-off is 12.5s, later than the 1-second lease deadline.
            require(status['elapsed_ms'] < until_ms + 200,
                    'host late at interruption point')
            return status
        if time.ticks_diff(time.ticks_ms(), last_keep) >= 200:
            player.command(5)
            last_keep = time.ticks_ms()
        time.sleep_ms(20)
    raise ProtocolError('RECOVERY: score wait timed out')


def quiet(player, state, error, duration_ms=4000):
    initial = player.status()
    healthy(initial)
    require(initial['state'] == state and initial['error'] == error,
            'wrong STOP/lease state')
    frozen = (initial['received'], initial['executed'], initial['ack'],
              initial['next_seq'], initial['crc32'])
    started = time.ticks_ms()
    while True:
        status = player.status()
        healthy(status)
        require(status['state'] == state and status['error'] == error
                and status['queued'] == 0
                and not status['flags'] & (4 | 16)
                and bool(status['flags'] & 32) == (error == 8),
                'stopped session resumed or retained queued events')
        require((status['received'], status['executed'], status['ack'],
                 status['next_seq'], status['crc32']) == frozen,
                'progress or command sequence changed during quiet readback')
        if time.ticks_diff(time.ticks_ms(), started) >= duration_ms:
            return status
        # Reads intentionally do not renew a lease or send any command.
        time.sleep_ms(100)


def run_check(bind, release, path=SCORE_PATH):
    """bind/release permit native tests; main below uses real hardware I2C0."""
    data = load_score(path)
    bus = None
    player = None
    observations = []
    try:
        bus = bind()
        player = RevCStream(bus)
        player.stop()
        healthy(player.last)
        print('PASS: I2C v2 identified; diagnostic 191 events / 13s / CRC=e5df0948')
        print('Four sections; no progress prints while audio plays. Sound starts in 5 seconds.')
        time.sleep_ms(5000)

        print('1/4 STOP: FM scale, SSG scale, then short six-voice chord; STOP; 4 seconds quiet')
        begin_score(player, data)
        before_stop = advance(player, 11000)
        require(before_stop['executed'] == 185, 'STOP must interrupt the six-voice chord')
        stopped = player.stop()
        require(stopped['state'] == 4 and stopped['error'] == 0,
                'STOP not acknowledged')
        observations.append(quiet(player, 4, 0))
        print('PASS 1/4: STOP cleared queue; progress frozen through 4-second readback')

        print('2/4 REPLAY: explicit BEGIN/upload/PLAY; FM scale, SSG scale, full chord, normal end')
        begin_score(player, data)
        observations.append(advance(player, 0, complete=True))
        print('PASS 2/4: all 191 events completed; CRC correct; no target reset')

        print('3/4 LEASE: same scales and short chord; release HOST pins for 1800ms; rebind; 4 seconds quiet')
        begin_score(player, data)
        before_release = advance(player, 11000)
        require(before_release['executed'] == 185, 'lease must interrupt the six-voice chord')
        # KEEP just before release makes the expected auto-mute about one
        # second after release. No STOP, reads or other traffic while unbound.
        player.command(5)
        release(bus)
        bus = None
        player = None
        time.sleep_ms(1800)
        bus = bind()
        player = RevCStream(bus)
        leased = quiet(player, 5, 8)
        require(before_release['executed'] <= leased['executed'] < SCORE_EVENTS,
                'lease did not interrupt the unfinished score')
        observations.append(leased)
        print('PASS 3/4: LEASE error8, queue empty; reattachment/readback did not restart audio')
        print('EXPECTED Rev C: FAIL I2C error=8 here is the intentional lease stop; audio fault must stay 0')

        print('4/4 RECOVERY: STOP clears lease; BEGIN/upload/PLAY; full FM/SSG scales and chord')
        player.stop()
        quiet(player, 4, 0, 500)
        begin_score(player, data)
        final = advance(player, 0, complete=True)
        observations.append(final)
        print('PASS 4/4: all 191 events completed after rebind; CRC correct')
        player.stop()
        final_stop = quiet(player, 4, 0, 500)
        print('RESULT: sections=4 completed=2 explicit_interruptions=1 lease_interruptions=1')
        print('INTERRUPT: STOP executed=%d LEASE executed=%d/%d' %
              (observations[0]['executed'], leased['executed'], SCORE_EVENTS))
        print('FINAL: state=%d error=%d queued=%d flags=0x%02x audio_ok=1' %
              (final_stop['state'], final_stop['error'], final_stop['queued'], final_stop['flags']))
        print('HOST PASS: STOP, lease mute, read-only reattachment and explicit restart verified')
        print('DONE: target stopped; report both logs and the four audible sections')
        return observations
    finally:
        try:
            if bus is not None:
                try:
                    if player is not None:
                        player.stop()
                finally:
                    release(bus)
        finally:
            print('HOST SAFE: GP0/GP1 inputs; target lease is fallback if STOP failed')


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

    print('Rev C C I2C v2 / STOP-lease-recovery HOST v1 / OTHER Pico only')
    print('C I2C v2; GP0=SDA GP1=SCL GND shared; 100kHz / 3.3V')
    print('Start both volumes low; leave physical cables connected throughout')
    run_check(bind, release)


if __name__ == '__main__':
    main()
