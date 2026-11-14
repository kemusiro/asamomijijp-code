# SPDX-License-Identifier: MIT
"""Bounded WYM1 catalogue and playlists for the controller Pico.

Playback uses the unchanged RevCStream.play_file(). No stdin or progress
printing while a track is audible. Ctrl+C cancels through its STOP cleanup.
"""
import os
import struct
import time
from ym2203_revc_stream import MAX_EVENTS

MAX_TRACKS = 64
GAP_MS = 1000


def scan_tracks(directory='/music'):
    """Read headers/lengths only; play_file checks the complete file at playback."""
    tracks, rejected = [], []
    candidates = 0
    for entry in os.ilistdir(directory):
        name, kind = entry[:2]
        if name.startswith('.') or not name.lower().endswith('.bin'):
            continue
        if kind & 0xf000 not in (0, 0x8000):
            continue
        candidates += 1
        if candidates > MAX_TRACKS:
            raise ValueError('At most64 BIN files are supported; reduce /music entries')
        path = directory.rstrip('/') + '/' + name
        try:
            with open(path, 'rb') as source:
                header = source.read(16)
            if len(header) != 16 or header[:4] != b'WYM1':
                raise ValueError('Expected WYM1 header')
            count, period, clock = struct.unpack_from('<III', header, 4)
            if not 0 < count <= MAX_EVENTS or not period or clock != 4000000:
                raise ValueError('Unsupported count,period or clock')
            if os.stat(path)[6] != 16 + count * 6:
                raise ValueError('BIN length/count mismatch')
            tracks.append({'path': path, 'name': name, 'events': count, 'period_ms': period})
        except (OSError, ValueError) as error:
            rejected.append((name, str(error)))
    tracks.sort(key=lambda item: item['name'])
    rejected.sort()
    return tracks, rejected


def parse_selection(text, tracks):
    """Return selected tracks and repeat flag, or raise before touching I2C."""
    words = text.strip().lower().split()
    if words == ['a']:
        selected, repeat = tracks, False
    elif words == ['l']:
        selected, repeat = tracks, True
    else:
        repeat = len(words) == 2 and words[0] == 'r'
        value = words[1] if repeat else words[0] if len(words) == 1 else ''
        if not value or not all('0' <= ch <= '9' for ch in value) or len(value) > 3:
            raise ValueError('Use number,r number,a,l,u or q')
        index = int(value) - 1
        if not 0 <= index < len(tracks):
            raise ValueError('Track number is outside the list')
        selected = [tracks[index]]
    if not selected:
        raise ValueError('No playable WYM1 BIN files; use u after uploading')
    return selected, repeat


def run_playlist(stream, tracks, repeat=False, gap_ms=GAP_MS, write=print):
    """Play in order; fail closed on any error, never skip a failed track.

    A repeat is explicitly requested by the user and ends with Ctrl+C.
    Memory stays bounded; completed results are not retained across cycles.
    """
    if not tracks or len(tracks) > MAX_TRACKS or not 0 <= gap_ms <= 60000:
        raise ValueError('Invalid playlist or gap')
    completed = cycles = 0
    try:
        while True:
            for index, track in enumerate(tracks):
                write('PLAY / cycle%d track%d/%d / %s / Ctrl+C stops to menu' %
                      (cycles + 1, index + 1, len(tracks), track['name']))
                result = stream.play_file(track['path'])
                completed += 1
                # play_file has returned after CRC-checked DONE and output mute.
                write('DONE / %s / events=%d/%d period=%dms CRC32=%08x' %
                      (track['name'], result['executed'], result['total'],
                       result['period_ms'], result['crc32']))
                if repeat or index + 1 < len(tracks):
                    time.sleep_ms(gap_ms)
            cycles += 1
            if not repeat:
                break
    except BaseException:
        try:
            stream.stop()
        except Exception:
            pass  # Preserve the original error; target1s lease is fallback.
        raise
    stream.stop()
    return {'completed': completed, 'cycles': cycles}


def run_console(stream, directory='/music', read_line=None, write=print):
    """Number menu. Attaching/browsing/exiting the menu never sends STOP/PLAY."""
    if read_line is None:
        read_line = input
    tracks = []
    refresh = True
    while True:
        if refresh:
            try:
                tracks, rejected = scan_tracks(directory)
            except (OSError, ValueError) as error:
                tracks, rejected = [], []
                write('CATALOG ERROR: %s' % error)
            for name, error in rejected:
                write('SKIP / %s / %s' % (name, error))
            refresh = False
        write('TRACKS / %s / alphabetical order' % directory)
        for index, track in enumerate(tracks):
            seconds = track['period_ms'] // 1000
            write('%d: %s / %d:%02d / %d events' %
                  (index + 1, track['name'], seconds // 60, seconds % 60, track['events']))
        write('number=once | r number=repeat one | a=all once | l=loop all | u=rescan | q=quit')
        try:
            text = read_line('HOST> ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if text == 'q':
            return
        if text == 'u':
            refresh = True
            continue
        try:
            selected, repeat = parse_selection(text, tracks)
        except ValueError as error:
            write('INPUT: %s' % error)
            continue
        try:
            summary = run_playlist(stream, selected, repeat=repeat, write=write)
        except KeyboardInterrupt:
            write('STOP / requested; menu ready. If STOP transport failed, lease mutes within1s.')
        else:
            write('PLAYLIST DONE / tracks=%d cycles=%d / muted' %
                  (summary['completed'], summary['cycles']))
