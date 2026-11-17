# SPDX-License-Identifier: MIT
"""Constraint and mapping tests for the new design, never bench acceptance."""
import copy
import os
import unittest
from pathlib import Path
from verify import HERE,load,references,validate


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load()
        cls.ref=references(Path(os.environ.get('P2_REFERENCE_HARDWARE',HERE.parent)))

    def reject(self,mutation,code):
        d=copy.deepcopy(self.data);mutation(d)
        self.assertIn(code,validate(d,self.ref))

    def test_clean_sheet_design_valid(self):
        self.assertEqual(validate(self.data,self.ref),[])

    def test_old_card_compatibility_not_implied(self):
        self.reject(lambda d:d['connector'].update(legacy_connector_compatible=True),'clean_sheet_scope')

    def test_old_key32_not_preserved(self):
        self.reject(lambda d:d['connector'].update(key_pin=32),'key6')

    def test_analog_guard_removed(self):
        self.reject(lambda d:d['connector']['pins'][34].update(signal='AUX',kind='digital',voltage_v=3.3),'analog_guard')

    def test_clock_ground_removed(self):
        self.reject(lambda d:d['connector']['pins'][25].update(kind='digital',signal='AUX',voltage_v=3.3),'clock_ground_pairs')

    def test_reversed_mating_view(self):
        self.reject(lambda d:d['connector']['pins'][0].update(column='B'),'mating_view')

    def test_connector_5V_logic_rejected(self):
        self.reject(lambda d:d['connector']['pins'][8].update(voltage_v=5),'digital_voltage')

    def test_F_distributed_data_map_rejected(self):
        self.reject(lambda d:d['gpio-proposal'].update(data_gpio_lsb_first=[0,1,2,3,30,31,32,33]),'contiguous_data')

    def test_GPIO_alias_collision(self):
        self.reject(lambda d:d['gpio-proposal']['base'][4].update(gpio=0),'gpio_uniqueness')

    def test_wrong_PGA_pad(self):
        self.reject(lambda d:d['gpio-proposal']['base'][5].update(module_pad='C3'),'vendor_pad_identity')

    def test_UNO_steals_parallel_pin(self):
        self.reject(lambda d:d['gpio-proposal']['uno']['gpio'].update(D3=4),'uno_bus_conflict')

    def test_UNO_wrong_UART_mux(self):
        self.reject(lambda d:d['gpio-proposal']['uno']['gpio'].update(D1=24),'sdk_mux')

    def test_UNO_wrong_SPI_mux(self):
        self.reject(lambda d:d['gpio-proposal']['uno']['gpio'].update(D13=25),'sdk_mux')

    def test_UNO_wrong_ADC_pin(self):
        self.reject(lambda d:d['gpio-proposal']['uno']['gpio'].update(A0=35),'uno_adc')

    def test_UNO_PWM_duplicate_channel(self):
        self.reject(lambda d:d['gpio-proposal']['uno']['pwm_channels'].update(D9='pwm_a_3'),'uno_pwm')

    def test_PIO_window16_loses_data0(self):
        self.reject(lambda d:d['gpio-proposal']['pio_budget']['parallel'].update(gpio_base=16),'pio_parallel_range')

    def test_OUT12_may_touch_control_unintentionally(self):
        self.reject(lambda d:d['gpio-proposal']['pio_budget']['parallel'].update(data_count=12),'pio_parallel_range')

    def test_SET_range_reaches_ENABLE(self):
        self.reject(lambda d:d['gpio-proposal']['pio_budget']['parallel'].update(set_base=9),'pio_parallel_range')

    def test_audio_sideset_not_adjacent(self):
        self.reject(lambda d:d['gpio-proposal']['pio_budget']['audio'].update(clock_sideset_base=16),'pio_audio_range')

    def test_audio_and_bus_same_PIO_instance(self):
        self.reject(lambda d:d['gpio-proposal']['pio_budget']['audio'].update(instance=0),'pio_resource_scope')

    def test_SPI_parallel_simultaneous(self):
        self.reject(lambda d:d['architecture']['control'].update(spi_parallel_simultaneous=True),'mode_exclusion')

    def test_SN_READY_cannot_be_output(self):
        self.reject(lambda d:d['architecture']['control']['profile_direction_masks']['sn76489an_parallel'].update(control_outputs=14),'profile_direction')

    def test_SPI_MISO_cannot_be_driven(self):
        self.reject(lambda d:d['architecture']['control']['profile_direction_masks']['spi'].update(data_outputs=15),'direction_contention')

    def test_PIO_waiting_inside_active_pulse_forbidden(self):
        self.reject(lambda d:d['bus-timing']['pio_candidate'].update(FIFO_underflow_must_stall_only_while_inactive=False),'pio_timing_candidate')

    def test_unbounded_READY_wait_forbidden(self):
        self.reject(lambda d:d['bus-timing']['pio_candidate'].update(READY_wait_must_be_bounded=False),'pio_timing_candidate')

    def test_DISABLE_SM_alone_not_sufficient_stop(self):
        self.reject(lambda d:d['architecture']['stop'].update(parallel_cleanup='disable PIO only'),'pio_stop_handover')

    def test_legacy_HOST_packet_size_preserved(self):
        self.reject(lambda d:d['architecture']['legacy'].update(status_bytes=80),'C_wire_constants')

    def test_usb_disconnect_must_not_stop_HOST_owner(self):
        self.reject(lambda d:d['architecture']['stop']['owner_policy'].update(i2c_owned_usb_disconnect='stop'),'stop_ownership_semantics')

    def test_status_read_cannot_resume_audio(self):
        self.reject(lambda d:d['architecture']['stop']['owner_policy'].update(reattach_or_status='resume'),'stop_ownership_semantics')

    def test_ADC_GPIO_old5_not_reused(self):
        self.reject(lambda d:d['gpio-proposal']['audio'].update(adc_rx=5),'audio_gpio')

    def test_level_translation_not_removed_by_repinning(self):
        self.reject(lambda d:d['architecture']['control']['parallel'].update(five_volt_translation_removed=True),'pio_feasibility_only')

    def test_PIO_not_claimed_hardware_accepted(self):
        self.reject(lambda d:d['gpio-proposal']['pio_budget'].update(hardware_timing_verified=True),'pio_resource_scope')

    def test_all_256_bytes_fit_one_low_GPIO_bank(self):
        gpios=self.data['gpio-proposal']['data_gpio_lsb_first']
        for value in range(256):
            physical=sum(((value>>bit)&1)<<gp for bit,gp in enumerate(gpios))
            self.assertEqual(physical,value)
            self.assertEqual(physical & ~0xff,0)

    def test_all_16_control_patterns_exclude_ENABLE_and_ALERT(self):
        for value in range(16):
            physical=value<<self.data['gpio-proposal']['pio_budget']['parallel']['set_base']
            self.assertEqual(physical & ((1<<12)|(1<<13)),0)

    def test_program_pin_sets_disjoint_and_in_same_window(self):
        data=set(range(8));ctl=set(self.data['gpio-proposal']['control_gpio'].values())
        self.assertFalse(data&ctl)
        self.assertTrue(data|ctl <= set(range(32)))
        self.assertFalse((data|ctl)&{12,13,14,15,16,17,18})


if __name__=='__main__':unittest.main()
