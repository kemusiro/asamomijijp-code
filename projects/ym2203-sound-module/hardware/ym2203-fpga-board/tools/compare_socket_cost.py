#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare five-board assembly scopes against the existing assumed U budget."""
import argparse
import csv
import hashlib
import io
import json
import runpy
from decimal import Decimal, ROUND_CEILING
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def d(value):
    return Decimal(str(value))


def yen_round(value):
    return int((value / 1000).to_integral_value(rounding=ROUND_CEILING) * 1000)


def calculate():
    source = (ROOT / 'socket-cost-inputs.json').read_bytes()
    cfg = json.loads(source)
    baseline_bytes = (ROOT / cfg['baseline_inputs']).read_bytes()
    baseline = json.loads(baseline_bytes)
    # Run the canonical calculator without __main__ or Python bytecode writes.
    calculator_path = ROOT / 'tools/analyze_cost.py'
    calculator = runpy.run_path(str(calculator_path))
    report_text, _ = calculator['calculate']()
    baseline_report = json.loads(report_text)
    quantity = cfg['assembled_quantity']
    assert quantity == 5 and not cfg['quote_received']
    reference = next(row for row in baseline_report['cases'] if row['assembled_quantity'] == quantity)
    old_lines = {key: [d(value) for value in bounds] for key, bounds in reference['line_items_usd'].items()}
    rates = baseline['published_standard_pcba_rates']
    single = cfg['published_single_side_rates']
    owner = cfg['owner_assembly']
    moved = owner['pico_mainboard_socket_pins_per_board'] + owner['ym_ic_socket_pins_per_board']
    manual_before = baseline['assumptions_not_measured_bom_or_quote']['manual_joints_per_board']
    assert 0 < moved <= manual_before
    manual_after = manual_before - moved
    fx = d(baseline['jpy_per_usd_planning_assumption_not_spot_rate'])
    multiplier = fx * (1 + d(baseline['tax_reserve_fraction_assumption_not_tax_calculation'])) * (1 + d(baseline['contingency_fraction']))
    baseline_subtotal = [sum(bounds[i] for bounds in old_lines.values()) for i in range(2)]
    variants = []

    def variant(name, lines, self_assembly, conditional=False):
        subtotal = [sum(bounds[i] for bounds in lines.values()) for i in range(2)]
        total = [amount * multiplier for amount in subtotal]
        # Paired endpoints preserve common assumptions; not independent price intervals.
        saving = [(baseline_subtotal[i] - subtotal[i]) * multiplier for i in range(2)]
        component_total = lines['components']
        local_components = [d(value) * quantity for value in cfg['local_component_allocation_usd_per_board']] if self_assembly else [d(0), d(0)]
        supplier_components = [component_total[i] - local_components[i] for i in range(2)]
        assert all(value >= 0 for value in supplier_components)
        variants.append({
            'name': name, 'conditional_service_acceptance': conditional,
            'line_items_usd': {key: [float(value) for value in bounds] for key, bounds in lines.items()},
            'component_split_usd_included_in_total': {
                'supplier': [float(value) for value in supplier_components],
                'owner': [float(value) for value in local_components],
            },
            'subtotal_usd': [float(value) for value in subtotal],
            'planning_total_jpy_rounded_up_1000': [yen_round(value) for value in total],
            'planning_per_board_jpy_rounded_up_1000': [yen_round(value / quantity) for value in total],
            'paired_saving_jpy_before_rounding': [float(value) for value in saving],
        })

    variant('U_previous_double_side_full_outsource', old_lines, False)
    standard = {key: bounds[:] for key, bounds in old_lines.items()}
    fixed = sum(d(rates[key]) for key in ['rigid_fixture_small_order_total', 'hand_solder_labor_per_order', 'placement_confirmation_per_order'])
    fixed += d(single['standard_setup']) + d(single['standard_stencil'])
    standard['published_fixed_assembly_fee_model'] = [fixed, fixed]
    manual_cost = d(manual_after) * quantity * d(rates['manual_per_joint_small_order'])
    standard['manual_joint_model'] = [manual_cost, manual_cost]
    variant('S_single_side_Standard_owner_sockets_common_logistics', standard, True)
    shipping = [d(value) for value in cfg['local_purchase_extra_shipping_usd_per_order']]
    standard_shipping = {**standard, 'owner_additional_shipping_allowance': shipping}
    variant('S_plus_owner_additional_shipping_allowance', standard_shipping, True)

    economic = {key: bounds[:] for key, bounds in standard_shipping.items()}
    economic_fixed = sum(d(rates[key]) for key in ['hand_solder_labor_per_order', 'placement_confirmation_per_order'])
    economic_fixed += d(single['economic_setup']) + d(single['economic_stencil'])
    economic['published_fixed_assembly_fee_model'] = [economic_fixed, economic_fixed]
    charged = cfg['economic_conditional_case']['charged_extended_types_assumption']
    total_types = cfg['economic_conditional_case']['total_type_assumption']
    assert all(0 <= charged[i] <= total_types[i] for i in range(2))
    economic['feeder_loading_model'] = [d(value) * d(single['economic_feeder_per_charged_extended_type']) for value in charged]
    variant('E_conditional_Economic_15_to_25_charged_types_plus_local_shipping', economic, True, True)
    all_extended = {**economic, 'feeder_loading_model': [d(value) * d(single['economic_feeder_per_charged_extended_type']) for value in total_types]}
    variant('E_all_types_charged_sensitivity_plus_local_shipping', all_extended, True, True)

    setup_saving = (d(rates['setup_double_side_per_order']) + d(rates['stencil_double_side_per_order']) - d(single['standard_setup']) - d(single['standard_stencil'])) * multiplier
    socket_saving = d(moved) * quantity * d(rates['manual_per_joint_small_order']) * multiplier
    assert abs(setup_saving + socket_saving - d(variants[1]['paired_saving_jpy_before_rounding'][0])) < d('0.001')
    result = {
        'schema_version': 1, 'date': cfg['date'], 'status': cfg['status'],
        'inputs_sha256': hashlib.sha256(source).hexdigest(),
        'baseline_inputs_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
        'baseline_calculator_sha256': hashlib.sha256(calculator_path.read_bytes()).hexdigest(),
        'comparison_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'assembled_quantity': quantity,
        'manual_joints_per_board_assumed_before_after': [manual_before, manual_after],
        'owner_socket_joints_per_board': moved,
        'additional_Pico_male_header_savings_counted': False,
        'owner_socket_joints_all_boards': moved * quantity,
        'common_fx_tax_contingency_multiplier_jpy_per_model_usd': float(multiplier),
        'standard_setup_stencil_saving_jpy_before_rounding': float(setup_saving),
        'socket_assembly_saving_jpy_before_rounding': float(socket_saving),
        'cases': variants,
        'owner_labor_priced': False, 'quote_received': False,
        'complete_BOM_or_service_acceptance_confirmed': False,
        'identical_supplier_function_test_scope_confirmed': False,
    }
    out = io.StringIO(newline='')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['case', 'five_board_total_jpy_low', 'five_board_total_jpy_high', 'per_board_jpy_low', 'per_board_jpy_high', 'paired_saving_jpy_low_endpoint', 'paired_saving_jpy_high_endpoint', 'conditional_acceptance'])
    for row in variants:
        writer.writerow([row['name'], *row['planning_total_jpy_rounded_up_1000'], *row['planning_per_board_jpy_rounded_up_1000'], *row['paired_saving_jpy_before_rounding'], row['conditional_service_acceptance']])
    return json.dumps(result, ensure_ascii=False, indent=2) + '\n', out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report, csv_text = calculate()
    for path, content in [(ROOT / 'verification/socket-cost-check.json', report), (ROOT / 'socket-cost-summary.csv', csv_text)]:
        if args.write:
            path.write_text(content, encoding='utf-8')
        else:
            assert path.read_text() == content, f'Stale {path.name}; use --write'
    for row in json.loads(report)['cases']:
        print(row['name'], row['planning_total_jpy_rounded_up_1000'])
    print('PASS: paired comparison, component accounting and generated outputs; NOT a quote')


if __name__ == '__main__':
    main()
