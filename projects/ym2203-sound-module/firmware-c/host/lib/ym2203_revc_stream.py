# SPDX-License-Identifier: MIT
"""Rev C C firmware I2C v2. Uses hardware I2C;one outstanding command only."""
import binascii
import struct
import time

SIGNATURE = b'YM22S002'
ADDRESS = 0x42
MAX_EVENTS = 131071
CAPACITY = 1024
BATCH = 32
LEASE_MS = 1000

class ProtocolError(Exception):
    pass

def _file_complete(s, total, period, crc):
    # DONE must describe this sealed file, with healthy audio and no owned queue.
    return (s['state'] == 3 and not s['error'] and s['flags'] & 0x3f == 0x0b
            and s['received'] == total and s['executed'] == total and s['total'] == total
            and s['period_ms'] == period and s['elapsed_ms'] >= period
            and not s['queued'] and s['crc32'] == crc)

class RevCStream:
    def __init__(self, i2c, address=ADDRESS):
        self.i2c = i2c
        self.address = address
        self.commands = 0
        self.status_reads = 0
        self.retries = 0
        self.last = self.status()
        self.seq = self.last['next_seq']

    def status(self):
        for attempt in range(3):
            data = self.i2c.readfrom(self.address, 64)
            self.status_reads += 1
            if len(data) == 64 and data[:8] == SIGNATURE and data[8] == 2:
                crc = binascii.crc32(data[:60]) & 0xffffffff
                if crc == struct.unpack_from('<I', data, 60)[0]:
                    values = struct.unpack_from('<6I2H', data, 12)
                    # ack,next,received,executed,total,period,queued,free
                    return {
                        'state': data[9], 'result': data[10], 'flags': data[11],
                        'ack': values[0], 'next_seq': values[1], 'received': values[2],
                        'executed': values[3], 'total': values[4], 'period_ms': values[5],
                        'queued': values[6], 'free': values[7],
                        'elapsed_ms': struct.unpack_from('<I', data, 40)[0],
                        'error': struct.unpack_from('<H', data, 44)[0],
                        'min_queue': struct.unpack_from('<H', data, 46)[0],
                        'max_late_us': struct.unpack_from('<I', data, 48)[0],
                        'crc32': struct.unpack_from('<I', data, 52)[0],
                    }
            elif data[:8] != SIGNATURE:
                raise ProtocolError('Expected C I2C v2 YM22S002;old firmware/driver is incompatible')
            time.sleep_ms(2)
        raise ProtocolError('Invalid I2C status length/version/CRC')

    def command(self, opcode, payload=b''):
        return self._command(opcode, payload)

    def _command(self, opcode, payload=b'', completed=None):
        seq = self.seq
        packet = bytearray(16 + len(payload))
        struct.pack_into('<2sBBIH2x', packet, 0, b'Y2', 2, opcode, seq, len(payload))
        packet[12:12 + len(payload)] = payload
        struct.pack_into('<I', packet, len(packet) - 4, binascii.crc32(packet[:-4]) & 0xffffffff)
        # Retry only the IDENTICAL packet;the target never reapplies a duplicate.
        # Two500ms response windows fit typical ACK loss;lease still governs safety.
        for attempt in range(2):
            if self.i2c.writeto(self.address, packet) != len(packet):
                raise ProtocolError('Short I2C write')
            self.commands += 1
            deadline = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), deadline) < 500:
                time.sleep_ms(2)
                s = self.status()
                if s['ack'] == seq:
                    if s['result']:
                        # A RUNNING status may become DONE before the final KEEP
                        # reaches the target. Only play_file's verified, sealed
                        # session may accept this STATE rejection as completion.
                        # A rejected command does not consume seq; do not advance it.
                        if (opcode == 5 and not payload and completed is not None
                                and s['result'] == 4 and s['next_seq'] == seq
                                and _file_complete(s, *completed)):
                            self.last = s
                            return s
                        name = ('PING', 'STOP', 'BEGIN', 'PUSH', 'PLAY', 'KEEP', 'SEAL')[opcode] if 0 <= opcode <= 6 else str(opcode)
                        raise ProtocolError('%s rejected:code%d state%d error%d audio_ok=%d;save Rev C STATUS/AUDIO log' %
                                            (name, s['result'], s['state'], s['error'], bool(s['flags'] & 2)))
                    if s['next_seq'] == ((seq + 1) & 0xffffffff):
                        self.seq = s['next_seq']
                        self.last = s
                        return s
                if s['state'] == 5:
                    raise ProtocolError('Target stopped:error%d' % s['error'])
            self.retries += 1
        raise ProtocolError('I2C acknowledgement timeout;target lease will mute')

    def stop(self):
        self.seq = self.status()['next_seq']
        return self.command(1)

    def play_file(self, path):
        """Two bounded file passes. Target checks every event and final file CRC."""
        with open(path, 'rb') as f:
            header = f.read(16)
            if len(header) != 16 or header[:4] != b'WYM1':
                raise ValueError('Expected WYM1 BIN')
            total, period, clock = struct.unpack_from('<III', header, 4)
            if not 0 < total <= MAX_EVENTS or not period or clock != 4000000:
                raise ValueError('Unsupported count,period or clock')
            crc = binascii.crc32(header)
            size = 16
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                crc = binascii.crc32(chunk, crc)
                size += len(chunk)
            if size != 16 + 6 * total:
                raise ValueError('BIN length/count mismatch')
        crc &= 0xffffffff
        self.stop()
        active = False
        try:
            s = self.command(2, header + struct.pack('<I', crc))
            active = True
            sent = 0
            with open(path, 'rb') as f:
                if f.read(16) != header:
                    raise ProtocolError('BIN changed after validation')
                prefill = min(768, total)
                while sent < prefill:
                    n = min(BATCH, prefill - sent)
                    block = f.read(n * 6)
                    if len(block) != n * 6:
                        raise ProtocolError('Truncated BIN')
                    s = self.command(3, block)
                    sent += n
                s = self.command(4)
                last_keep = time.ticks_ms()
                sealed = False
                while True:
                    if s['state'] == 5:
                        raise ProtocolError('Target stopped:error%d' % s['error'])
                    if s['state'] == 3:
                        if not sealed or not _file_complete(s, total, period, crc):
                            raise ProtocolError('Incomplete final state')
                        active = False
                        return s
                    if sent < total and s['free'] >= min(BATCH, total - sent):
                        n = min(BATCH, total - sent)
                        block = f.read(n * 6)
                        if len(block) != n * 6:
                            raise ProtocolError('Truncated BIN')
                        s = self.command(3, block)
                        sent += n
                        last_keep = time.ticks_ms()
                    elif sent == total and not sealed:
                        s = self.command(6)
                        sealed = True
                        last_keep = time.ticks_ms()
                    elif time.ticks_diff(time.ticks_ms(), last_keep) >= 200:
                        s = self._command(5, completed=(total, period, crc) if sealed else None)
                        last_keep = time.ticks_ms()
                    else:
                        time.sleep_ms(10)
                        s = self.status()
        finally:
            if active:
                try:
                    self.stop()
                except Exception:
                    pass  # The target's1s lease remains the fallback.
