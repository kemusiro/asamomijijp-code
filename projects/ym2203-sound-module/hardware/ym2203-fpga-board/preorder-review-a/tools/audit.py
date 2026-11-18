#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read native PCB and reproduce the pre-order dimensional review; never save CAD."""
import argparse
import hashlib
import json
from pathlib import Path

import pcbnew as p


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--hardware-root', type=Path, default=Path(__file__).resolve().parents[2])
    cli.add_argument('--output', type=Path)
    args = cli.parse_args()
    hw = args.hardware_root
    inputs = [
        'clean-sheet-pcb-review-j/base/p2-base-j.kicad_pcb',
        'clean-sheet-pcb-review-k/module/p2-ym2203-k.kicad_pcb',
        'primary-order-5pcb-1set/order-plan.json',
        'primary-order-5pcb-1set/assembly-vias.json',
        'clean-sheet-pcb-review-j/mechanical-review.json',
    ]
    digest = lambda file: hashlib.sha256(file.read_bytes()).hexdigest()
    before = {name: digest(hw / name) for name in inputs}
    board = p.LoadBoard(str(hw / inputs[0]))
    fp = next(f for f in board.GetFootprints() if f.GetReference() == 'JUSB')
    pads = []
    for pad in fp.Pads():
        xy = pad.GetFPRelativePosition()
        size, drill = pad.GetSize(), pad.GetDrillSize()
        pads.append({
            'number': pad.GetNumber(),
            'x_mm': p.ToMM(xy.x), 'y_mm': p.ToMM(xy.y),
            'width_mm': p.ToMM(size.x), 'length_mm': p.ToMM(size.y),
            'drill_width_mm': p.ToMM(drill.x), 'drill_length_mm': p.ToMM(drill.y),
        })
    by_number = {q['number']: q for q in pads if q['number']}
    npth = [q for q in pads if not q['number']]
    shell = [q for q in pads if q['number'] == 'SH']
    rear = max(shell, key=lambda q: q['y_mm'])
    front = min(shell, key=lambda q: q['y_mm'])
    # Manufacturer values are transcribed from the inspected HRO 2020-12-08 drawing.
    comparisons = [
        ('positioning_hole_diameter_mm', npth[0]['drill_width_mm'], 0.60),
        ('signal_pad_length_mm', by_number['A6']['length_mm'], 1.14),
        ('outer_ground_pad_span_mm', abs(by_number['A1']['x_mm'] - by_number['A12']['x_mm']), 6.40),
        ('vbus_pad_span_mm', abs(by_number['A4']['x_mm'] - by_number['A9']['x_mm']), 4.80),
        ('rear_shell_slot_length_mm', rear['drill_length_mm'], 1.40),
        ('rear_shell_copper_width_mm', rear['width_mm'], 0.90),
        ('rear_shell_copper_length_mm', rear['length_mm'], 1.70),
        ('front_shell_copper_width_mm', front['width_mm'], 0.90),
        ('front_shell_copper_length_mm', front['length_mm'], 2.00),
    ]
    checks = [{'feature': name, 'pcb': round(actual, 6), 'hro_recommended': expected,
               'difference': round(actual - expected, 6)} for name, actual, expected in comparisons]
    order = json.loads((hw / inputs[2]).read_text())
    assert order['selection'] == 'base4-module2'
    assert order['profile']['pcb_each'] == 5 and order['profile']['fitted_sets'] == 1
    assert len(npth) == 2 and len(shell) == 4
    assert len(checks) == 9 and all(q['difference'] != 0 for q in checks)
    after = {name: digest(hw / name) for name in inputs}
    assert before == after, 'Read-only audit changed an input'
    result = {
        'schema_version': 1, 'date': '2026-11-18', 'review': 'preorder-review-a',
        'status': 'usb_purchase_drawing_land_pattern_mismatch_unresolved',
        'fabrication_release': False, 'cad_changed': False, 'gerber_changed': False,
        'hardware_accepted': False, 'input_sha256': before,
        'usb': {'reference': 'base:JUSB', 'procurement_id': 'J10',
                'footprint': str(fp.GetFPID().GetLibItemName()),
                'supplier_candidate': 'LCSC C165948',
                'manufacturer_recommended_values': 'manual transcription, HRO drawing 2020-12-08',
                'pads_native': pads, 'dimensional_differences': checks,
                'fit_failure_proven': False},
        'socket_nominal_geometry': {
            'part': '0300-2-15-15-47-27-10-0',
            'drawing_hole_min_mm': 1.07, 'pcb_hole_nominal_mm': 1.20,
            'tail_mm': 4.75, 'pcb_thickness_mm': 1.6,
            'tail_protrusion_mm': round(4.75 - 1.6, 3),
            'male_header_insulator_mm': 2.5, 'male_mating_pin_mm': 6.1,
            'mcu_underside_mm': 9.5, 'socket_mouth_nominal_mm': 5.33,
            'nominal_engagement_mm': round(2.5 + 6.1 - (9.5 - 5.33), 3),
            'physical_fit_confirmed': False,
            'assumption': 'insulator directly below MCU board; socket shoulder seated on carrier',
        },
        'adc_capacitor_screening': {
            'id': 'C14', 'refs': ['base:CACL', 'base:CACR'], 'qty': 2,
            'nominal_bias_v': 1.65, 'bias_assumption': 'AVDD=3.3V, source DC=0V',
            'capacitance_uf': 10, 'assumed_tolerance_retention': 0.9,
            'assumed_temperature_retention': 0.85, 'required_effective_uf': 4.7,
            'minimum_dc_retention_fraction': round(4.7 / (10 * 0.9 * 0.85), 6),
            'manufacturer_combined_guarantee': False, 'mpn_approved': False,
        },
    }
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    else:
        saved = json.loads((hw / 'preorder-review-a/audit.json').read_text())
        assert result == saved, 'Native data differs from recorded review'
    print('PASS: read-only input hashes and nine USB dimensional differences reproduced; '
          'socket/ADC arithmetic recorded; fabrication release remains FALSE')


if __name__ == '__main__':
    main()
