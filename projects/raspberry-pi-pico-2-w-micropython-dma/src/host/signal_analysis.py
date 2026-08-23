"""Pure-Python signal analysis used by acquisition and offline verification."""

from __future__ import annotations

import statistics


PATTERN_BYTES = bytes((0xF0, 0xAA, 0x00, 0xFF))


def bits_lsb_first(data):
    return tuple((byte >> bit) & 1 for byte in data for bit in range(8))


def analyse_pio_samples(samples, output_hz: int, sample_hz: int):
    """Analyse packed DIO0/1 samples captured from the PIO TX experiment."""
    buffer_samples = len(samples)
    bits = tuple(sample & 1 for sample in samples)
    activity_bits = tuple((sample >> 1) & 1 for sample in samples)
    edges = tuple(
        (index, bits[index - 1], bits[index])
        for index in range(1, len(bits))
        if bits[index] != bits[index - 1]
    )
    expected_trigger_index = buffer_samples - 3500
    rising_edges = tuple(edge for edge in edges if edge[1:] == (0, 1))
    if not rising_edges:
        raise ValueError("no rising edge was captured on DIO0")
    trigger_index = min(
        rising_edges,
        key=lambda edge: abs(edge[0] - expected_trigger_index),
    )[0]

    samples_per_bit = sample_hz / output_hz
    pattern_bits = bits_lsb_first(PATTERN_BYTES)
    pattern_start = trigger_index - 4.0 * samples_per_bit
    decoded = []
    bit_number = 0
    while True:
        sample_index = int(round(pattern_start + (bit_number + 0.5) * samples_per_bit))
        if sample_index < 0:
            bit_number += 1
            continue
        if sample_index >= len(bits):
            break
        decoded.append(bits[sample_index])
        bit_number += 1

    expected = tuple(
        pattern_bits[index % len(pattern_bits)] for index in range(len(decoded))
    )
    mismatch_indexes = tuple(
        index
        for index, (actual, wanted) in enumerate(zip(decoded, expected))
        if actual != wanted
    )

    transition_indexes = tuple(edge[0] for edge in edges)
    normalized_widths = []
    for left, right in zip(transition_indexes, transition_indexes[1:]):
        run_samples = right - left
        expected_bits = int(round(run_samples / samples_per_bit))
        if expected_bits < 1 or expected_bits > 8:
            continue
        unit_samples = run_samples / expected_bits
        if abs(unit_samples - samples_per_bit) <= samples_per_bit * 0.25:
            normalized_widths.append(unit_samples / sample_hz * 1_000_000)
    if not normalized_widths:
        raise ValueError("could not derive bit widths")

    activity_edges = tuple(
        index
        for index in range(1, len(activity_bits))
        if activity_bits[index] != activity_bits[index - 1]
    )
    activity_intervals_us = tuple(
        (right - left) / sample_hz * 1_000_000
        for left, right in zip(activity_edges, activity_edges[1:])
    )

    return {
        "output_hz": output_hz,
        "sample_hz": sample_hz,
        "buffer_samples": buffer_samples,
        "trigger_index": trigger_index,
        "captured_bits": len(decoded),
        "mismatch_count": len(mismatch_indexes),
        "first_mismatch": mismatch_indexes[0] if mismatch_indexes else None,
        "transition_count": len(edges),
        "bit_width_median_us": statistics.median(normalized_widths),
        "bit_width_min_us": min(normalized_widths),
        "bit_width_max_us": max(normalized_widths),
        "decoded_first_32": "".join(str(bit) for bit in decoded[:32]),
        "expected_first_32": "".join(str(bit) for bit in expected[:32]),
        "dio1_transition_count": len(activity_edges),
        "dio1_transition_interval_median_us": (
            statistics.median(activity_intervals_us) if activity_intervals_us else None
        ),
        "dio1_transition_interval_min_us": (
            min(activity_intervals_us) if activity_intervals_us else None
        ),
        "dio1_transition_interval_max_us": (
            max(activity_intervals_us) if activity_intervals_us else None
        ),
    }


def analyse_logic_capture(capture: bytes, pattern_hz: int, sample_hz: int):
    """Recover the known 32-bit pattern from a GP18 PIO+DMA capture."""
    samples = bits_lsb_first(capture)
    pattern_bits = bits_lsb_first(PATTERN_BYTES)
    if sample_hz % pattern_hz:
        raise ValueError("sample rate must be an integer multiple of pattern rate")
    samples_per_bit = sample_hz // pattern_hz
    expected_period = tuple(
        bit for bit in pattern_bits for _ in range(samples_per_bit)
    )

    period_length = len(expected_period)
    sample_counts = [[0, 0] for _ in range(period_length)]
    for index, sample in enumerate(samples):
        sample_counts[index % period_length][sample] += 1

    best_phase = 0
    best_mismatches = len(samples) + 1
    for phase in range(period_length):
        mismatches = sum(
            sample_counts[position][1 - expected_period[(position + phase) % period_length]]
            for position in range(period_length)
        )
        if mismatches < best_mismatches:
            best_phase = phase
            best_mismatches = mismatches

    transition_indexes = tuple(
        index
        for index in range(1, len(samples))
        if samples[index] != samples[index - 1]
    )
    normalized_samples_per_bit = []
    recovered_bits = []
    anomalous_runs = 0
    for left, right in zip(transition_indexes, transition_indexes[1:]):
        run_samples = right - left
        expected_bits = int(round(run_samples / samples_per_bit))
        if expected_bits < 1 or expected_bits > 8:
            anomalous_runs += 1
            continue
        unit_samples = run_samples / expected_bits
        if abs(unit_samples - samples_per_bit) > samples_per_bit * 0.25:
            anomalous_runs += 1
        else:
            normalized_samples_per_bit.append(unit_samples)
            recovered_bits.extend([samples[left]] * expected_bits)

    if not normalized_samples_per_bit:
        raise ValueError("no valid transitions were captured")

    bit_error_scores = tuple(
        sum(
            actual != pattern_bits[(index + phase) % len(pattern_bits)]
            for index, actual in enumerate(recovered_bits)
        )
        for phase in range(len(pattern_bits))
    )
    best_pattern_phase = min(
        range(len(pattern_bits)), key=lambda phase: bit_error_scores[phase]
    )
    bit_errors = bit_error_scores[best_pattern_phase]

    return {
        "capture_bytes": len(capture),
        "capture_samples": len(samples),
        "pattern_hz": pattern_hz,
        "sample_hz": sample_hz,
        "samples_per_pattern_bit": samples_per_bit,
        "best_phase_samples": best_phase,
        "sample_mismatches": best_mismatches,
        "sample_mismatch_rate": best_mismatches / len(samples),
        "transitions": len(transition_indexes),
        "anomalous_runs": anomalous_runs,
        "recovered_bits": len(recovered_bits),
        "best_pattern_phase_bits": best_pattern_phase,
        "bit_errors": bit_errors,
        "bit_error_rate": bit_errors / len(recovered_bits),
        "normalized_bit_samples_median": statistics.median(
            normalized_samples_per_bit
        ),
        "normalized_bit_samples_min": min(normalized_samples_per_bit),
        "normalized_bit_samples_max": max(normalized_samples_per_bit),
    }


def make_vcd(capture: bytes, sample_hz: int, capture_date: str) -> str:
    """Convert one packed one-bit capture into a compact VCD string."""
    if 1_000_000_000 % sample_hz:
        raise ValueError("sample period cannot be represented as integer nanoseconds")
    samples = bits_lsb_first(capture)
    tick_ns = 1_000_000_000 // sample_hz
    lines = [
        f"$date {capture_date} $end",
        "$version Pico 2 W MicroPython PIO+DMA capture $end",
        "$timescale 1ns $end",
        "$scope module logic $end",
        "$var wire 1 ! GP18 $end",
        "$upscope $end",
        "$enddefinitions $end",
    ]
    previous = None
    for index, sample in enumerate(samples):
        if sample != previous:
            lines.extend((f"#{index * tick_ns}", f"{sample}!"))
            previous = sample
    lines.append(f"#{len(samples) * tick_ns}")
    return "\n".join(lines) + "\n"
