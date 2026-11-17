# SPDX-License-Identifier: MIT
"""PC-only waveform contract oracle; not an RP2350 GPIO driver."""
from math import ceil


def encode_byte(value, gpios):
    if len(gpios) != 8 or len(set(gpios)) != 8 or not 0 <= value <= 255:
        raise ValueError('invalid_data_mapping')
    mask = sum(1 << pin for pin in gpios)
    levels = sum(((value >> bit) & 1) << pin for bit, pin in enumerate(gpios))
    return mask & 0xffffffff, levels & 0xffffffff, mask >> 32, levels >> 32


def sn_minimum_us(clock_hz, guard_us=2):
    if clock_hz <= 0:
        raise ValueError('clock_missing')
    return ceil(32 * 1000000 / clock_hz) + guard_us


def sn_write_complete(clock_hz, elapsed_us, ready, deadline_us=100):
    if elapsed_us > deadline_us:
        raise ValueError('ready_timeout')
    return elapsed_us >= sn_minimum_us(clock_hz) and ready


def validate_ay_trace(samples, limits):
    """Check setup/hold, write pulse upper/lower bounds, and no read in a write-only trace.

    Samples are full snapshots: (ns, data byte, BDIR, BC2, BC1).
    GPIO-bank updates may be split in inactive intervals; every active sample must be stable.
    """
    if not samples:
        raise ValueError('empty_trace')
    previous = None
    data_changed_at = samples[0][0]
    active = None
    active_since = 0
    hold_until = 0
    completed = []
    for now, data, bdir, bc2, bc1 in samples:
        if previous is not None and now <= previous[0]:
            raise ValueError('nonmonotonic_time')
        if not 0 <= data <= 255:
            raise ValueError('invalid_byte')
        if bc1 != 0:
            raise ValueError('write_only_BC1_must_stay_low')
        phase = ('write' if bc2 else 'address') if bdir else None
        if previous is not None and data != previous[1]:
            if active or phase:
                raise ValueError('data_changed_during_strobe')
            if now < hold_until:
                raise ValueError('hold_time')
            data_changed_at = now
        if active and phase == active and previous is not None:
            if (bdir, bc2, bc1) != previous[2:]:
                raise ValueError('control_changed_during_strobe')
        if active and phase != active:
            if phase:
                raise ValueError('control_changed_during_strobe')
            width = now - active_since
            if active == 'write':
                if width < limits['write_pulse_min']:
                    raise ValueError('write_pulse_short')
                if width > limits['write_pulse_max']:
                    raise ValueError('write_pulse_long')
            required_hold = limits['write_hold_min'] if active == 'write' else limits['address_hold_min']
            hold_until = now + required_hold
            completed.append(active)
            active = None
        if phase and active is None:
            if previous is not None and bc2 != previous[3]:
                raise ValueError('BC2_changed_at_strobe_edge')
            setup = limits['write_setup_min'] if phase == 'write' else limits['address_setup_min']
            if now - data_changed_at < setup:
                raise ValueError('setup_time')
            active, active_since = phase, now
        previous = (now, data, bdir, bc2, bc1)
    if active:
        raise ValueError('unfinished_strobe')
    if samples[-1][0] < hold_until:
        raise ValueError('hold_time')
    return completed


def validate_read_turnaround(samples):
    """Check a hypothetical CS-controlled/OE, RD-controlled/DIR transceiver.

    This proves only the stated mutual-drive/order conditions, not chip timings.
    Samples: (ns, CS_N, RD_N, WR_N, base_driving).
    """
    previous = None
    for now, cs_n, rd_n, wr_n, base_driving in samples:
        if previous is not None:
            if now <= previous[0]:
                raise ValueError('nonmonotonic_time')
            if rd_n != previous[2] and (not previous[1] or not cs_n):
                raise ValueError('DIR_changed_while_enabled')
        if not cs_n and not rd_n:
            if base_driving:
                raise ValueError('read_bus_contention')
            if not wr_n:
                raise ValueError('read_and_write_together')
        if not cs_n and not wr_n and not base_driving:
            raise ValueError('write_without_data_drive')
        previous = (now, cs_n, rd_n, wr_n, base_driving)
