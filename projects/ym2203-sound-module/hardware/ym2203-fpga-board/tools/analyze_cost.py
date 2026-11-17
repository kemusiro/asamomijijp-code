#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute an explicitly assumed budget scenario, never a supplier quote."""
import argparse
import csv
import hashlib
import io
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def decimal(value):
    return Decimal(str(value))


def calculate():
    source = (ROOT / 'upper-cost-inputs.json').read_bytes()
    plan = json.loads(source)
    rates = plan['published_standard_pcba_rates']
    assumptions = plan['assumptions_not_measured_bom_or_quote']
    assert not plan['quote_received'] and not plan['order_placed']
    # No automatic assumption that every listed fee applies in a real order.
    fixed_keys = ['setup_double_side_per_order', 'stencil_double_side_per_order',
                  'rigid_fixture_small_order_total', 'hand_solder_labor_per_order',
                  'placement_confirmation_per_order']
    fixed = sum(decimal(rates[key]) for key in fixed_keys)
    lines = []
    for quantity in plan['assembled_quantities']:
        assert 1 <= quantity <= 10, 'Rate tiers in this model stop at 10 assemblies'
        cost_lines = {}

        def add(name, bounds, factor=1):
            low, high = [decimal(value) * decimal(factor) for value in bounds]
            assert 0 <= low <= high, f'Invalid cost interval: {name}'
            cost_lines[name] = [low, high]

        add('components', assumptions['component_allowance_per_board_usd'], quantity)
        add('bare_pcbs', assumptions['bare_pcb_allowance_usd_by_assembled_quantity'][str(quantity)])
        add('published_fixed_assembly_fee_model', [fixed, fixed])
        add('feeder_loading_model', assumptions['feeder_load_count_per_order'], rates['feeder_loading_per_load'])
        smt = decimal(assumptions['smt_joints_per_board']) * decimal(rates['smt_per_joint_small_order']) * quantity
        tht = decimal(assumptions['manual_joints_per_board']) * decimal(rates['manual_per_joint_small_order']) * quantity
        xray = decimal(plan['physical_configuration']['xray_packages_per_board']) * decimal(rates['xray_per_package_up_to_ten']) * quantity
        add('smt_joint_model', [smt, smt])
        add('manual_joint_model', [tht, tht])
        add('xray_model', [xray, xray])
        for name, key in [
            ('program_and_basic_test_allowance', 'program_and_basic_functional_test_per_order_usd'),
            ('procurement_moq_and_spares_allowance', 'procurement_moq_and_spares_extra_per_order_usd'),
            ('handling_and_packaging_allowance', 'other_handling_packaging_storage_per_order_usd'),
            ('shipping_allowance', 'shipping_and_procurement_logistics_per_order_usd'),
        ]:
            add(name, assumptions[key])
        subtotal = [sum(value[index] for value in cost_lines.values()) for index in range(2)]
        fx = decimal(plan['jpy_per_usd_planning_assumption_not_spot_rate'])
        tax_factor = 1 + decimal(plan['tax_reserve_fraction_assumption_not_tax_calculation'])
        reserve_factor = 1 + decimal(plan['contingency_fraction'])
        total = [value * fx * tax_factor * reserve_factor for value in subtotal]
        rounded = [int((value / 1000).to_integral_value(rounding=ROUND_CEILING) * 1000) for value in total]
        lines.append({
            'assembled_quantity': quantity,
            'bare_board_quantity_assumption': max(quantity, plan['physical_configuration']['minimum_bare_pcbs']),
            'line_items_usd': {name: [float(value) for value in bounds] for name, bounds in cost_lines.items()},
            'subtotal_usd': [float(value) for value in subtotal],
            'jpy_total_with_tax_reserve_and_contingency_rounded_up_1000': rounded,
            'jpy_per_assembly_rounded_up_1000': [int((value / quantity / 1000).to_integral_value(rounding=ROUND_CEILING) * 1000) for value in total],
        })
    report = {
        'schema_version': 1, 'date': plan['date'], 'status': plan['status'],
        'inputs_sha256': hashlib.sha256(source).hexdigest(),
        'analysis_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'price_reference_four_part_subtotal_usd_excludes_remaining_bom': float(sum(decimal(part['usd_one_piece_display']) for part in plan['public_price_references'])),
        'published_fixed_fee_model_usd_excludes_feeders': float(fixed),
        'cases': lines, 'quote_received': False,
        'is_guaranteed_upper_bound': False,
        'counts_or_complete_BOM_verified': False,
    }
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['assembled_quantity', 'bare_boards_assumed', 'model_subtotal_usd_low', 'model_subtotal_usd_high', 'planning_total_jpy_low', 'planning_total_jpy_high', 'planning_jpy_per_assembly_low', 'planning_jpy_per_assembly_high'])
    for row in lines:
        writer.writerow([row['assembled_quantity'], row['bare_board_quantity_assumption'], *row['subtotal_usd'], *row['jpy_total_with_tax_reserve_and_contingency_rounded_up_1000'], *row['jpy_per_assembly_rounded_up_1000']])
    return json.dumps(report, ensure_ascii=False, indent=2) + '\n', out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report, csv_text = calculate()
    for path, content in [(ROOT / 'verification/upper-cost-check.json', report), (ROOT / 'upper-cost-summary.csv', csv_text)]:
        if args.write:
            path.write_text(content, encoding='utf-8')
        else:
            assert path.read_text() == content, f'Stale {path.name}; use --write'
    for row in json.loads(report)['cases']:
        print(row['assembled_quantity'], 'assemblies: JPY planning total', row['jpy_total_with_tax_reserve_and_contingency_rounded_up_1000'])
    print('PASS: assumed budget recalculation and generated outputs match; NOT a quote or guaranteed ceiling')


if __name__ == '__main__':
    main()
