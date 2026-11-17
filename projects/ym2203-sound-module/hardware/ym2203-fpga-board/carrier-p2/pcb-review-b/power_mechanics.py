#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproducible design budgets, not physical measurements or guaranteed IC maxima."""
import json,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOADS=[
 ('PGA2350 module incl.RP2350B/flash/idle PSRAM','V3V3',180,'design allocation;150MHz firmware current must be measured'),
 ('Si5351A core + CLK0 only','V3V3',42,'35mA core(3 outputs enabled) +5.6mA/output;CLK1/2 disabled;rounded up'),
 ('MCP23017 logic','V3V3',3,'design allowance, not a measured maximum'),
 ('RX +6 voice LEDs','V3V3',14,'seven sinks <=2mA; all on together'),
 ('DIP +STOP/TEST pullups','V3V3',2.2,'six10k pullups simultaneously low including tolerance'),
 ('HOST +panel I2C pullups','V3V3',6.2,'four2.2k pullups simultaneously low including tolerance'),
 ('level shifters,FM buffer,GPIO pulls','V3V3',12,'switching and bias allowance, not per-pin drive maximum'),
 ('PCM5102A DVDD +AVDD/CPVDD','V3_AUX',45,'13+32mA datasheet limits at48kHz1kHz -1dBFS'),
 ('UNO3V3 shield load','V3_AUX',100,'USER LOAD LIMIT; excluded from PGA regulator'),
 ('AUX regulator IQ and reserve','V3_AUX',5,'includes regulator quiescent current and pulldown allowance'),
 ('YM2203C and5V-domain reserve','V5_CARRIER',150,'YM datasheet120mA max, rounded to150 for clock/bus reserve'),
 ('analog mixer,mute and reset bias','V5_CARRIER',15,'design allowance'),
 ('optional UNO5V shield','V5_CARRIER',100,'JP5V OPEN default; USER LOAD LIMIT when fitted')]

def evaluate():
 sums={r:sum(v[2] for v in LOADS if v[1]==r) for r in ['V3V3','V3_AUX','V5_CARRIER']}
 # Both3V3 rails use linear regulators. Add currents directly to5V budget.
 input_ma=sum(sums.values());module_w=(5.25-3.2)*sums['V3V3']/1000;aux_w=(5.25-3.2)*sums['V3_AUX']/1000
 d=dict(schema_version=1,scope='datasheet and dimensional review; NO bench measurements',loads=[dict(load=a,rail=b,budget_ma=c,basis=e) for a,b,c,e in LOADS],totals_ma=sums,input_5v_budget_ma=round(input_ma,1),adapter_target_ma=1500,module_regulator_rating_ma=300,module_spare_ma=round(300-sums['V3V3'],1),aux_regulator_rating_ma=500,aux_spare_ma=500-sums['V3_AUX'],thermal=dict(ambient_design_c=30,vin_stress_v=5.25,vout_stress_v=3.2,module_ldo='AP7366EA-33SN-7 / U-DFN2020-6; confirm purchased module revision',module_dissipation_w=round(module_w,4),module_reference_theta_ja_c_per_w=46.2,module_reference_tj_c=round(30+module_w*46.2,1),module_sensitivity_theta_c_per_w=139,module_sensitivity_tj_c=round(30+module_w*139,1),aux_ldo='TLV75533PDBVR / DBV SOT-23-5',aux_dissipation_w=round(aux_w,4),aux_reference_theta_ja_c_per_w=231.1,aux_reference_tj_c=round(30+aux_w*231.1,1),qualification='JEDEC thermal values do not describe the25.4mm PGA2350 module or final PCB; sensitivity calculation is not a guaranteed bound'),hardware_accepted=False)
 assert sums['V3V3']<300 and sums['V3_AUX']<500 and input_ma<750
 assert d['thermal']['aux_reference_tj_c']<125 and d['thermal']['module_sensitivity_tj_c']<125
 return d

def mechanical():
 # Supplier dimensional facts; nominal stack depends on selected male pins and jig.
 flange_max=(.078+.002)*25.4;pitch_min=2.54-.10
 return dict(schema_version=1,scope='2D CAD/body envelopes plus conditional Z stack; no fitted sample',module=dict(model='Pimoroni PGA2350 PIM722',size_mm=[25.4,25.4,3.6],socket='64 x Mill-Max0300-2-15-15-47-27-10-0 individual solder receptacles',pin_acceptance='0.64mm square',recommended_finished_hole_mm=1.2,pcb_pad_diameter_mm=2.05,socket_flange_max_diameter_mm=round(flange_max,4),nominal_pitch_mm=2.54,min_pitch_assumption_mm=pitch_min,min_flange_to_flange_gap_mm=round(pitch_min-flange_max,4),socket_nominal_height_above_pcb_mm=5.33,assembly_jig_module_bottom_mm=9.5,module_bottom_component_allowance_mm=3.6,conditional_under_module_clearance_mm=5.9,nominal_assembly_top_envelope_mm=13.1,male_pin_engagement='Use approximately6mm free mating length and2.54mm insulator, verify3.5..4.5mm engagement; DO NOT force to socket bottom',restriction='No hot insertion; assemble64 terminals with alignment jig; check contact height and retention on a sample before ordering PCB'),rejected_strip_socket=dict(model='Harwin M20-7830842',body_length_mm=20.72,body_width_mm=5.04,height_mm=8.5,grid_segment_span_mm=20.32,reason='four2x8 strips overlap around corners; not interchangeable without machining'),uno=dict(header_family='SamtecSSW single-row;8/10/6/8 positions,3V3-only',header_nominal_height_mm=8.51,icsp_header='2x03 MALE2.54mm; target2.54mm insulator+6mm free mating pins; verify shield mating',maximum_shield_underhang_target_mm=5,minimum_clearance_to_empty_carrier_mm=3.51,standoffs='H1,H2,H4 support shield; H3 left-top hole has NO FASTENER because of header end proximity',mounting_hole_positions_unchanged=True,qualification='Arbitrary shield overhang, underside components and connector bodies remain shield-specific'),hardware_accepted=False)

class BudgetTests(unittest.TestCase):
 def test_rails_and_thermal(self):evaluate()
 def test_socket_spacing(self):self.assertGreater(mechanical()['module']['min_flange_to_flange_gap_mm'],.3)
 def test_four_strip_rejected(self):d=mechanical()['rejected_strip_socket'];self.assertGreater(d['body_length_mm'],d['grid_segment_span_mm'])
 def test_shield_and_module_z(self):d=mechanical();self.assertGreater(d['module']['conditional_under_module_clearance_mm'],3);self.assertGreater(d['uno']['minimum_clearance_to_empty_carrier_mm'],3)
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=HERE/'schematic');v=a.parse_args();v.output.mkdir(parents=True,exist_ok=True)
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BudgetTests));assert r.wasSuccessful()
 (v.output/'power-budget.json').write_text(json.dumps(evaluate(),indent=2)+'\n');(v.output/'mechanical-review.json').write_text(json.dumps(mechanical(),indent=2)+'\n')
 print('PASS calculated power budgets and conditional mechanical envelope; not bench acceptance')
