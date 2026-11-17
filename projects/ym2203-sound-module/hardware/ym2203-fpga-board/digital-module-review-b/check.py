#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Review manifest checks and budget arithmetic; no runtime, ERC or bench claims."""
import argparse
import hashlib
import json
import math
import re
import struct
import sys
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PROJECT = Path('projects/ym2203-sound-module')
BOARD = PROJECT / 'hardware/ym2203-fpga-board'


def read(name):
    return json.loads((HERE / name).read_text())


def bundle():
    return {k: read(k + '.json') for k in ('connector', 'clock-tree', 'adc-plan',
            'power-plan', 'resources', 'gpio-proposal', 'module-header')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evaluate(d):
    c, clock, adc, power, res, gpio, headers = (d[k] for k in (
        'connector', 'clock-tree', 'adc-plan', 'power-plan', 'resources',
        'gpio-proposal', 'module-header'))
    pins = c['pins']
    require(c['positions'] == 32 and sorted(p['pin'] for p in pins) == list(range(1, 33)), '32 distinct contacts')
    require(c['rows'] == 16 and c['pitch_mm'] == 2.54 and c['contact_grid_length_mm'] == 38.1, 'connector grid')
    signals = Counter(p['signal'] for p in pins)
    require(signals['GND'] == 12 and signals['V5_MODULE'] == 2, 'power and return contacts')
    require(all(n == 1 for s, n in signals.items() if s not in ('GND', 'V5_MODULE')), 'duplicate signal')
    expected = {5:'MOD_SPI_SCK',7:'MOD_SPI_MOSI',8:'MOD_SPI_MISO',9:'MOD_SPI_CS_N',
                11:'MOD_ENABLE',12:'MOD_ALERT_N',13:'MOD_I2S_BCK',15:'MOD_I2S_LRCK',
                17:'MOD_I2S_DATA',19:'SOUND_CLK0',21:'SOUND_CLK1',23:'SOUND_CLK2'}
    for pin, signal in expected.items():
        p = pins[pin - 1]
        require(p['signal'] == signal and p['kind'] == 'digital' and p['voltage_v'] == 3.3, 'digital identity/level')
        direction = 'module_to_base' if signal in ('MOD_SPI_MISO','MOD_ALERT_N','MOD_I2S_DATA') else 'base_to_module'
        require(p['direction'] == direction, 'driver direction')
    require(pins[31]['signal'] == 'KEY' and pins[31]['kind'] == 'key' and pins[31]['voltage_v'] is None, 'key must not conduct')
    require(all(not p['opn1_use'] for p in pins if p['kind'] in ('reserved','key') or p['signal'] in ('SOUND_CLK1','SOUND_CLK2')), 'reserved contacts must stay unused')
    require(not c['power_3v3_crosses'] and not c['hot_plug'], 'power isolation/no hotplug')
    require(not c['legacy60_compatible'], 'old connector incompatible')
    require(clock['sample_rate_hz'] == 48000 and clock['channels'] == 2 and clock['slot_bits'] == 32 and clock['payload_bits'] == 24, 'audio format')
    require(clock['bck_hz'] == clock['sample_rate_hz'] * clock['channels'] * clock['slot_bits'], 'BCK ratio')
    require(clock['clock_master'] == 'base PGA2350 PIO' and clock['module_tx_mode'] == 'slave' and clock['module_adc_rx_mode'] == 'slave', 'one clock master')
    require('BCK-input slave PLL' in clock['adc_clock_mode'] and not clock['mclk_contact_used'], 'ADC BCK PLL/MCLK contract')
    require(adc['part'] == 'PCM1863DBT' and adc['adc_channels'] == 2 and adc['analog_input_pins'] == 8, 'ADC channels distinct from input pins')
    require([(p['ym_pin'],p['adc_pin']) for p in adc['analog_inputs']] == [(20,3),(19,1),(18,29)], 'SSG ADC mapping')
    require(adc['left_mux_field'] == 7 and adc['right_mux_field'] == 0 and not adc['automatic_gain_control'], 'ADC mix fields/AGC')
    require(adc['supply_rail'] == 'MODULE_ADC_3V3', 'ADC separate rail')
    require(not power['module_3v3_exported'] and not power['usb_vbus_power_connected'], 'no regulator/USB backfeed')
    require(power['common_ground'] and not power['galvanic_isolation'], 'common digital reference')
    totals = Counter()
    for load in power['loads']:
        require(load['budget_ma'] > 0, 'positive load')
        totals[load['rail']] += load['budget_ma']
    for regulator in power['regulators']:
        require(totals[regulator['rail']] < regulator['rating_ma'], 'regulator overload')
    module_total = sum(v for k,v in totals.items() if k.startswith('MODULE_'))
    whole = sum(totals.values())
    admitted = whole - module_total + power['module_5v_admission_limit_ma']
    require(module_total <= power['module_5v_admission_limit_ma'], 'module current budget')
    require(admitted < power['ptc_hold_40c_ma'] < power['supply_target_ma'], 'input budget / thermal derating')
    require(power['connector_power_rails'] == ['V5_MODULE','GND'], 'separate onboard regulators only')
    require(gpio['approval_required_before_implementation'] and not gpio['module_is_pga_pin_compatible'], 'GPIO approval and board identity')
    require(gpio['base_mcu'] == 'Pimoroni PGA2350 PIM722' and gpio['module_mcu'] == 'Waveshare Core2350B0', 'only one PGA2350')
    existing = json.loads((REPO / BOARD / 'carrier-p2/pins.json').read_text())['gpio']
    base = {p['gpio']:p for p in gpio['base']}
    protected = {8,9,10,11,12,13,14,15,19,20,21,22,23,24,25,26,27,28,29,38,39,40,41,42,43,44,45,46}
    for p in existing:
        if p['gpio'] in protected:
            require(all(base.get(p['gpio'],{}).get(k) == p.get(k) for k in ('gpio','module_pad','net','function','adc_channel','pwm')), 'UNO/HOST/DAC/gates/VBUS pin changed')
    for side, reserved, capacity in [('base',{47},47),('module',{39,47},46)]:
        entries = gpio[side]
        require(len({p['gpio'] for p in entries}) == len(entries), 'GPIO collision')
        require(not any(p['gpio'] in reserved or not 0 <= p['gpio'] <= 47 for p in entries), 'reserved GPIO')
        require(res[side]['native_gpio'] == len(entries) and res[side]['free_gpio'] == capacity-len(entries), 'GPIO allocation count')
        require(res[side]['pio_sm'] <= res[side]['pio_sm_limit'] and res[side]['dma_channels'] <= res[side]['dma_limit'], 'PIO/DMA allocation exceeded')
        ram = res[side].get('sram_budget_bytes',res[side].get('audio_and_event_sram_budget_bytes'))
        require(ram < res[side]['sram_bytes'], 'SRAM budget')
    for p in gpio['module']:
        header, number = p['module_pad'].split('.')
        require(headers['headers'][header][int(number)-1] == p['gpio'], 'Core2350B header pin mismatch')
    require(headers['headers']['P2'][14] == 'VBUS' and headers['headers']['P2'][15] == '3V3' and headers['headers']['P2'][10] == 'RUN', 'Core power/RUN identity')
    mux = (REPO / PROJECT / '.cache/pico-sdk-2.2.0/src/rp2350/hardware_regs/include/hardware/regs/io_bank0.h')
    if mux.is_file():
        text = mux.read_text()
        for side in ('base','module'):
            for p in gpio[side]:
                if p['function'].startswith(('spi','i2c')):
                    macro = 'IO_BANK0_GPIO%d_CTRL_FUNCSEL_VALUE_%s' % (p['gpio'],p['function'].upper())
                    require(macro in text, 'invalid hardware pin mux')
    pinfile = REPO / BOARD / 'carrier-p2/pins.json'
    require(hashlib.sha256(pinfile.read_bytes()).hexdigest() == gpio['legacy_manifest_sha256'], 'approved GPIO source modified')
    stream_h = (REPO / PROJECT / 'firmware-c/src/stream.h').read_text()
    stream_c = (REPO / PROJECT / 'firmware-c/src/stream.c').read_text()
    for key,val in [('REVC_QUEUE_CAPACITY',1024),('REVC_STATUS_SIZE',64),('REVC_LEASE_US',1000000),('REVC_PACKET_PAYLOAD',192)]:
        require(re.search(r'#define\s+'+key+r'\s+'+str(val)+r'u\b',stream_h), 'legacy protocol constant changed')
    require('S_PING,S_STOP,S_BEGIN,S_PUSH,S_PLAY,S_KEEP,S_SEAL' in stream_h and 'YM22S002' in stream_c and struct.calcsize('<IBB') == 6, 'public opcode/signature/format changed')
    f = adc['front_end']; ratio = f['divider_bottom_ohms']/(f['divider_top_ohms']+f['divider_bottom_ohms'])
    effective_load = 1/(1/f['load_ohms']+1/(f['divider_top_ohms']+f['divider_bottom_ohms']))
    require(990 <= effective_load <= 1010, 'SSG source follower DC loading')
    step = 5.25 * ratio
    require(1.5-step > 0 and 1.8+step < 5.0, 'ADC initial rail-step bound')
    resistor_tolerance = .01
    analog_gain = (47000*(1+resistor_tolerance))/(100000*(1-resistor_tolerance))
    analog_peak = 2.2 * math.sqrt(2) * analog_gain
    room = 4.75*.99/2-.30
    require(analog_peak < room, 'biased final gate headroom')
    batch_bits = (res['spi']['batch_header_crc_bytes'] + res['spi']['batch_max_events']*res['spi']['design_event_record_bytes'])*8
    return dict(scope='arithmetic allocations only, not runtime or bench',rail_totals_ma={k:round(v,1) for k,v in totals.items()},module_5v_total_ma=round(module_total,1),whole_5v_ma=round(whole,1),with_module_admission_limit_ma=round(admitted,1),ptc_drop_v_at_admitted_limit=round(admitted/1000*power['ptc_r1max_ohm'],6),ldo_stress_w={k:round(v/1000*(power['regulator_stress_vin']-power['regulator_stress_vout']),6) for k,v in totals.items() if k.endswith('3V3')},ssg_load_ohm=round(effective_load,3),ssg_divider_ratio=round(ratio,6),ssg_single_rail_step_bound_v=round(step,6),output_peak_bound_v=round(analog_peak,6),output_available_peak_v=round(room,6),spi_batch_wire_us=round(batch_bits/res['spi']['initial_hz']*1e6,3),pga2350_count=1)


class Contracts(unittest.TestCase):
    def setUp(self):
        self.d = bundle()
        evaluate(self.d)
    def reject(self, action):
        action(self.d)
        with self.assertRaises(ValueError): evaluate(self.d)
    def test_valid(self): evaluate(self.d)
    def test_duplicate_contact(self): self.reject(lambda d:d['connector']['pins'][7].update(pin=7))
    def test_signal_swap(self): self.reject(lambda d:d['connector']['pins'][7].update(signal='MOD_SPI_MOSI'))
    def test_i2s_wrong_direction(self): self.reject(lambda d:d['connector']['pins'][16].update(direction='base_to_module'))
    def test_clock_wrong_direction(self): self.reject(lambda d:d['connector']['pins'][12].update(direction='module_to_base'))
    def test_5v_signal(self): self.reject(lambda d:d['connector']['pins'][4].update(voltage_v=5))
    def test_ground_removed(self): self.reject(lambda d:d['connector']['pins'][1].update(signal='NC'))
    def test_key_power(self): self.reject(lambda d:d['connector']['pins'][31].update(voltage_v=5))
    def test_reserved_drive(self): self.reject(lambda d:d['connector']['pins'][24].update(opn1_use=True))
    def test_regulator_outputs_connected(self): self.reject(lambda d:d['connector'].update(power_3v3_crosses=True))
    def test_two_clock_masters(self): self.reject(lambda d:d['clock-tree'].update(module_tx_mode='master'))
    def test_bck_ratio(self): self.reject(lambda d:d['clock-tree'].update(bck_hz=6144000))
    def test_nonstandard_payload(self): self.reject(lambda d:d['clock-tree'].update(payload_bits=32))
    def test_adcs_not_input_pins(self): self.reject(lambda d:d['adc-plan'].update(adc_channels=8))
    def test_wrong_ssg_pin(self): self.reject(lambda d:d['adc-plan']['analog_inputs'][1].update(adc_pin=29))
    def test_mix_field_not_register_byte(self): self.reject(lambda d:d['adc-plan'].update(left_mux_field=0x47))
    def test_unwanted_agc(self): self.reject(lambda d:d['adc-plan'].update(automatic_gain_control=True))
    def test_adc_supply_wrong(self): self.reject(lambda d:d['adc-plan'].update(supply_rail='MODULE_MCU_3V3'))
    def test_usb_backfeed(self): self.reject(lambda d:d['power-plan'].update(usb_vbus_power_connected=True))
    def test_no_common_ground(self): self.reject(lambda d:d['power-plan'].update(common_ground=False))
    def test_ldo_overload(self): self.reject(lambda d:d['power-plan']['loads'][0].update(budget_ma=500))
    def test_module_power_limit(self): self.reject(lambda d:d['power-plan'].update(module_5v_admission_limit_ma=250))
    def test_ptc_temperature_budget(self): self.reject(lambda d:d['power-plan'].update(ptc_hold_40c_ma=1000))
    def test_second_pga_forbidden(self): self.reject(lambda d:d['gpio-proposal'].update(module_mcu='Pimoroni PGA2350 PIM722'))
    def test_pga_socket_not_compatible(self): self.reject(lambda d:d['gpio-proposal'].update(module_is_pga_pin_compatible=True))
    def test_core_header_pin(self): self.reject(lambda d:d['module-header']['headers']['P2'].__setitem__(14,'3V3'))
    def test_core_led_gpio_reserved(self): self.reject(lambda d:d['gpio-proposal']['module'][0].update(gpio=39))
    def test_uno_affected(self): self.reject(lambda d:next(p for p in d['gpio-proposal']['base'] if p['gpio']==8).update(net='MOD_CLK'))
    def test_host_affected(self): self.reject(lambda d:next(p for p in d['gpio-proposal']['base'] if p['gpio']==20).update(function='spi0_rx'))
    def test_gpio_collision(self): self.reject(lambda d:d['gpio-proposal']['module'][0].update(gpio=1))
    def test_unapproved_application(self): self.reject(lambda d:d['gpio-proposal'].update(approval_required_before_implementation=False))
    def test_dma_exhaustion(self): self.reject(lambda d:d['resources']['module'].update(dma_channels=17))
    def test_ssg_load(self): self.reject(lambda d:d['adc-plan']['front_end'].update(load_ohms=100))
    def test_adc_step(self): self.reject(lambda d:d['adc-plan']['front_end'].update(divider_top_ohms=0,load_ohms=1e9))


def main():
    global REPO
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo',type=Path,default=REPO)
    ap.add_argument('--output',type=Path,default=None)
    args = ap.parse_args(); REPO = args.repo
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful(): return 1
    report = dict(schema_version=1,date='2026-11-16',python=sys.version.split()[0],tests_passed=result.testsRun,scope='design-manifest contracts and negative tests; NOT executable firmware simulation or electrical verification',budget=evaluate(bundle()),gpio_applied=False,firmware_modified=False,new_schematic=False,erc_run=False,pcb_created=False,hardware_accepted=False,board_source='Core2350B manufacturer schematic; module-header.json identity checked by transcription and unique GPIO rules')
    if args.output:
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
