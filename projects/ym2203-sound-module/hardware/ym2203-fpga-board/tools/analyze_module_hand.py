#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recalculate M1 logical pin and Si5351 divider budgets; no board/RTL verification."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def require(ok,message):
    if not ok: raise ValueError(message)


def analyze():
    raw=(ROOT/'module-hand-soldered-plan.json').read_bytes()
    plan=json.loads(raw);cfg=plan['clock_plan'];module=plan['module']
    constraints=plan['user_constraints']
    require(constraints['real_ym2203'] and not constraints['fpga_ym_emulation_in_main_plan'],'Real YM must remain')
    require(constraints['fpga_mount']=='preassembled_module','Use an assembled FPGA module')
    require(constraints['fine_pitch_smd_hand_soldering_allowed'],'Fine-pitch hand assembly must be allowed')
    pins=sum(g['count'] for g in plan['runtime_pin_groups'])
    capacity=module['published_gpio_count']-module['reserved_oscillator_gpio_count']
    require(pins<=capacity,'Logical module pin budget exceeded')
    require(cfg['ym_rdivider'] in [1,2,4,8,16,32,64,128],'Invalid Si5351 R divider')
    require(not cfg['ym_clock_divider_in_fpga'],'CLK0 should reach YM without extra FPGA pins')
    vco=cfg['plla_hz'];ref=cfg['reference_hz']
    fb=Fraction(vco,ref);control=Fraction(vco,cfg['control_hz'])
    require(cfg['vco_min_hz']<=vco<=cfg['vco_max_hz'],'PLLA range')
    require(cfg['pll_feedback_min']<=fb<=cfg['pll_feedback_max'] and fb.denominator<=cfg['max_denominator'],'PLLA feedback')
    require(cfg['multisynth_min']<=control<=cfg['multisynth_max'] and control.denominator<=cfg['max_denominator'],'Control divider')
    require(vco==cfg['audio_hz']*cfg['plla_audio_divider'],'Audio divider')
    frame_cycles=Fraction(cfg['audio_hz'],cfg['sample_hz'])
    bit_cycles=frame_cycles/(cfg['i2s_slot_bits']*cfg['i2s_channels'])
    require(frame_cycles.denominator==bit_cycles.denominator==1,'I2S integer clock division')
    profiles=[]
    for hz in cfg['initial_profiles_hz']+cfg['calculation_boundaries_hz']:
        candidates=[]
        for divider in range(cfg['multisynth_min'],cfg['multisynth_max']+1,2):
            fv=hz*cfg['ym_rdivider']*divider;ratio=Fraction(fv,ref)
            if (cfg['vco_min_hz']<=fv<=cfg['vco_max_hz'] and
                cfg['pll_feedback_min']<=ratio<=cfg['pll_feedback_max'] and
                ratio.denominator<=cfg['max_denominator']):
                candidates.append((abs(fv-cfg['pllb_target_hz']),divider,fv,ratio))
        require(candidates,f'No exact PLLB plan for {hz}')
        _,divider,fv,ratio=min(candidates)
        require(Fraction(fv,divider*cfg['ym_rdivider'])==hz,'YM divider equation')
        a,b=divmod(ratio.numerator,ratio.denominator)
        profiles.append({'ym_hz':hz,'pllb_hz':fv,'pllb_a_b_c':[a,b,ratio.denominator],
                         'multisynth_even_divider':divider,'internal_rdivider':cfg['ym_rdivider'],
                         'clk0_to_ym_hz':hz,'mathematical_error_ppm':0})
    return {'date':plan['date'],'variant':plan['variant'],'kind':'architecture arithmetic only',
            'plan_sha256':hashlib.sha256(raw).hexdigest(),
            'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'gpio_required':pins,'gpio_conservative_capacity':capacity,'gpio_spare':capacity-pins,
            'physical_gpio_verified':False,'clock_inputs_required':module['global_clock_inputs_needed'],
            'plla_feedback':str(fb),'audio_divider':cfg['plla_audio_divider'],
            'control_multisynth':str(control),'i2s_frame_cycles':int(frame_cycles),
            'i2s_bit_cycles':int(bit_cycles),'ym_profiles':profiles,
            'clock_registers_generated':False,'timing_or_hardware_verified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');a=p.parse_args()
    result=analyze();text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    path=ROOT/'verification/module-hand-check.json'
    if a.write: path.write_text(text)
    else: require(path.read_text()==text,'Stale M1 arithmetic report')
    print(f"PASS: M1 GPIO {result['gpio_required']}/{result['gpio_conservative_capacity']}; 8 exact clock calculations; physical pinout/clock quality/RTL not verified")
