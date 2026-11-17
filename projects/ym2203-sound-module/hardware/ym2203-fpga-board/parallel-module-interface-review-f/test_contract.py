# SPDX-License-Identifier: MIT
"""Static constraints and PC-only protocol waveforms, never hardware acceptance."""
import copy
import os
import unittest
from pathlib import Path

from bus_model import encode_byte, sn_minimum_us, sn_write_complete, validate_ay_trace, validate_read_turnaround
from verify import HERE, load, references, validate


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.ref = references(Path(os.environ.get('P2_REFERENCE_HARDWARE', HERE.parent)))

    def reject(self, mutation, code):
        d = copy.deepcopy(self.data)
        mutation(d)
        self.assertIn(code, validate(d, self.ref))

    def test_specification_valid(self):
        self.assertEqual(validate(self.data, self.ref), [])

    def test_only_39_positions(self):
        self.reject(lambda d: d['connector']['pins'].pop(), '40_positions')

    def test_mirrored_connector(self):
        self.reject(lambda d: d['connector']['pins'][32].update(column='B'), 'orientation')

    def test_old32_partial_mating(self):
        self.reject(lambda d: d['connector'].update(old32_mating_approved=True), 'mating')

    def test_5V_on_connector_data(self):
        self.reject(lambda d: d['connector']['pins'][32].update(voltage_v=5), '3v3_connector')

    def test_SPI_mode_MISO_direction_preserved(self):
        self.reject(lambda d: d['connector']['pins'][7].update(direction='base_to_module'), 'E_spi_pin_preservation')

    def test_SPI_parallel_simultaneous(self):
        self.reject(lambda d: d['architecture']['control'].update(spi_parallel_simultaneous=True), 'bus_exclusion')

    def test_parallel_disables_ADC_clock_control_bus(self):
        self.reject(lambda d: d['architecture']['control'].update(service_i2c_remains_available_in_parallel=False), 'bus_exclusion')

    def test_live_bus_switch(self):
        self.reject(lambda d: d['architecture']['control'].update(switch_only='any_time'), 'mode_selection')

    def test_mode_switch_without_high_Z(self):
        self.reject(lambda d: d['architecture']['control']['mode_switch_sequence'].remove('all_shared_data_and_aux_high_impedance'), 'mode_switch_order')

    def test_GPIO_steals_UNO(self):
        self.reject(lambda d: d['gpio-proposal']['additions'][-1].update(gpio=8), 'gpio_conflict')

    def test_duplicate_GPIO(self):
        self.reject(lambda d: d['gpio-proposal']['additions'][-1].update(gpio=17), 'gpio_additions')

    def test_unapproved_GPIO_adoption(self):
        self.reject(lambda d: d['gpio-proposal'].update(schematic_applied=True), 'approval_pending')

    def test_noncontiguous_single_PIO_claim(self):
        self.reject(lambda d: d['gpio-proposal'].update(single_pio_8bit_out_claimed=True), 'SIO_strobe_contract')

    def test_level_translation_removed(self):
        self.reject(lambda d: d['architecture']['control']['parallel'].update(five_volt_translation_removed=True), 'parallel_simplification')

    def test_data_changes_while_strobe_active(self):
        self.reject(lambda d: d['architecture']['control']['parallel'].update(data_may_update_while_strobe_active=True), 'SIO_strobe_contract')

    def test_ADC_path_removed(self):
        self.reject(lambda d: d['architecture']['audio']['adc'].update(location='module'), 'audio_preservation')

    def test_HOST_service_bus_short(self):
        self.reject(lambda d: d['gpio-proposal']['service_i2c'].update(sda=20, scl=21), 'i2c_preservation')

    def test_legacy_executed_means_only_SPI_enqueue(self):
        self.reject(lambda d: d['architecture']['legacy'].update(execution_ack='SPI_queue'), 'legacy_preservation')

    def test_MIDI_replayed_after_I2C(self):
        self.reject(lambda d: d['architecture']['stop']['owner_policy'].update(i2c_owned_midi='deferred'), 'stop_ownership_preservation')

    def test_status_extends_lease(self):
        self.reject(lambda d: d['architecture']['stop'].update(readback_renews_lease=True), 'stop_ownership_preservation')

    def test_STOP_waits_for_READY(self):
        self.reject(lambda d: d['architecture']['stop'].update(parallel_cleanup='wait READY before mute'), 'parallel_stop')

    def test_SN_data_named_D0_mistaken_for_LSB(self):
        self.reject(lambda d: d['profiles']['profiles'][2].update(logical_bit_to_ic_data=['D'+str(i) for i in range(8)]), 'SN_MSB_mapping')

    def test_SN_READY_is_driven_as_RD(self):
        self.reject(lambda d: d['profiles']['profiles'][2]['control_roles'].update(CTL3='RD_N_output'), 'SN_ready_pin')

    def test_PSG_requires_extra_bridge_MCU(self):
        self.reject(lambda d: d['profiles']['profiles'][1].update(module_mcu='Core2350B0'), 'direct_psg_no_bridge')

    def test_PSG_claims_YM_identity(self):
        self.reject(lambda d: d['profiles']['profiles'][1].update(legacy_wym1=True), 'profile_identity')

    def test_opn_decoder_removed(self):
        self.reject(lambda d: d['profiles']['profiles'][0].update(module_mcu=None), 'opn_bridge_retained')

    def test_card_I2C_collides_with_ADC(self):
        self.reject(lambda d: d['profiles']['profiles'][3].update(i2c_addresses_7bit=[74]), 'i2c_collision')

    def test_AY_20us_write_candidate(self):
        self.reject(lambda d: d['bus-timing']['ay38910']['candidate_ns'].update(write_pulse=20000), 'AY_timing')

    def test_AY_read_state_used_for_address(self):
        self.reject(lambda d: d['bus-timing']['ay38910'].update(address_bdir_bc2_bc1=[0,1,1]), 'AY_no_read')

    def test_old_READY_high_accepted(self):
        self.reject(lambda d: d['bus-timing']['sn76489an'].update(ready_high_before_minimum_delay_sufficient=True), 'SN_timing')

    def test_fake_hardware_timing_acceptance(self):
        self.reject(lambda d: d['architecture']['control']['parallel'].update(timing_guaranteed_on_hardware=True), 'timing_not_bench')


class BusModelTests(unittest.TestCase):
    def setUp(self):
        self.spec = load()
        self.gpios = self.spec['gpio-proposal']['parallel_data_gpio_lsb_first']
        self.limits = self.spec['bus-timing']['ay38910']['datasheet_ns']

    @staticmethod
    def ay_trace(address=7, value=0x80):
        return [(0,address,0,0,0), (1000,address,1,0,0), (3000,address,0,0,0),
                (4000,value,0,0,0), (5000,value,0,1,0), (6000,value,1,1,0),
                (8000,value,0,1,0), (9000,value,0,0,0)]

    def test_all_256_bytes_across_two_SIO_banks(self):
        for value in range(256):
            lo_mask, lo, hi_mask, hi = encode_byte(value, self.gpios)
            self.assertEqual((lo_mask, hi_mask), (0xc000000f, 3))
            expected = (value & 15) | ((value & 0x30) << 26) | ((value & 0xc0) << 26)
            self.assertEqual(lo | (hi<<32), expected)
            # Unrelated GPIO state survives masked updates.
            initial = 0x555555555555
            mask = lo_mask | (hi_mask<<32)
            changed = (initial & ~mask) | lo | (hi<<32)
            self.assertEqual(changed & ~mask, initial & ~mask)

    def test_significance_example_81(self):
        self.assertEqual(encode_byte(0x81, self.gpios), (0xc000000f,1,3,2))

    def test_mapping_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError,'invalid_data_mapping'):
            encode_byte(1,[0]*8)

    def test_SN_physical_bus_decodes_original_256_bytes(self):
        pins = self.spec['profiles']['profiles'][2]['logical_bit_to_ic_pin']
        # Physical IC pin numbers in MSB-to-LSB order from TI pin table.
        ic_msb_order = [3,2,1,15,13,12,11,10]
        for value in range(256):
            levels = {pin:(value>>bit)&1 for bit,pin in enumerate(pins)}
            reconstructed = sum(levels[pin]<<(7-i) for i,pin in enumerate(ic_msb_order))
            self.assertEqual(value,reconstructed)

    def test_AY_all_16_addresses_and_256_data_values(self):
        for addr in range(16):
            for value in range(256):
                self.assertEqual(validate_ay_trace(self.ay_trace(addr,value),self.limits),['address','write'])

    def test_AY_strobe_data_glitch_rejected(self):
        t=self.ay_trace();t.insert(2,(2000,1,1,0,0))
        with self.assertRaisesRegex(ValueError,'data_changed_during_strobe'):
            validate_ay_trace(t,self.limits)

    def test_AY_setup_short(self):
        t=self.ay_trace();t[1]=(399,7,1,0,0)
        with self.assertRaisesRegex(ValueError,'setup_time'):
            validate_ay_trace(t,self.limits)

    def test_AY_hold_short(self):
        t=self.ay_trace();t[3]=(3050,0x80,0,0,0)
        with self.assertRaisesRegex(ValueError,'hold_time'):
            validate_ay_trace(t,self.limits)

    def test_AY_write_pulse_short(self):
        t=self.ay_trace();t[6]=(6200,0x80,0,1,0)
        with self.assertRaisesRegex(ValueError,'write_pulse_short'):
            validate_ay_trace(t,self.limits)

    def test_AY_IRQ_stretches_pulse_past_10us(self):
        t=self.ay_trace();t[6]=(17001,0x80,0,1,0);t[7]=(18000,0x80,0,0,0)
        with self.assertRaisesRegex(ValueError,'write_pulse_long'):
            validate_ay_trace(t,self.limits)

    def test_AY_BC1_read_risk_rejected(self):
        t=self.ay_trace();t[4]=(5000,0x80,0,1,1)
        with self.assertRaisesRegex(ValueError,'BC1_must_stay_low'):
            validate_ay_trace(t,self.limits)

    def test_AY_BC2_changes_at_rising_strobe(self):
        t=self.ay_trace();t[4]=(5000,0x80,0,0,0)
        with self.assertRaisesRegex(ValueError,'BC2_changed_at_strobe_edge'):
            validate_ay_trace(t,self.limits)

    def test_SN_minimum_recomputed_for_clock(self):
        self.assertEqual(sn_minimum_us(3579545),11)
        self.assertEqual(sn_minimum_us(2000000),18)

    def test_SN_stale_READY_high_does_not_complete(self):
        self.assertFalse(sn_write_complete(3579545,1,True))
        self.assertTrue(sn_write_complete(3579545,11,True))

    def test_SN_low_READY_and_timeout(self):
        self.assertFalse(sn_write_complete(3579545,99,False))
        with self.assertRaisesRegex(ValueError,'ready_timeout'):
            sn_write_complete(3579545,101,False)

    def test_SN_missing_clock(self):
        with self.assertRaisesRegex(ValueError,'clock_missing'):
            sn_write_complete(0,11,True)

    def test_generic_read_turnaround(self):
        validate_read_turnaround([(0,1,1,1,True),(1000,1,1,1,False),
                                  (2000,1,0,1,False),(3000,0,0,1,False),
                                  (4000,1,0,1,False),(5000,1,1,1,False),
                                  (6000,1,1,1,True)])

    def test_generic_read_base_does_not_release(self):
        with self.assertRaisesRegex(ValueError,'read_bus_contention'):
            validate_read_turnaround([(0,1,0,1,True),(1000,0,0,1,True)])

    def test_generic_DIR_changes_with_OE_enabled(self):
        with self.assertRaisesRegex(ValueError,'DIR_changed_while_enabled'):
            validate_read_turnaround([(0,0,1,1,False),(1000,0,0,1,False)])

    def test_generic_read_and_write_together(self):
        with self.assertRaisesRegex(ValueError,'read_and_write_together'):
            validate_read_turnaround([(0,0,0,0,False)])


if __name__ == '__main__':
    unittest.main()
