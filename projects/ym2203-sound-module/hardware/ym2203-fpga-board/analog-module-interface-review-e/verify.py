# SPDX-License-Identifier: MIT
"""Static review-E contract checks. Does not emulate hardware or implement firmware."""
import argparse
import csv
import hashlib
import json
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def load():
    return {name: read(HERE / (name + '.json')) for name in
            ('connector', 'architecture', 'profiles', 'gpio-proposal')}


def validate(data, old_connector, old_gpio, header, stream_source):
    """Return stable error codes for incompatible proposals, never modify inputs."""
    errors = []

    def require(condition, code):
        if not condition:
            errors.append(code)

    c, a, p, g = (data[k] for k in ('connector', 'architecture', 'profiles', 'gpio-proposal'))
    pins = c['pins']
    indexed = {x['pin']: x for x in pins}
    require(len(pins) == len(indexed) == c['positions'] == 32 and set(indexed) == set(range(1, 33)), 'pin_count')
    require(c['pitch_mm'] == 2.54 and c['rows'] == 16, 'geometry')
    require(all(x['row'] == (x['pin'] + 1) // 2 and x['column'] == ('A' if x['pin'] % 2 else 'B')
                for x in pins), 'pin_orientation')
    required = {25: 'V3V3_MODULE_AUX', 27: 'AUDIO_L', 28: 'AUDIO_R',
                29: 'MOD_I2C_SDA', 30: 'MOD_I2C_SCL', 32: 'KEY'}
    require(all(indexed.get(k, {}).get('signal') == v for k, v in required.items()), 'new_signal_map')
    changed = set(c['reassigned_previous_nc'])
    require(changed == {25, 27, 28, 29, 30}, 'nc_reassignment')
    for previous in old_connector['pins']:
        n = previous['pin']
        if n in changed:
            require(previous['base_net'] is None and previous['module_net'] is None, 'previous_nc')
        else:
            fields = ['signal', 'kind', 'direction', 'voltage_v', 'base_gpio_proposed', 'module_gpio_proposed']
            require(all(indexed.get(n, {}).get(k) == previous.get(k) for k in fields), 'used_pin_changed')
    require(all(x['voltage_v'] == 3.3 for x in pins if x['kind'] == 'digital'), 'digital_3v3')
    require(all(indexed.get(n, {}).get('direction') == 'module_to_base'
                and indexed[n]['kind'] == 'analog' for n in (27, 28)), 'analog_direction')
    require(indexed[25]['direction'] == 'base_to_module' and indexed[25]['kind'] == 'power', 'aux_direction')
    require(not c['hot_plug'] and not a['hot_plug'] and a['slots'] == 1, 'one_slot_cold_swap')
    require(not a['module_mcu_required'] and not a['module_adc_required'] and not a['module_eeprom_required'], 'minimal_modules')
    require(a['selection'] == 'manual_while_stopped', 'selection')
    require(not any(c.get(k) for k in ('firmware_applied', 'schematic_applied', 'gpio_adopted')), 'not_implemented')

    power = a['power']
    require(power['common_ground'] and power['source'] == 'base external 5V'
            and not power['external_module_power'], 'power_source')
    require(not power['module_regulator_outputs_connected_to_aux'], 'no_backfeed')
    require(power['aux_source'] == 'base_auxiliary_ldo_not_pga_onboard_3v3'
            and power['module_aux_3v3_budget_ma'] <= 100, 'aux_budget')
    require(power['module_5v_budget_ma'] <= 500 and not power['capacity_recalculated_for_e'], 'power_budget_pending')

    audio = a['audio']
    adc, i2s = audio['adc'], audio['i2s']
    require(adc['location'] == 'base' and adc['quantity'] == 1 and adc['channels'] == 2, 'common_adc')
    require(adc['input_coupling'] == 'AC_on_base' and adc['design_max_input_vrms_at_0db'] <= 2.0
            and adc['nominal_input_vrms'] <= adc['design_max_input_vrms_at_0db'], 'analog_level')
    require(adc['clock'] == 'BCK_PLL_slave' and adc['address_7bit'] == 0b1001010
            and adc['ad_pin'] == 0, 'adc_clock_address')
    require(not adc['power_cycle_on_stop'] and a['stop']['continuous_adc_while_stopped'], 'adc_stop')
    require(i2s['optional'] and i2s['clock_master'] == 'base'
            and not i2s['asynchronous_module_master_supported'], 'i2s_master')
    require(i2s['channels'] == 2 and i2s['sample_hz'] == 48000 and i2s['slot_bits'] == 32
            and i2s['valid_bits'] == 24
            and i2s['bck_hz'] == i2s['sample_hz'] * i2s['channels'] * i2s['slot_bits'], 'i2s_frame')
    require(audio['mono'] == 'L_to_both_in_base_R_unused', 'mono_route')
    require(not audio['analog_bypass_final_mute'] and set(audio['final_mute_covers']) == {'adc', 'module_i2s'}, 'final_mute')
    mix = audio['hybrid']
    require(0 <= mix['initial_analog_gain'] <= 1 and 0 <= mix['initial_digital_gain'] <= 1
            and mix['initial_analog_gain'] + mix['initial_digital_gain'] <= 1
            and mix['duplicate_sources_forbidden'], 'mix_headroom')

    require(g['approval_required_before_implementation'] and not g['firmware_applied'] and not g['schematic_applied'], 'gpio_approval')
    require(g['preserved_base'] == old_gpio['base'], 'approved_gpio_changed')
    additions = g['additions']
    require(len(additions) == 1 and additions[0]['gpio'] == 5 and additions[0]['net'] == 'BASE_ADC_DOUT', 'adc_gpio')
    added = {x['gpio'] for x in additions}
    used = {x['gpio'] for x in old_gpio['base']}
    require(added.isdisjoint(used) and added <= set(old_gpio['base_free_gpio']), 'gpio_conflict')
    require(g['base_assigned_proposed'] == len(used | added)
            and set(g['base_free_gpio_proposed']) == set(old_gpio['base_free_gpio']) - added, 'gpio_budget')
    require(g['host_i2c'] == {'controller': 0, 'sda': 20, 'scl': 21, 'address': 66, 'hz': 100000}, 'host_i2c')
    require(g['service_i2c'] == {'controller': 1, 'sda': 42, 'scl': 43, 'hz': 100000}, 'service_i2c')
    require((indexed[29]['base_gpio_proposed'], indexed[30]['base_gpio_proposed']) == (42, 43), 'service_connector_gpio')
    require(g['audio_data'] == {'dac_tx': 26, 'module_rx': 16, 'adc_rx_candidate': 5}
            and i2s['module_data_gpio'] == 16 and i2s['adc_data_gpio_candidate'] == 5
            and i2s['shared_bck_gpio'] == 27 and i2s['shared_lrck_gpio'] == 28, 'audio_gpio')
    control = a['control']
    reserved = list(control['service_reserved_addresses'].values())
    require(set(reserved) == {32, 74, 96} and len(reserved) == 3, 'service_addresses')
    require(not control['i2c_mux_required'] and control['service_pullups'] == 'base_only_3v3', 'simple_i2c')
    require(control['transaction_timeout_ms_candidate'] <= 5
            and not control['blind_i2c_scan_during_play'], 'bounded_i2c')
    require(control['jumpers_open'] == 'disable_all_service_dependent_playback_stay_muted', 'service_jumpers')

    ids = [x['id'] for x in p['profiles']]
    require(len(ids) == len(set(ids)) and set(ids) == {
        'opn1_hybrid', 'ay_psg', 'sn_psg', 'speech_atp3012', 'radio_si4732',
        'sn76477_presets', 'native_i2s_slave'}, 'profiles')
    for profile in p['profiles']:
        analog, digital = set(profile['analog_sources']), set(profile['digital_sources'])
        require(not analog.intersection(digital), 'duplicate_source')
        mode = profile['audio_mode']
        require(mode in audio['modes'] and bool(analog) == (mode != 'digital_stereo')
                and bool(digital) == (mode in ('hybrid', 'digital_stereo')), 'profile_routes')
        require(not profile['module_adc'], 'module_adc_not_required')
        require(not digital or (profile['i2s_clock_master'] == 'base' and profile['i2s_sample_hz'] == 48000), 'profile_sync')
        addresses = profile['i2c_addresses_7bit']
        require(len(addresses) == len(set(addresses)) and all(8 <= v <= 0x77 and v not in reserved for v in addresses), 'module_address_collision')
        require(not profile['legacy_wym1'] or profile['id'] == 'opn1_hybrid', 'false_legacy_identity')
    opn = next((v for v in p['profiles'] if v['id'] == 'opn1_hybrid'), {})
    require(opn.get('analog_sources') == ['SSG'] and opn.get('digital_sources') == ['FM']
            and opn.get('legacy_wym1'), 'opn_routes')

    stop = a['stop']
    require(stop['first_action'] == 'close_final_gates_without_bus_transaction'
            and stop['physical_default_gates'] == 'closed', 'stop_order')
    require(stop['next'] == ['invalidate_generation', 'flush_event_and_pcm_queues', 'MOD_ENABLE_low', 'bounded_device_cleanup'], 'stop_flush')
    require(not stop['readback_renews_lease'] and not stop['audio_activity_renews_lease'], 'lease_readback')
    require(stop['resume'] == 'explicit_new_play_or_note_only_after_initialize_and_prime', 'explicit_resume')
    require(not stop['independent_external_watchdog_required'], 'prototype_scope')
    require(stop['owner_policy'] == {
        'midi_owned_begin': 'reject_keep_midi', 'i2c_owned_midi': 'discard_no_replay',
        'midi_owned_usb_disconnect': 'global_stop_release_owner',
        'i2c_owned_usb_disconnect': 'continue_if_power_and_host_lease_present',
        'reattach_or_status': 'never_resume', 'STOP_any_owner': 'global_stop'}, 'ownership')

    legacy = a['legacy']
    require(legacy['signature'] in stream_source and legacy['signature'] == 'YM22S002'
            and legacy['clock_hz'] == 4000000, 'legacy_identity')
    defines = {k: int(v) for k, v in re.findall(r'#define\s+(REVC_\w+)\s+(\d+)u', header)}
    require(legacy['status_bytes'] == defines.get('REVC_STATUS_SIZE') == 64
            and legacy['fifo_events'] == defines.get('REVC_QUEUE_CAPACITY') == 1024
            and legacy['lease_ms'] * 1000 == defines.get('REVC_LEASE_US') == 1000000, 'legacy_c_constants')
    require(legacy['event_struct'] == '<IBB' and legacy['event_bytes'] == struct.calcsize(legacy['event_struct']) == 6
            and legacy['push_max_events'] * legacy['event_bytes'] == defines.get('REVC_PACKET_PAYLOAD') == 192, 'legacy_packets')
    require(not legacy['host_modified'] and not legacy['non_opn1_may_identify_as_legacy']
            and not legacy['p2_hardware_accepted'] and legacy['other_families_wire_format'] is None, 'legacy_scope')
    require(legacy['execution_ack'] == 'after_actual_chip_write_not_only_SPI_enqueue', 'execution_ack')
    return sorted(set(errors))


def references(hardware_root):
    firmware = hardware_root.parent.parent / 'firmware-c' / 'src'
    return (read(hardware_root / 'digital-module-review-c/connector.json'),
            read(hardware_root / 'digital-module-review-c/pins.json'),
            (firmware / 'stream.h').read_text(), (firmware / 'stream.c').read_text())


def verify_files(hardware_root):
    errors = validate(load(), *references(hardware_root))
    for item in read(HERE / 'preservation.json')['files']:
        target = hardware_root / item['path'].removeprefix('../')
        if hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
            errors.append('preservation:' + item['path'])
    expected = load()['gpio-proposal']['approved_manifest_sha256']
    if hashlib.sha256((hardware_root / 'digital-module-review-c/pins.json').read_bytes()).hexdigest() != expected:
        errors.append('approved_gpio_hash')
    with (HERE / 'connector.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    pins = load()['connector']['pins']
    if len(rows) != len(pins) or any(
        row[k] != ('' if p.get(k) is None else str(p[k]))
        for row, p in zip(rows, pins) for k in rows[0]
    ):
        errors.append('csv_mismatch')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hardware-root', type=Path, default=HERE.parent)
    args = parser.parse_args()
    errors = verify_files(args.hardware_root)
    if errors:
        raise SystemExit('FAIL: ' + ', '.join(errors))
    print('PASS: 32 contacts; 27 contacts preserved; GPIO/rails/routes/profiles/STOP/ownership and existing C wire constants checked')
    print('SCOPE: static contracts only; no new CAD, firmware, simulation or hardware acceptance')
