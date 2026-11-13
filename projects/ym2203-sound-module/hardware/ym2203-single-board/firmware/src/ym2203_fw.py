# SPDX-License-Identifier: MIT
"""Rev C protocol v1 and cooperative register scheduler;no hardware on import."""
from array import array
import time

VERSION = "0.2.0-alpha.1"
MAGIC = b"YM22F001"
PING, STOP, KEEP, WRITE, PUSH, PLAY, GATES, SEAL = range(8)
OK, CRC_ERROR, INVALID, BUSY, FULL, LEASE_ERROR, SEQUENCE, LATE, IO_ERROR, FAULT, PENDING = range(11)
READY, ACTIVE, DAC_ON, LINE_ON, WORKING, EXPIRED, FAILED, SEALED = (1,2,4,8,16,32,64,128)
IDLE, WRITING, PRIMING, STOPPING, DRAINING = range(5)
CAPACITY, LEASE_MS, LATE_MS, IO_MS, PRIME_BLOCKS = 128, 1000, 100, 100, 12
OFF_REG = (0x28,0x28,0x28,8,9,10)
OFF_VAL = (0,1,2,0,0,0)


def crc16(data, length=14):
    crc = 0
    i = 0
    while i < length:
        crc ^= data[i] << 8
        bit = 0
        while bit < 8:
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 65535
            bit += 1
        i += 1
    return crc


def valid_register(reg, value):
    if not 0 <= value <= 255: return False
    if 0 <= reg <= 13:
        if reg in (1,3,5,13): return value <= 15
        if reg == 6: return value <= 31
        if reg == 7: return value <= 63  # no GPIO-port direction changes
        if 8 <= reg <= 10: return value <= 31
        return True
    if reg == 0x28: return not value & 12 and value & 3 != 3
    if reg in (0x24,0x26): return True
    if reg == 0x25: return value <= 3
    if reg == 0x27: return value <= 63  # CSM/three-slot mode is outside v0.1
    if 0x30 <= reg <= 0x9E and reg & 3 != 3:
        group = reg >> 4
        mask = 127 if group <= 4 else 223 if group == 5 else 159 if group == 6 else 31 if group == 7 else 255 if group == 8 else 15
        return value & ~mask == 0
    if 0xA0 <= reg <= 0xA2: return True
    if 0xA4 <= reg <= 0xA6 or 0xB0 <= reg <= 0xB2: return value <= 63
    # Prescaler/test/SSG GPIO ports/reserved registers are never written.
    return False


class RegisterQueue:
    def __init__(self):
        self.delays = array("H", (0 for unused in range(CAPACITY)))
        self.regs = bytearray(CAPACITY)
        self.values = bytearray(CAPACITY)
        self.head = self.tail = self.count = 0

    def clear(self):
        self.head = self.tail = self.count = 0

    def push(self, delay, reg, value):
        self.delays[self.tail] = delay
        self.regs[self.tail] = reg
        self.values[self.tail] = value
        self.tail = (self.tail + 1) & (CAPACITY - 1)
        self.count += 1

    def pop(self):
        self.head = (self.head + 1) & (CAPACITY - 1)
        self.count -= 1


class Engine:
    def __init__(self, board, clock=None):
        self.board = board
        self.clock = time if clock is None else clock
        self.queue = RegisterQueue()
        self.status = bytearray(4)
        self.last_frame = bytearray(16)
        self.cached = False
        self.external_busy = self.midi_online = False
        self.midi_mask = 0
        self.wrote = False
        self.seq = 0
        self.result = OK
        self.cached_result = OK
        self.active = self.running = self.sealed = self.expired = self.failed = False
        self.gates = self.job = self.job_seq = self.cursor = self.prime = 0
        self.writes = bytearray(10)
        self.write_length = 0
        self.last_keep = self.last_due = self.due = self.drain_at = 0
        self.due_valid = False
        self.io_kind = self.io_reg = self.io_value = 0
        self.io_since = -1
        self.executed = self.expirations = self.max_late = 0
        self.publish()

    def publish(self):
        flags = READY
        if self.active: flags |= ACTIVE
        if self.gates & 1: flags |= DAC_ON
        if self.gates & 2: flags |= LINE_ON
        if self.job or self.io_kind or self.external_busy: flags |= WORKING
        if self.expired: flags |= EXPIRED
        if self.failed: flags |= FAILED
        if self.sealed: flags |= SEALED
        self.status[0] = self.seq
        self.status[1] = self.result
        self.status[2] = flags
        self.status[3] = self.queue.count

    def set_gates(self, gates):
        if not gates & 2: self.board.line_allow.value(0)
        self.board.dac_allow.value(1 if gates & 1 else 0)
        self.board.line_allow.value(1 if gates & 2 else 0)
        self.gates = gates

    def begin_stop(self, expired=False, failed=False):
        self.set_gates(0)
        self.board.cancel_write()
        self.queue.clear()
        self.active = self.running = self.sealed = self.due_valid = False
        self.io_kind = 0
        self.io_since = -1
        self.job = STOPPING
        self.cursor = 0
        self.prime = 0
        if expired:
            self.expired = True
            self.expirations = (self.expirations + 1) & 65535
        if failed: self.failed = True

    def complete_job(self):
        if self.seq == self.job_seq and self.cached_result == PENDING:
            self.result = self.cached_result = OK
        self.job = IDLE

    def fault(self, result):
        self.begin_stop(failed=True)
        self.result = result
        self.cached_result = result

    def check_lease(self, now):
        if self.active and self.clock.ticks_diff(now,self.last_keep) >= LEASE_MS:
            self.begin_stop(expired=True)
            self.result = self.cached_result = LEASE_ERROR

    def accept(self, frame):
        self.check_lease(self.clock.ticks_ms())
        if len(frame) != 16 or crc16(frame) != frame[14] | frame[15] << 8:
            self.result = CRC_ERROR
            self.publish()
            return
        # Exact duplicate requests are idempotent,including after a lost reply.
        if self.cached and frame[1] == self.seq:
            i = 0
            while i < 16 and frame[i] == self.last_frame[i]: i += 1
            if i == 16:
                self.result = self.cached_result
                self.publish()
                return
            self.result = SEQUENCE
            self.publish()
            return
        if frame[1] != (self.seq + 1) & 255:
            self.result = SEQUENCE
            self.publish()
            return
        self.seq = frame[1]
        i = 0
        while i < 16:
            self.last_frame[i] = frame[i]
            i += 1
        self.cached = True
        op = frame[2]
        length = frame[3]
        self.result = INVALID
        self.cached_result = INVALID
        if frame[0] != 1 or length > 10:
            self.publish()
            return
        i = 4 + length
        while i < 14:
            if frame[i]:
                self.publish()
                return
            i += 1
        now = self.clock.ticks_ms()
        if op == STOP and length == 0:
            self.begin_stop()
            self.expired = self.failed = False
            self.job_seq = self.seq
            self.result = PENDING
        elif op == PING and length == 0:
            self.result = OK
        elif self.expired or self.failed:
            self.result = LEASE_ERROR if self.expired else FAULT
        elif self.external_busy:
            self.result = BUSY
        elif op == KEEP and length == 0:
            if self.active: self.last_keep = now
            self.result = OK
        elif self.job:
            self.result = BUSY
        elif op == WRITE and 2 <= length <= 10 and length & 1 == 0:
            i = 4
            while i < 4 + length:
                if not valid_register(frame[i], frame[i+1]): break
                i += 2
            if i == 4 + length:
                i = 0
                while i < length:
                    self.writes[i] = frame[4+i]
                    i += 1
                self.write_length = length
                self.cursor = 0
                self.job = WRITING
                self.job_seq = self.seq
                self.result = PENDING
                if self.active: self.last_keep = now
        elif op == PUSH and (length == 4 or length == 8):
            if self.sealed:
                self.result = INVALID
            elif self.queue.count + length // 4 > CAPACITY:
                self.result = FULL
            else:
                i = 4
                while i < 4 + length:
                    if not valid_register(frame[i+2], frame[i+3]): break
                    i += 4
                if i == 4 + length:
                    i = 4
                    while i < 4 + length:
                        self.queue.push(frame[i] | frame[i+1] << 8,frame[i+2],frame[i+3])
                        i += 4
                    self.result = OK
                    if self.active: self.last_keep = now
        elif op == SEAL and length == 0:
            self.sealed = True
            self.result = OK
            if self.active: self.last_keep = now
        elif op == PLAY and length == 0 and self.queue.count and not self.active:
            self.active = True
            self.job = PRIMING
            self.job_seq = self.seq
            self.prime = PRIME_BLOCKS
            self.last_keep = now
            self.result = PENDING
        elif op == GATES and length == 1 and frame[4] <= 3:
            self.set_gates(frame[4])
            self.active = True
            self.last_keep = now
            self.result = OK
        self.cached_result = self.result
        self.publish()

    def poll(self, bus_idle=True):
        self.wrote = False
        now = self.clock.ticks_ms()
        self.check_lease(now)
        if self.job == PRIMING:
            if self.prime: self.prime -= 1
            elif bus_idle:
                self.set_gates(3)
                self.running = True
                self.last_due = now
                self.last_keep = now
                self.due_valid = False
                self.complete_job()
        if self.job == DRAINING:
            if self.clock.ticks_diff(now,self.drain_at) >= 135:
                self.set_gates(0)
                self.active = False
                self.complete_job()
        # External I2C and the parallel YM bus use different peripherals/pins.
        # Drain committed work even while I2C is active: blocking on every read
        # or refill can starve simultaneous events past LATE_MS. Request-frame
        # acceptance and PLAY's initial handoff still wait for I2C idle. The
        # audio budget remains at most one nonblocking YM write per poll.
        if not self.io_kind:
            if self.job == STOPPING:
                self.io_kind = 1
                self.io_reg = OFF_REG[self.cursor]
                self.io_value = OFF_VAL[self.cursor]
            elif self.running and self.queue.count:
                head = self.queue.head
                if not self.due_valid:
                    self.due = self.clock.ticks_add(self.last_due,self.queue.delays[head])
                    self.due_valid = True
                late = self.clock.ticks_diff(now,self.due)
                if late > LATE_MS:
                    self.fault(LATE)
                elif late >= 0:
                    self.io_kind = 2
                    self.io_reg = self.queue.regs[head]
                    self.io_value = self.queue.values[head]
            if not self.io_kind and self.job == WRITING:
                self.io_kind = 3
                self.io_reg = self.writes[self.cursor]
                self.io_value = self.writes[self.cursor+1]
        if self.io_kind:
            if not self.board.write_register(self.io_reg,self.io_value):
                if self.io_since < 0: self.io_since = now
                elif self.clock.ticks_diff(now,self.io_since) >= IO_MS: self.fault(IO_ERROR)
            else:
                self.wrote = True
                kind = self.io_kind
                self.io_kind = 0
                self.io_since = -1
                if kind == 1:
                    self.cursor += 1
                    if self.cursor == 6: self.complete_job()
                elif kind == 2:
                    late = self.clock.ticks_diff(self.clock.ticks_ms(),self.due)
                    if late > LATE_MS: self.fault(LATE)
                    else:
                        if late > self.max_late: self.max_late = late
                        self.last_due = self.due
                        self.due_valid = False
                        self.queue.pop()
                        self.executed = (self.executed + 1) & 65535
                else:
                    self.cursor += 2
                    if self.cursor == self.write_length: self.complete_job()
        if self.running and self.sealed and not self.queue.count and not self.io_kind:
            # Stop all voices one register per poll,then drain the FM/I2S tail.
            self.running = False
            self.job = STOPPING
            self.cursor = 0
            self.job_seq = -1
            self.prime = -1  # normal-end drain marker;outputs remain enabled
        if self.job == IDLE and self.prime == -1:
            self.prime = 0
            self.job = DRAINING
            self.drain_at = now
        self.publish()


class Window:
    def __init__(self, engine):
        self.engine = engine
        self.data = bytearray(256)
        self.data[:8] = MAGIC
        self.data[8:16] = bytes((1,1,0,31,CAPACITY,10,16,48))
        self.reply = bytearray(4)
        self.frame = bytearray(16)
        self.pointer = self.mask = 0
        self.pending = self.bad_frame = False
        self.finish_pending = self.finished = False

    def receive(self, value, first=0):
        if first:
            self.pointer = value
            if value == 0x10:
                i = 0
                while i < 4:
                    self.reply[i] = self.engine.status[i]
                    i += 1
            elif value == 0x40 and not self.pending:
                self.mask = 0
            return
        if 0x40 <= self.pointer <= 0x4F and not self.pending:
            index = self.pointer-0x40
            self.frame[index] = value
            self.mask |= 1 << index
        elif self.pointer == 0x50:
            if value == 0xA5 and self.mask == 65535 and not self.pending:
                self.pending = True
            else: self.bad_frame = True
        self.pointer = (self.pointer+1) & 255

    def next_byte(self):
        if self.pointer==0x14:value = int(self.engine.external_busy)
        elif self.pointer==0x15:value = self.engine.midi_mask
        elif self.pointer==0x16:value = int(self.engine.midi_online)
        else:value = self.reply[self.pointer-0x10] if 0x10 <= self.pointer <= 0x13 else self.data[self.pointer]
        self.pointer = (self.pointer+1) & 255
        return value

