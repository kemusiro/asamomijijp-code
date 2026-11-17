# SPDX-License-Identifier: MIT
"""Reject hazardous or falsely compatible revisions of the connector proposal."""
import copy
import os
import unittest
from pathlib import Path

from verify import HERE, load, references, validate


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.ref = references(Path(os.environ.get('P2_REFERENCE_HARDWARE', HERE.parent)))

    def reject(self, change, code):
        data = copy.deepcopy(self.data)
        change(data)
        self.assertIn(code, validate(data, *self.ref))

    def test_valid_proposal(self):
        self.assertEqual([], validate(self.data, *self.ref))

    def test_duplicate_contact(self):
        self.reject(lambda d: d['connector']['pins'].__setitem__(0, d['connector']['pins'][1]), 'pin_count')

    def test_existing_spi_changed(self):
        self.reject(lambda d: d['connector']['pins'][4].update(direction='module_to_base'), 'used_pin_changed')

    def test_mirrored_pin_numbering(self):
        self.reject(lambda d: d['connector']['pins'][26].update(column='B'), 'pin_orientation')

    def test_five_volt_digital(self):
        self.reject(lambda d: d['connector']['pins'][28].update(voltage_v=5), 'digital_3v3')

    def test_aux_backfeed(self):
        self.reject(lambda d: d['architecture']['power'].update(module_regulator_outputs_connected_to_aux=True), 'no_backfeed')

    def test_aux_on_pga_rail(self):
        self.reject(lambda d: d['architecture']['power'].update(aux_source='pga_onboard_3v3'), 'aux_budget')

    def test_independent_power(self):
        self.reject(lambda d: d['architecture']['power'].update(external_module_power=True), 'power_source')

    def test_adc_for_every_card(self):
        self.reject(lambda d: d['architecture']['audio']['adc'].update(location='module'), 'common_adc')

    def test_analog_bypasses_stop(self):
        self.reject(lambda d: d['architecture']['audio'].update(analog_bypass_final_mute=True), 'final_mute')

    def test_adc_power_cycle_stop(self):
        self.reject(lambda d: d['architecture']['audio']['adc'].update(power_cycle_on_stop=True), 'adc_stop')

    def test_async_i2s(self):
        self.reject(lambda d: d['architecture']['audio']['i2s'].update(clock_master='module'), 'i2s_master')

    def test_inconsistent_bck(self):
        self.reject(lambda d: d['architecture']['audio']['i2s'].update(bck_hz=1536000), 'i2s_frame')

    def test_duplicate_ssg(self):
        self.reject(lambda d: d['profiles']['profiles'][0]['digital_sources'].append('SSG'), 'duplicate_source')

    def test_mix_clipping_headroom(self):
        self.reject(lambda d: d['architecture']['audio']['hybrid'].update(initial_analog_gain=1, initial_digital_gain=1), 'mix_headroom')

    def test_adc_gpio_steals_uno(self):
        self.reject(lambda d: d['gpio-proposal']['additions'][0].update(gpio=8), 'gpio_conflict')

    def test_service_bus_steals_host(self):
        self.reject(lambda d: d['gpio-proposal']['service_i2c'].update(controller=0, sda=20, scl=21), 'service_i2c')

    def test_module_collides_with_adc(self):
        self.reject(lambda d: d['profiles']['profiles'][3].update(i2c_addresses_7bit=[74]), 'module_address_collision')

    def test_duplicate_module_addresses(self):
        self.reject(lambda d: d['profiles']['profiles'][3].update(i2c_addresses_7bit=[46, 46]), 'module_address_collision')

    def test_reserved_module_address(self):
        self.reject(lambda d: d['profiles']['profiles'][3].update(i2c_addresses_7bit=[0]), 'module_address_collision')

    def test_profile_i2s_44100(self):
        self.reject(lambda d: d['profiles']['profiles'][0].update(i2s_sample_hz=44100), 'profile_sync')

    def test_radio_claims_legacy(self):
        self.reject(lambda d: d['profiles']['profiles'][4].update(legacy_wym1=True), 'false_legacy_identity')

    def test_stop_waits_for_i2c(self):
        self.reject(lambda d: d['architecture']['stop'].update(first_action='wait_i2c_mute'), 'stop_order')

    def test_stop_leaves_pcm(self):
        self.reject(lambda d: d['architecture']['stop']['next'].remove('flush_event_and_pcm_queues'), 'stop_flush')

    def test_status_renews_lease(self):
        self.reject(lambda d: d['architecture']['stop'].update(readback_renews_lease=True), 'lease_readback')

    def test_reattach_replays_midi(self):
        self.reject(lambda d: d['architecture']['stop']['owner_policy'].update(i2c_owned_midi='queue_for_later'), 'ownership')

    def test_usb_disconnect_stops_i2c(self):
        self.reject(lambda d: d['architecture']['stop']['owner_policy'].update(i2c_owned_usb_disconnect='stop'), 'ownership')

    def test_spi_enqueue_is_executed(self):
        self.reject(lambda d: d['architecture']['legacy'].update(execution_ack='after_SPI_enqueue'), 'execution_ack')

    def test_host_wire_size_changed(self):
        self.reject(lambda d: d['architecture']['legacy'].update(status_bytes=80), 'legacy_c_constants')

    def test_push_size_changed(self):
        self.reject(lambda d: d['architecture']['legacy'].update(push_max_events=64), 'legacy_packets')

    def test_gpio_falsely_applied(self):
        self.reject(lambda d: d['gpio-proposal'].update(schematic_applied=True), 'gpio_approval')

    def test_unknown_jumpers_ignored(self):
        self.reject(lambda d: d['architecture']['control'].update(jumpers_open='continue'), 'service_jumpers')


if __name__ == '__main__':
    unittest.main()
