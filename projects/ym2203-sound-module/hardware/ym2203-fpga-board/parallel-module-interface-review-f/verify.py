# SPDX-License-Identifier: MIT
"""Validate review F sources against preserved E/C and actual Rev C wire constants."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def load():
    return {name: read(HERE / (name + '.json')) for name in
            ('connector', 'architecture', 'gpio-proposal', 'profiles', 'bus-timing')}


def references(hardware):
    e = hardware / 'analog-module-interface-review-e'
    firmware = hardware.parent.parent / 'firmware-c/src'
    return {'e_connector': read(e/'connector.json'), 'e_architecture': read(e/'architecture.json'),
            'approved_gpio': read(hardware/'digital-module-review-c/pins.json'),
            'stream_header': (firmware/'stream.h').read_text(),
            'stream_source': (firmware/'stream.c').read_text()}


def validate(data, ref):
    c, a, g, pp, t = (data[x] for x in
                       ('connector', 'architecture', 'gpio-proposal', 'profiles', 'bus-timing'))
    errors = []

    def check(ok, code):
        if not ok:
            errors.append(code)

    pins = {p['pin']: p for p in c['pins']}
    check(len(c['pins']) == len(pins) == c['positions'] == 40 and set(pins) == set(range(1, 41)), '40_positions')
    check(c['rows'] == 20 and c['pitch_mm'] == 2.54 and c['contact_grid_length_mm'] == 48.26, 'geometry')
    check(all(p['row'] == (p['pin']+1)//2 and p['column'] == ('A' if p['pin']%2 else 'B') for p in c['pins']), 'orientation')
    check(pins.get(32, {}).get('signal') == 'KEY' and not c['old32_mating_approved'] and not c['hot_plug'], 'mating')
    for p in ref['e_connector']['pins']:
        check(all(pins.get(p['pin'], {}).get(k) == p.get(k) for k in
                  ('signal', 'direction', 'voltage_v', 'kind', 'base_gpio_proposed')), 'E_spi_pin_preservation')
    check(all(p['voltage_v'] == 3.3 for p in c['pins'] if p['kind'] == 'digital'), '3v3_connector')
    check(sum(p['kind'] == 'ground' for p in c['pins']) == 12, 'ground_count')
    expected = {33: ('BUS_D4', 30), 34: ('BUS_D5', 31), 35: ('BUS_D6', 32), 36: ('BUS_D7', 33),
                37: ('MOD_CTL0', 6), 38: ('MOD_CTL1', 7), 39: ('MOD_CTL2', 17), 40: ('MOD_CTL3', 18)}
    check(all((pins.get(n, {}).get('signal'), pins.get(n, {}).get('base_gpio_proposed')) == v
              for n, v in expected.items()), 'extra_pin_map')
    for pin, bit in [(8, 0), (9, 1), (5, 2), (7, 3)]:
        check(pins[pin].get('parallel_alias') == 'BUS_D'+str(bit), 'shared_aliases')
    approved = ref['approved_gpio']
    check(g['preserved_base'] == approved['base'], 'approved_gpio_preservation')
    check(g['approval_required_before_implementation'] and not g['firmware_applied']
          and not g['schematic_applied'] and not c['gpio_adopted'], 'approval_pending')
    extra = {p['gpio'] for p in g['additions']}
    check(len(extra) == len(g['additions']) == 9 and extra == {5, 6, 7, 17, 18, 30, 31, 32, 33}, 'gpio_additions')
    used = {p['gpio'] for p in approved['base']}
    check(not extra.intersection(used) and extra <= set(approved['base_free_gpio']), 'gpio_conflict')
    check(g['base_assigned_proposed'] == len(used | extra) == 44
          and g['base_free_gpio_proposed'] == sorted(set(approved['base_free_gpio']) - extra) == [35, 36, 37], 'gpio_budget')
    check(g['parallel_data_gpio_lsb_first'] == [0, 1, 2, 3, 30, 31, 32, 33]
          and g['parallel_control_gpio'] == {'CTL0': 6, 'CTL1': 7, 'CTL2': 17, 'CTL3': 18}, 'gpio_roles')
    ea = ref['e_architecture']
    check(a['audio'] == ea['audio'] and g['audio_data'] == {'dac_tx':26,'module_rx':16,'adc_rx_candidate':5}, 'audio_preservation')
    check(g['host_i2c'] == {'controller':0,'sda':20,'scl':21,'address':66,'hz':100000}
          and g['service_i2c'] == {'controller':1,'sda':42,'scl':43,'hz':100000}, 'i2c_preservation')
    ctrl = a['control']
    check(not ctrl['spi_parallel_simultaneous'] and ctrl['service_i2c_remains_available_in_parallel'], 'bus_exclusion')
    check(ctrl['bus_modes'] == ['spi', 'parallel8', 'i2c']
          and ctrl['switch_only'] == 'stopped_no_owner_MOD_ENABLE_low_final_gates_closed', 'mode_selection')
    check(ctrl['mode_switch_sequence'] == [
        'require_stopped_no_owner', 'close_final_gates', 'MOD_ENABLE_low',
        'cancel_generation_and_flush_queues', 'disable_SPI_and_bus_writer',
        'all_shared_data_and_aux_high_impedance', 'select_manual_profile_and_check_voltage_and_clock',
        'set_inactive_control_levels_then_set_pin_functions', 'initialize_muted_chip_and_audio_paths',
        'await_explicit_PLAY_or_NoteOn_before_prime_and_unmute'], 'mode_switch_order')
    par = ctrl['parallel']
    check(par['connector_data_lsb_first'] == [8,9,5,7,33,34,35,36]
          and par['gpio_data_lsb_first'] == g['parallel_data_gpio_lsb_first'], 'parallel_data_order')
    check(par['data_bits'] == 8 and par['controls'] == {'CTL0':37,'CTL1':38,'CTL2':39,'CTL3':40}, 'parallel_width')
    check(not par['five_volt_translation_removed'] and not par['native_parallel_adapter_required_on_source'], 'parallel_simplification')
    check(not par['single_pio_OUT_8_supported_by_this_mapping'] and not g['single_pio_8bit_out_claimed']
          and not par['data_may_update_while_strobe_active'], 'SIO_strobe_contract')
    check(not par['timing_guaranteed_on_hardware'], 'timing_not_bench')
    check(a['slots'] == 1 and not a['hot_plug'] and not a['module_mcu_required']
          and not a['module_adc_required'] and not a['module_eeprom_required'], 'minimal_scope')
    for key, value in ea['stop'].items():
        check(a['stop'].get(key) == value, 'stop_ownership_preservation')
    check(a['stop']['parallel_cleanup'].startswith('gate first;'), 'parallel_stop')
    check(all(a['legacy'].get(k) == v for k,v in ea['legacy'].items()), 'legacy_preservation')
    check(a['legacy']['default_module_transport'] == 'existing_SPI0_Core2350B0_FM_bridge', 'opn_transport')
    defines = {k: int(v) for k,v in re.findall(r'#define\s+(REVC_\w+)\s+(\d+)u', ref['stream_header'])}
    check(defines.get('REVC_STATUS_SIZE') == a['legacy']['status_bytes'] == 64
          and defines.get('REVC_QUEUE_CAPACITY') == a['legacy']['fifo_events'] == 1024
          and defines.get('REVC_LEASE_US') == a['legacy']['lease_ms'] * 1000 == 1000000
          and defines.get('REVC_PACKET_PAYLOAD') == a['legacy']['event_bytes']*a['legacy']['push_max_events'] == 192
          and a['legacy']['signature'] in ref['stream_source'], 'C_wire_constants')
    check(not a['power']['module_regulator_outputs_connected_to_aux']
          and a['power']['module_aux_3v3_budget_ma'] == 100
          and not a['power']['external_module_power'], 'power_policy')
    profiles = pp['profiles']
    ids = {p['id'] for p in profiles}
    check(len(ids) == len(profiles) == 7
          and {'ay38910_parallel','sn76489an_parallel','opn1_hybrid'} <= ids, 'profile_set')
    for p in profiles:
        check(p['bus_mode'] in ctrl['bus_modes'], 'profile_mode')
        check(not p['parallel_readback'] and not p['module_adc'], 'write_only_profiles')
        check(not p['legacy_wym1'] or p['id'] == 'opn1_hybrid', 'profile_identity')
        check(not set(p['analog_sources']).intersection(p['digital_sources']), 'double_audio')
        check(len(set(p['i2c_addresses_7bit'])) == len(p['i2c_addresses_7bit'])
              and all(8 <= n <= 0x77 and n not in ctrl['service_reserved_addresses'].values()
                      for n in p['i2c_addresses_7bit']), 'i2c_collision')
    ay = next((p for p in profiles if p['id'] == 'ay38910_parallel'), {})
    sn = next((p for p in profiles if p['id'] == 'sn76489an_parallel'), {})
    opn = next((p for p in profiles if p['id'] == 'opn1_hybrid'), {})
    check(ay.get('bus_mode') == sn.get('bus_mode') == 'parallel8' and ay.get('module_mcu') is None
          and sn.get('module_mcu') is None, 'direct_psg_no_bridge')
    check(ay.get('clock_hz_candidate') == 2000000 and ay.get('control_roles') == {
        'CTL0':'NC_BC1_tied_low_on_module','CTL1':'BC2','CTL2':'BDIR','CTL3':'NC'}, 'AY_control')
    check(sn.get('logical_bit_to_ic_data') == ['D7','D6','D5','D4','D3','D2','D1','D0']
          and sn.get('logical_bit_to_ic_pin') == [10,11,12,13,15,1,2,3], 'SN_MSB_mapping')
    check(sn.get('control_roles') == {'CTL0':'NC','CTL1':'CE_N','CTL2':'WE_N','CTL3':'READY_input'}, 'SN_ready_pin')
    check(opn.get('bus_mode') == 'spi' and opn.get('module_mcu') == 'Core2350B0', 'opn_bridge_retained')
    ayt, snt = t['ay38910'], t['sn76489an']
    check(ayt['bc1_fixed'] == 0 and ayt['address_bdir_bc2_bc1'] == [1,0,0]
          and ayt['write_bdir_bc2_bc1'] == [1,1,0], 'AY_no_read')
    cand, limits = ayt['candidate_ns'], ayt['datasheet_ns']
    check(cand['setup'] >= max(limits['address_setup_min'], limits['write_setup_min'])
          and cand['hold'] >= max(limits['address_hold_min'], limits['write_hold_min'])
          and limits['write_pulse_min'] <= cand['write_pulse'] <= limits['write_pulse_max'] == 10000, 'AY_timing')
    check(snt['load_clocks'] == 32 and not snt['ready_high_before_minimum_delay_sufficient']
          and snt['complete_only_after_ready_high'] and not snt['STOP_waits_for_READY']
          and snt['ready_deadline_us'] == 100, 'SN_timing')
    return sorted(set(errors))


def verify_files(hardware):
    errors = validate(load(), references(hardware))
    for p in read(HERE/'preservation.json')['files']:
        target = hardware / p['path'].removeprefix('../')
        if hashlib.sha256(target.read_bytes()).hexdigest() != p['sha256']:
            errors.append('preservation:'+p['path'])
    if hashlib.sha256((hardware/'digital-module-review-c/pins.json').read_bytes()).hexdigest() != load()['gpio-proposal']['approved_manifest_sha256']:
        errors.append('approved_gpio_hash')
    with (HERE/'connector.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    pins = load()['connector']['pins']
    if len(rows) != 40 or any(row[k] != ('' if p.get(k) is None else str(p[k]))
                             for row,p in zip(rows,pins) for k in row):
        errors.append('CSV_mismatch')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hardware-root', type=Path, default=HERE.parent)
    args = parser.parse_args()
    errors = verify_files(args.hardware_root)
    if errors:
        raise SystemExit('FAIL: '+', '.join(errors))
    print('PASS:40positions/12GND;32 SPI-mode contacts retained;44GPIO/3free;parallel/SPI exclusion;PSG bit order and C wire constants')
    print('SCOPE: static proposal only; GPIO, CAD and firmware not applied; no hardware timing acceptance')
