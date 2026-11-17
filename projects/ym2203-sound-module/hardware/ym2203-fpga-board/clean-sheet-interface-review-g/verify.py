# SPDX-License-Identifier: MIT
"""Static pin-design verifier. Does not execute a PIO program or change firmware."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from export_pinout import outputs

HERE=Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def load():
    return {k:read(HERE/(k+'.json')) for k in
            ['connector','gpio-proposal','architecture','profiles','bus-timing']}


def references(hardware):
    parts=read(hardware/'digital-module-review-c/base/circuit.json')['parts']
    m=next(p for p in parts if p['ref']=='MPGA')
    pads={int(p['name'][2:]):p['num'] for p in m['pins'] if p['name'].startswith('GP')}
    source=hardware.parent.parent/'firmware-c/src'
    return {'pads':pads,'sdk':read(hardware/'carrier-p2/pins.json')['sdk_mux_evidence']['functions'],
            'F':read(hardware/'parallel-module-interface-review-f/architecture.json'),
            'C_header':(source/'stream.h').read_text(),'C_source':(source/'stream.c').read_text()}


def validate(d,r):
    c,g,a,p,t=(d[k] for k in ['connector','gpio-proposal','architecture','profiles','bus-timing'])
    errors=[]

    def need(ok,code):
        if not ok:errors.append(code)

    pins={p['pin']:p for p in c['pins']}
    need(c['positions']==40 and c['rows']==20 and c['pitch_mm']==2.54 and c['contact_grid_length_mm']==48.26,'geometry')
    need(len(pins)==len(c['pins'])==40 and set(pins)==set(range(1,41)),'pin_uniqueness')
    need(all(p['row']==(p['pin']+1)//2 and p['column']==('A' if p['pin']%2 else 'B') for p in c['pins']),'mating_view')
    need(c['key_pin']==6 and pins.get(6,{}).get('signal')=='KEY','key6')
    need(not c['legacy_connector_compatible'] and not c['legacy_partial_mating_permitted'] and not c['hot_plug'],'clean_sheet_scope')
    grounds={p['pin'] for p in c['pins'] if p['kind']=='ground'}
    need(grounds=={2,4,13,14,26,28,30,32,35,36,38,40},'ground_layout')
    need(all(p['voltage_v']==3.3 for p in c['pins'] if p['kind']=='digital'),'digital_voltage')
    need((pins.get(37,{}).get('signal'),pins.get(39,{}).get('signal'))==('AUDIO_L','AUDIO_R')
         and {35,36,38,40}<=grounds,'analog_guard')
    need(all(pins.get(n,{}).get('signal')=='SOUND_CLK'+str(i) and n+1 in grounds
             for i,n in enumerate([25,27,29])),'clock_ground_pairs')
    data_contacts=[9,10,11,12,15,16,17,18]
    need(all(pins.get(n,{}).get('signal')=='BUS_D'+str(i) and pins[n]['base_gpio']==i
             for i,n in enumerate(data_contacts)),'data_contacts')
    need(all(pins.get(19+i,{}).get('signal')=='MOD_CTL'+str(i) and pins[19+i]['base_gpio']==8+i for i in range(4)),'control_contacts')
    need((pins[7]['base_gpio'],pins[8]['base_gpio'])==(12,13),'enable_alert')
    need((pins[23]['base_gpio'],pins[24]['base_gpio'])==(42,43),'service_contacts')
    need((pins[31]['base_gpio'],pins[33]['base_gpio'],pins[34]['base_gpio'])==(15,16,18),'audio_contacts')
    gpios=[v['gpio'] for v in g['base']]
    need(len(gpios)==len(set(gpios))==g['base_assigned']==44,'gpio_uniqueness')
    need(set(gpios)==set(range(35))|set(range(38,47)) and g['base_free_gpio']==[35,36,37]
         and g['reserved_gpio']==[47] and g['base_usable']==47,'gpio_budget')
    need(all(v['module_pad']==r['pads'].get(v['gpio']) for v in g['base']),'vendor_pad_identity')
    nets={v['net']:v['gpio'] for v in g['base']}
    need(all(nets.get('BUS_D'+str(i))==i for i in range(8)) and g['data_gpio_lsb_first']==list(range(8)),'contiguous_data')
    need(g['control_gpio']==dict(zip(['CTL0','CTL1','CTL2','CTL3'],range(8,12)))
         and all(nets.get('MOD_CTL'+str(i))==8+i for i in range(4)),'contiguous_control')
    need(g['design_authority']['clean_sheet_base_and_module_authorized']
         and not g['design_authority']['old_connector_or_gpio_preservation_required']
         and not g['firmware_applied'] and not g['schematic_applied'],'design_not_adopted')
    need(g['host_i2c']=={'controller':0,'sda':20,'scl':21,'address':66,'hz':100000}
         and g['service_i2c']=={'controller':1,'sda':42,'scl':43,'hz':100000},'i2c_contract')
    uno=g['uno'];u=uno['gpio']
    need(uno['shape']=='UNO R3' and uno['io_ref_v']==3.3
         and set(u)=={'D'+str(i) for i in range(14)}|{'A'+str(i) for i in range(6)},'uno_shape_roles')
    need(len(set(u.values()))==20 and all(nets.get('EXT_'+name)==gp for name,gp in u.items()),'uno_gpio')
    bus_gpio=set(range(19))
    need(not set(u.values()).intersection(bus_gpio),'uno_bus_conflict')
    expected_mux={0:('0x01','spi0_rx'),1:('0x01','spi0_ss_n'),2:('0x01','spi0_sclk'),3:('0x01','spi0_tx'),
                  u['D12']:('0x01','spi1_rx'),u['D10']:('0x01','spi1_ss_n'),
                  u['D13']:('0x01','spi1_sclk'),u['D11']:('0x01','spi1_tx'),
                  u['D1']:('0x02','uart0_tx'),u['D0']:('0x02','uart0_rx'),
                  20:('0x03','i2c0_sda'),21:('0x03','i2c0_scl'),
                  u['A4']:('0x03','i2c1_sda'),u['A5']:('0x03','i2c1_scl')}
    need(all(r['sdk'].get(str(gp),{}).get(fn)==value for gp,(fn,value) in expected_mux.items()),'sdk_mux')
    need(u['A4']==42 and u['A5']==43 and {u['A'+str(i)] for i in range(6)}==set(range(40,46)),'uno_adc')
    for name in ['A'+str(i) for i in range(6)]:
        rec=next((v for v in g['base'] if v['net']=='EXT_'+name),{})
        need(rec.get('adc_channel')==u[name]-40,'adc_channel')
    actual_pwm={name:r['sdk'].get(str(u[name]),{}).get('0x04') for name in uno['pwm_pins']}
    need(set(actual_pwm)=={'D3','D5','D6','D9','D10','D11'} and len(set(actual_pwm.values()))==6
         and actual_pwm==uno['pwm_channels'],'uno_pwm')
    audio={'dac_tx':14,'bck':15,'lrck':16,'adc_rx':17,'module_rx':18}
    need(g['audio']==audio and all(nets.get(n)==gp for n,gp in
         {'DAC_I2S_DATA':14,'AUDIO_BCK':15,'AUDIO_LRCK':16,'BASE_ADC_DOUT':17,'MOD_I2S_DATA':18}.items()),'audio_gpio')
    need(nets.get('M_DAC_ALLOW')==38 and nets.get('M_LINE_ALLOW')==39 and nets.get('M_VBUS_SENSE')==46,'safety_gpio')
    pb=g['pio_budget'];bus=pb['parallel'];aud=pb['audio']
    need(bus=={'instance':0,'gpio_base':0,'data_base':0,'data_count':8,'set_base':8,'set_count':4,'candidate_sms':1},'pio_parallel_range')
    need(aud=={'instance':1,'gpio_base':0,'tx_data_base':14,'clock_sideset_base':15,
               'clock_sideset_count':2,'rx_data':[17,18],'candidate_sms':3},'pio_audio_range')
    need(bus['instance']!=aud['instance'] and bus['candidate_sms']<=4 and aud['candidate_sms']<=4
         and not pb['program_assembled'] and not pb['hardware_timing_verified'],'pio_resource_scope')
    par=a['control']['parallel']
    need(par['gpio_data_lsb_first']==list(range(8)) and par['connector_data_lsb_first']==data_contacts
         and par['controls']==dict(zip(['CTL0','CTL1','CTL2','CTL3'],range(19,23))), 'architecture_bus')
    need(par['single_pio_OUT_8_supported_by_this_mapping'] and not par['complete_pio_program_implemented']
         and not par['data_may_update_while_strobe_active'] and not par['five_volt_translation_removed'],'pio_feasibility_only')
    need(not a['control']['spi_parallel_simultaneous'] and a['control']['service_i2c_remains_available_in_parallel'],'mode_exclusion')
    masks=a['control']['profile_direction_masks']
    need(masks['sn76489an_parallel']=={'data_outputs':255,'data_inputs':0,'control_outputs':6,'control_inputs':8}
         and masks['ay38910_parallel']=={'data_outputs':255,'data_inputs':0,'control_outputs':6,'control_inputs':0}
         and masks['spi']=={'data_outputs':14,'data_inputs':1,'control_outputs':3,'control_inputs':0},'profile_direction')
    for m in masks.values():
        need(not m['data_outputs']&m['data_inputs'] and not m['control_outputs']&m['control_inputs'],'direction_contention')
    old_audio=copy.deepcopy(r['F']['audio'])
    old_audio['i2s'].update(module_data_gpio=18,adc_data_gpio_candidate=17,shared_bck_gpio=15,shared_lrck_gpio=16)
    need(a['audio']==old_audio,'audio_semantics')
    need(a['legacy']==r['F']['legacy'],'legacy_wire_semantics')
    for k,v in r['F']['stop'].items():
        if k!='parallel_cleanup':need(a['stop'].get(k)==v,'stop_ownership_semantics')
    need(a['stop']['parallel_cleanup'].startswith('gate first; disable PIO'),'pio_stop_handover')
    need(a['hardware_compatibility']=={'old_base':False,'old_sound_card':False,'old_gpio_assignment':False,
                                     'host_wire_and_software_compatibility_opn1':True},'compatibility_boundary')
    constants={k:int(v) for k,v in re.findall(r'#define\s+(REVC_\w+)\s+(\d+)u',r['C_header'])}
    legacy=a['legacy']
    need(constants.get('REVC_QUEUE_CAPACITY')==legacy['fifo_events']==1024
         and constants.get('REVC_STATUS_SIZE')==legacy['status_bytes']==64
         and constants.get('REVC_PACKET_PAYLOAD')==legacy['push_max_events']*legacy['event_bytes']==192
         and constants.get('REVC_LEASE_US')==legacy['lease_ms']*1000==1000000
         and legacy['signature'] in r['C_source'],'C_wire_constants')
    need(not a['power']['module_regulator_outputs_connected_to_aux'] and not a['power']['external_module_power']
         and not a['module_mcu_required'] and not a['module_adc_required'],'minimal_power_modules')
    need(all(q['connector_revision']=='P2 clean-sheet5.0-draft' for q in p['profiles']),'profile_revision')
    pio=t['pio_candidate']
    need(pio['frequency_hz_candidate']*pio['cycle_ns']==1000000000
         and pio['AY_write_pulse_cycles_candidate']*pio['cycle_ns']==2000
         and pio['FIFO_underflow_must_stall_only_while_inactive'] and pio['READY_wait_must_be_bounded']
         and pio['STOP_must_disable_SM_and_reclaim_outputs'] and not pio['instruction_program_assembled'],'pio_timing_candidate')
    return sorted(set(errors))


def verify_files(hardware):
    errors=validate(load(),references(hardware))
    for rec in read(HERE/'preservation.json')['files']:
        target=hardware/rec['path'].removeprefix('../')
        if hashlib.sha256(target.read_bytes()).hexdigest()!=rec['sha256']:
            errors.append('preservation:'+rec['path'])
    for name,expected in outputs(hardware).items():
        if not (HERE/name).exists() or (HERE/name).read_text()!=expected:
            errors.append('stale_artifact:'+name)
    return errors


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hardware-root',type=Path,default=HERE.parent)
    args=parser.parse_args();errors=verify_files(args.hardware_root)
    if errors:raise SystemExit('FAIL:'+','.join(errors))
    print('PASS:clean-sheet40pin;GPIO0..7/8..11;44GPIO/3free;PIO windows;vendor pads/SDK mux;UNO/analog guards;HOST wire constants')
    print('SCOPE:pin feasibility only;new hardware/firmware/PIO assembly not verified')
