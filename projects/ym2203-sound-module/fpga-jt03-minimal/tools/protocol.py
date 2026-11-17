# SPDX-License-Identifier: MIT
"""Pure packet helpers; no board pins, transport retries or hardware writes."""
READ, ENQUEUE, START, KEEP, STOP, SEAL, BEGIN = 0, 1, 2, 3, 4, 5, 16


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (7 if crc & 128 else 0)) & 255
    return crc


def packet(op, reg=0, value=0, time_us=0):
    if not (0 <= op <= 255 and 0 <= reg <= 255 and 0 <= value <= 255 and 0 <= time_us <= 0xffffffff):
        raise ValueError('Packet field out of range')
    payload = bytes((op, reg, value, (time_us >> 24) & 255, (time_us >> 16) & 255,
                     (time_us >> 8) & 255, time_us & 255))
    return payload + bytes((crc8(payload),))


def parse_status(data):
    if len(data) != 8 or data[:2] != b'J\x01' or crc8(data[:7]) != data[7]:
        raise ValueError('Invalid status shape/signature/CRC')
    return {'ready': bool(data[2] & 1), 'running': bool(data[2] & 2),
            'fault': bool(data[2] & 4), 'audio_primed': bool(data[2] & 8),
            'sealed': bool(data[2] & 16), 'error': data[3],
            'free_slots': (data[4] << 8) | data[5], 'ack': data[6]}
