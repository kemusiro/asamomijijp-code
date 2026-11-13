# SPDX-License-Identifier: MIT
"""MicroPython I2C host for physical Rev C firmware v0.1/protocol1."""
import time

MAGIC = b"YM22F001"
PING, STOP, KEEP, WRITE, PUSH, PLAY, GATES, SEAL = range(8)
ACTIVE, WORKING, EXPIRED, FAILED = 2,16,32,64
PENDING = 10


class ProtocolError(RuntimeError):
    pass


def crc16(data):
    crc = 0
    for value in data:
        crc ^= value << 8
        for unused in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 65535
    return crc


class YM2203:
    def __init__(self, i2c, address=0x42, clock=None):
        self.i2c, self.address = i2c,address
        self.clock = time if clock is None else clock
        if self._read(0,8) != MAGIC:
            raise ProtocolError("Expected physical Rev C firmware YM22F001")
        self.seq = self.status()[0]
        self.stop()

    def _write(self, data):
        if self.i2c.writeto(self.address,data) != len(data):
            raise OSError("Short I2C write;request was not retried")

    def _read(self, pointer, count):
        self._write(bytes((pointer,)))
        data = self.i2c.readfrom(self.address,count)
        if len(data) != count: raise OSError("Short I2C read")
        return data

    def status(self):
        data = self._read(0x10,4)
        if data[1] > PENDING or not data[2] & 1 or data[3] > 128:
            raise ProtocolError("Malformed firmware status")
        return data

    def _command(self, opcode, payload=b""):
        if len(payload) > 10: raise ValueError("Payload exceeds10 bytes")
        seq = (self.seq+1) & 255
        frame = bytearray(16)
        frame[0:4] = bytes((1,seq,opcode,len(payload)))
        frame[4:4+len(payload)] = payload
        crc = crc16(memoryview(frame)[:14])
        frame[14],frame[15] = crc & 255,crc >> 8
        self._write(b"\x40"+frame)
        self._write(b"\x50\xA5")
        started = self.clock.ticks_ms()
        while self.clock.ticks_diff(self.clock.ticks_ms(),started) < 1500:
            # Preserve the physically verified idle opportunity between polls.
            self.clock.sleep_ms(40)
            status = self.status()
            if status[0] == seq:
                self.seq = seq  # rejected valid frames also consume a sequence
                if status[1] not in (0,PENDING):
                    raise ProtocolError("Firmware rejected request:code%d" % status[1])
                if status[1] == 0 and not status[2] & WORKING: return status
            elif status[1] in (1,6):
                raise ProtocolError("CRC/sequence failure;resync with explicit stop()")
        raise ProtocolError("ACK timeout;request not retried;resync with stop()")

    def stop(self):
        # Re-establish the sequence before explicit STOP after an uncertain ACK.
        self.seq = self.status()[0]
        return self._command(STOP)

    def keepalive(self): return self._command(KEEP)
    def play(self): return self._command(PLAY)
    def seal(self): return self._command(SEAL)

    def gates(self, dac=True, line=True):
        return self._command(GATES,bytes((int(bool(dac)) | int(bool(line)) << 1,)))

    def write_registers(self, registers):
        payload = bytearray()
        for reg,value in registers:
            if type(reg) is not int or type(value) is not int or not 0 <= reg <= 255 or not 0 <= value <= 255:
                raise ValueError("Register/value must be bytes")
            payload.extend((reg,value))
            if len(payload) == 10:
                self._command(WRITE,payload)
                payload = bytearray()
        if payload: self._command(WRITE,payload)

    def enqueue(self, events):
        """Append ordered(delta_ms,register,value) events,two per atomic frame."""
        payload = bytearray()
        for delay,reg,value in events:
            if (type(delay) is not int or not 0 <= delay <= 65535 or
                    type(reg) is not int or not 0 <= reg <= 255 or
                    type(value) is not int or not 0 <= value <= 255):
                raise ValueError("Event requires delta0..65535 and register/value bytes")
            payload.extend((delay & 255,delay >> 8,reg,value))
            if len(payload) == 8:
                self._command(PUSH,payload)
                payload = bytearray()
        if payload: self._command(PUSH,payload)

    def stream(self, events, prefill=32):
        """Consume finite/infinite generators in bounded memory;STOP on exit.

        Prepare timbres first. This method preserves that configuration but
        clears pending events. It does not impose a total song/run time limit.
        """
        if type(prefill) is not int or not 2 <= prefill <= 128:
            raise ValueError("prefill must be2..128 events")
        self.stop()
        iterator = iter(events)
        exhausted = sealed = False
        try:
            batch = []
            for unused in range(prefill):
                try: batch.append(next(iterator))
                except StopIteration:
                    exhausted = True
                    break
            if not batch: return
            self.enqueue(batch)
            if exhausted:
                self.seal()
                sealed = True
            self.play()
            while True:
                status = self.status()
                if status[2] & (EXPIRED | FAILED):
                    raise ProtocolError("Stream stopped by firmware lease/fault")
                if not exhausted and status[3] <= 126:
                    batch = []
                    for unused in range(2):
                        try: batch.append(next(iterator))
                        except StopIteration:
                            exhausted = True
                            break
                    if batch: self.enqueue(batch)
                else: self.keepalive()
                if exhausted and not sealed:
                    self.seal()
                    sealed = True
                if sealed and not status[2] & (ACTIVE | WORKING): return
        finally:
            self.stop()

    def pure_fm(self, channel=0):
        """One audible operator,TL0 with firmware1/8 conversion gain."""
        if type(channel) is not int or not 0 <= channel < 3: raise ValueError("FM channel0..2")
        registers = [(0x28,channel)]
        for slot in (0,4,8,12):
            for base,value in ((0x30,1),(0x40,0 if slot == 0 else 127),(0x50,31),
                               (0x60,0),(0x70,0),(0x80,15),(0x90,0)):
                registers.append((base+slot+channel,value))
        registers.append((0xB0+channel,7))
        self.write_registers(registers)

    def ssg_bass(self):
        registers = [(8,0),(9,0),(10,0)]
        for channel,period in enumerate((478,379,319)):
            registers.extend(((2*channel,period & 255),(2*channel+1,period >> 8)))
        registers.append((7,0x38))
        self.write_registers(registers)
