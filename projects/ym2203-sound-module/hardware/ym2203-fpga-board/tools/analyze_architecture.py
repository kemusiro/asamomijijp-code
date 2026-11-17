#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute proposal budgets from Rev C; not synthesis or circuit verification."""
import argparse
import csv
import hashlib
import io
import json
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent.parent


def parts_in(value):
    if isinstance(value, dict):
        if all(key in value for key in ("ref", "value", "pins")):
            yield value
        for child in value.values():
            yield from parts_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from parts_in(child)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def exact_feedback(vco, cfg):
    ratio = Fraction(vco, cfg["reference_hz"])
    return (cfg["feedback_min"] <= ratio <= cfg["feedback_max"]
            and ratio.denominator <= cfg["max_fraction_denominator"])


def clock_profile(ym_hz, cfg):
    require(cfg["ym_request_min_hz"] <= ym_hz <= cfg["ym_request_max_hz"], "YM clock out of proposal range")
    require(cfg["ym_output_multiplier"] == cfg["fpga_ym_divider"], "YM clock multiplier/divider mismatch")
    twice = ym_hz * cfg["ym_output_multiplier"]
    candidates = []
    for divider in range(cfg["output_divider_min"], cfg["output_divider_max"] + 1, 2):
        vco = twice * divider
        if cfg["vco_min_hz"] <= vco <= cfg["vco_max_hz"] and exact_feedback(vco, cfg):
            candidates.append((abs(vco - cfg["pllb_target_vco_hz"]), divider, vco))
    require(candidates, f"No exact even-MultiSynth plan found for {ym_hz} Hz")
    _, divider, vco = min(candidates)
    feedback = Fraction(vco, cfg["reference_hz"])
    integer, fraction = divmod(feedback.numerator, feedback.denominator)
    frame_rate = Fraction(ym_hz, cfg["default_fm_frame_divisor"])
    step = frame_rate / cfg["sample_hz"]
    return {
        "requested_ym_hz": ym_hz,
        "clk0_hz": twice,
        "pllb_vco_hz": vco,
        "pllb_feedback_a_b_c": [integer, fraction, feedback.denominator],
        "output_multisynth_even_divider": divider,
        "actual_synthesis_hz": ym_hz,
        "mathematical_error_ppm": 0,
        "fm_frame_hz": float(frame_rate),
        "resampler_input_step_numerator": step.numerator,
        "resampler_input_step_denominator": step.denominator,
        "physical_frequency_or_jitter_measured": False,
    }


def memory_budget(entry):
    depth, width = entry["depth"], entry["width_bits"]
    require(depth > 0 and width > 0, "Invalid memory allocation")
    if entry["memory"] == "EBR":
        # SB_RAM40_4K in 256x16 or 1024x4 mode; round geometry, not just bits.
        require(entry["layout"] in ("1024x4", "256x16"), "Unsupported EBR geometry")
        mode_depth, mode_width = (1024, 4) if entry["layout"] == "1024x4" else (256, 16)
    else:
        require(entry["memory"] == "SPRAM", "Unknown memory kind")
        require(entry["layout"] == "16384x16", "Unsupported SPRAM geometry")
        mode_depth, mode_width = 16384, 16
    blocks = ((depth + mode_depth - 1) // mode_depth) * ((width + mode_width - 1) // mode_width)
    return {**entry, "blocks": blocks, "payload_bits": depth * width}


def analyze():
    plan_bytes = (ROOT / "architecture.json").read_bytes()
    plan = json.loads(plan_bytes)
    baseline_path = PROJECT / plan["baseline_design"]
    baseline_bytes = baseline_path.read_bytes()
    baseline = list(parts_in(json.loads(baseline_bytes)))
    by_ref = {part["ref"]: part for part in baseline}
    require(len(by_ref) == len(baseline), "Duplicate Rev C references")
    expected = {ref for ref in by_ref if ref.startswith("A") or (ref.startswith("U") and ref[1:].isdigit())}
    mapped = [ref for row in plan["components"] for ref in row["baseline_refs"]]
    require(len(mapped) == len(set(mapped)), "Baseline reference mapped twice")
    require(set(mapped) == expected, "Comparison must cover every baseline A/U device")
    for row in plan["components"]:
        require(0 <= row["min"] <= row["max"], "Invalid component count interval")

    cfg, fpga = plan["clocks"], plan["fpga"]
    require(cfg["plla_vco_hz"] == cfg["system_hz"] * cfg["plla_system_divider"], "System clock plan mismatch")
    require(cfg["vco_min_hz"] <= cfg["plla_vco_hz"] <= cfg["vco_max_hz"], "PLLA VCO out of range")
    require(exact_feedback(cfg["plla_vco_hz"], cfg), "System clock requires approximation")
    frame_cycles = Fraction(cfg["system_hz"], cfg["sample_hz"])
    bit_cycles = frame_cycles / (cfg["i2s_slot_bits"] * cfg["i2s_slots"])
    require(frame_cycles.denominator == bit_cycles.denominator == 1, "I2S is not integer divided")
    profiles = [clock_profile(hz, cfg) for hz in cfg["ym_test_profiles_hz"] + cfg["boundary_model_profiles_hz"]]
    # A sweep adds coverage between named profiles; it is not every integer Hz.
    sweep = list(range(cfg["ym_request_min_hz"], cfg["ym_request_max_hz"] + 1, 10000))
    for hz in sweep:
        clock_profile(hz, cfg)

    used_pins = sum(group["count"] for group in plan["pins"])
    conservative_pins = fpga["total_user_io"] - fpga["open_drain_only_io"]
    require(used_pins <= conservative_pins, "Push-pull-capable I/O budget exceeded")
    memory = [memory_budget(entry) for entry in plan["memory_allocations"]]
    ebr_used = sum(entry["blocks"] for entry in memory if entry["memory"] == "EBR")
    spram_used = sum(entry["blocks"] for entry in memory if entry["memory"] == "SPRAM")
    dsp_used = sum(entry["blocks"] for entry in plan["dsp_allocations"])
    require(ebr_used <= fpga["ebr_blocks"], "EBR budget exceeded")
    require(spram_used <= fpga["spram_blocks"], "SPRAM budget exceeded")
    require(dsp_used <= fpga["dsp_blocks"], "DSP budget exceeded")

    targets = plan["capacity_targets"]
    batch = targets["spi_header_crc_bytes"] + targets["spi_batch_records"] * targets["fpga_event_bytes"]
    csv_file = io.StringIO(newline="")
    writer = csv.writer(csv_file, lineterminator="\n")
    writer.writerow(["function", "rev_c_refs", "rev_c_devices", "candidate", "proposed_min", "proposed_max"])
    for row in plan["components"]:
        writer.writerow([row["function"], "+".join(row["baseline_refs"]), len(row["baseline_refs"]), row["candidate"], row["min"], row["max"]])
    report = {
        "schema_version": 1,
        "status": "static_architecture_budget_and_clock_arithmetic_only",
        "date": plan["date"],
        "architecture_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "analysis_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rev_c_design_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "baseline_definition_count": len(baseline),
        "baseline_mountable_definitions_excluding_TP_and_H": sum(not ref.startswith(("TP", "H")) for ref in by_ref),
        "component_comparison": {
            "counting_unit": "A/U main-PCB IC or module placements; not module internals or total BOM",
            "rev_c": len(expected),
            "proposal_min": sum(row["min"] for row in plan["components"]),
            "proposal_max": sum(row["max"] for row in plan["components"]),
            "oscillator_change": "X1 is replaced by a crystal; Si5351 is counted as a new IC",
            "total_placement_reduction_proven": False,
        },
        "pin_budget": {
            "planned_regular_io": used_pins,
            "regular_io_conservative_capacity": conservative_pins,
            "regular_io_unassigned": conservative_pins - used_pins,
            "open_drain_only_unused": fpga["open_drain_only_io"],
            "dedicated_configuration_pins_separate": fpga["dedicated_configuration_pins"],
            "pico_gpio_budget": sum(group["count"] for group in plan["pico_signal_groups"]),
            "bank_global_pin_configuration_placement_verified": False,
        },
        "resource_budget": {
            "allocations": memory,
            "ebr_blocks": [ebr_used, fpga["ebr_blocks"]],
            "spram_blocks": [spram_used, fpga["spram_blocks"]],
            "dsp_blocks": [dsp_used, fpga["dsp_blocks"]],
            "lut_design_budget": int(fpga["logic_cells"] * Fraction(str(targets["lut_budget_fraction"]))),
            "lut_usage_measured": None,
        },
        "clock_plan": {
            "system_hz": cfg["system_hz"],
            "plla_vco_hz": cfg["plla_vco_hz"],
            "i2s_lrck_hz": cfg["sample_hz"],
            "i2s_bclk_hz": cfg["sample_hz"] * cfg["i2s_slot_bits"] * cfg["i2s_slots"],
            "system_cycles_per_i2s_frame": int(frame_cycles),
            "system_cycles_per_i2s_bit": int(bit_cycles),
            "profiles": profiles,
            "intermediate_sweep_cases": len(sweep),
            "clock_register_generation_and_hardware_tested": False,
        },
        "throughput_budget": {
            "spi_batch_bytes": batch,
            "ideal_batch_wire_us": batch * 8 * 1000000 / targets["spi_hz"],
            "ideal_events_per_second_excludes_status_cpu_and_crc": targets["spi_hz"] / (batch * 8) * targets["spi_batch_records"],
            "existing_YsII_max_1s_events": 569,
            "hardware_measured": False,
        },
        "audio_budget": {
            "startup_fifo_samples": targets["initial_audio_fifo_frames"],
            "startup_fifo_ms_at_48k": targets["initial_audio_fifo_frames"] * 1000 / cfg["sample_hz"],
            "full_path_audible_latency_measured": False,
            "anti_alias_filter_implemented": False,
        },
        "not_verified": ["RTL", "synthesis", "place_and_route", "timing_closure", "complete_pin_map", "power_sequence", "complete_BOM", "schematic_ERC", "PCB_DRC", "physical_hardware"],
    }
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n", csv_file.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="refresh checked-in analysis outputs")
    args = parser.parse_args()
    report, csv_text = analyze()
    outputs = [(ROOT / "verification/architecture-check.json", report), (ROOT / "bom-comparison.csv", csv_text)]
    if args.write:
        for path, text in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
    else:
        for path, text in outputs:
            require(path.read_text(encoding="utf-8") == text, f"Stale generated analysis: {path.name}; use --write")
    result = json.loads(report)
    print("PASS: proposal arithmetic, source BOM partition and generated outputs")
    print("A/U devices:", result["component_comparison"])
    print("I/O:", result["pin_budget"])
    print("EBR/SPRAM/DSP:", result["resource_budget"]["ebr_blocks"], result["resource_budget"]["spram_blocks"], result["resource_budget"]["dsp_blocks"])
    print("Clock profiles:", len(result["clock_plan"]["profiles"]), "intermediate cases:", result["clock_plan"]["intermediate_sweep_cases"])
    print("NOT synthesis, circuit approval or hardware acceptance")


if __name__ == "__main__":
    main()
