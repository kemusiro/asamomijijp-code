#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Connected-net contracts, physical pad validation and declared analog/RC bounds.
No firmware simulation, SPICE silicon model, PCB DRC or bench acceptance.
"""
import argparse,copy,csv,hashlib,itertools,json,math,re,sys,unittest
from pathlib import Path
from design import make,HERE,ROOT
REPO=HERE.parents[4]
FOOTPRINTS=next((p for p in [Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'),Path('/usr/share/kicad/footprints'),Path('/opt/homebrew/share/kicad/footprints')] if p.is_dir()),None)
P=Path('projects/ym2203-sound-module/hardware/ym2203-fpga-board')

def read(name):return json.loads((HERE/name).read_text())
def require(x,m):
 if not x:raise ValueError(m)
def component(d,board,ref):
 v=[p for p in d[board]['parts'] if p['ref']==ref]
 require(len(v)==1,'missing/duplicate '+board+'/'+ref);return v[0]
def net(d,b,ref,n):
 v=[p for p in component(d,b,ref)['pins'] if p['num']==str(n)]
 require(len(v)==1,'pin identity '+ref+':'+str(n));return v[0]['net']
def exact(d,b,ref,ps):
 for n,expected in ps.items():require(net(d,b,ref,n)==expected,'net mismatch '+b+'/'+ref+':'+str(n))

def validate(d):
 pins=read('pins.json');conn=read('connector.json')
 require(pins['schematic_applied'] and not pins['firmware_applied'],'adopted schematic scope')
 require(pins['base_mcu']=='Pimoroni PGA2350 PIM722' and pins['module_mcu']=='Waveshare Core2350B0','onePGA architecture')
 for b in ['base','module']:
  require(len({p['ref'] for p in d[b]['parts']})==len(d[b]['parts']),'duplicate refs')
 for row in pins['base']:
  exact(d,'base','MPGA',{row['module_pad']:row['net']})
 for pad in set(pins['historical_native_pads'])-{r['module_pad'] for r in pins['base']}:
  exact(d,'base','MPGA',{pad:None})
 for row in pins['module']:
  hdr,n=row['module_pad'].split('.');exact(d,'module','JCORE'+hdr[1:],{n:row['net']})
 exact(d,'module','JCORE2',{15:'V5_MODULE',16:'MCU_3V3',11:'CORE_RUN_N',3:None})
 exact(d,'module','JCORE4',{12:None}) # GP39 onboardLED is unused.
 # Frozen UNO/HOST/USB/panel identities from reviewA remain unchanged.
 original=json.loads((ROOT/'modular-review-a/base/circuit.json').read_text())
 for ref in ['JHOST','JUSB','UESD','UVBUS','UPANEL','JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR','JUNO_SPI','JP_SDA','JP_SCL','SWRESET']:
  old=next(p for p in original['parts'] if p['ref']==ref)
  require(component(d,'base',ref)['pins']==old['pins'],'legacy boundary changed '+ref)
 for row in conn['pins']:
  for b in ['base','module']:exact(d,b,'JMOD',{row['pin']:row[b+'_net']})
 require(net(d,'module','JMOD',32) is None and net(d,'base','JMOD',32) is None,'key')
 require(not any(net(d,b,'JMOD',n) in ['MCU_3V3','ADC_3V3','V3V3','V3_AUX'] for b in ['base','module'] for n in range(1,33)),'no3V3 export')
 for b in ['base','module']:
  for p in d[b]['parts']:
   if p['ref'].startswith('R') and p['value'].split()[0]=='0':
    nets={x['net'] for x in p['pins']}
    require(not len(nets & {'MCU_3V3','ADC_3V3','V3V3','V3_AUX'})>1,'shorted regulator outputs')
 # Physical STOP/reset permit and local output gates must not depend on an SPI reply.
 for ref,src,out in [('UPERMIT','MOD_ENABLE','MODULE_PERMIT'),('UDACRUN','M_DAC_ALLOW','DAC_RUN_OK'),('ULINERUN','M_LINE_ALLOW','LINE_RUN_OK')]:exact(d,'base',ref,{1:src,2:'RUN_N',4:out,5:'V3V3'})
 exact(d,'base','UDACBUF',{14:'V3_AUX',12:'DAC_RUN_OK',11:'DAC_XSMT'})
 exact(d,'base','U17',{17:'DAC_XSMT',6:'DAC_L',7:'DAC_R'})
 exact(d,'base','R55',{1:'LINE_RUN_OK'})
 exact(d,'base','U19',{1:'VREF',2:'MIX_R',10:'MUTE_5V',11:'MUTE_5V',12:'MIX_MONO',13:'VREF',14:'MUTED_MONO',15:'MUTED_R'})
 exact(d,'module','UENABLE',{2:'L_MOD_ENABLE',4:'MODULE_PERMIT_LOCAL',5:'MCU_3V3'})
 exact(d,'module','URUNOD',{2:'MODULE_PERMIT_LOCAL',4:'CORE_RUN_N'})
 require(next(x for x in component(d,'module','URUNOD')['pins'] if x['num']=='4')['type']=='open_collector','manualRUN short safety')
 exact(d,'module','UYMALLOW',{1:'MODULE_PERMIT_LOCAL',2:'YM_RESET_RELEASE',4:'YM_RELEASE_OK'})
 exact(d,'module','UYMRUN',{1:'YM_RELEASE_OK',2:'CORE_RUN_N',4:'YM_RELEASE_SAFE'})
 exact(d,'module','Q1',{2:'GND',3:'Y_RESET_N'});exact(d,'module','R19',{1:'V5_MODULE',2:'RESET_CLAMP_B'})
 exact(d,'module','R20',{1:'YM_RELEASE_SAFE'});exact(d,'module','RENPD',{1:'L_MOD_ENABLE',2:'GND'})
 exact(d,'module','UADCPOWER',{1:'V5_MODULE',2:'GND',3:'MODULE_PERMIT_LOCAL',5:'ADC_3V3'})
 exact(d,'module','RADCBLEED',{1:'ADC_3V3',2:'GND'})
 exact(d,'module','UADC',{1:'ADC_SSG_B',3:'ADC_SSG_A',29:'ADC_SSG_C',6:'ADC_VREF',7:'GND',8:'ADC_3V3',11:'ADC_LDO_1V8',12:'GND',13:'ADC_3V3',14:'ADC_3V3',15:'GND',19:'ADC_INPUT_ARM',23:'ADC_SDA',24:'ADC_SCL',25:'GND',26:'GND'})
 exact(d,'module','UADCCLK',{14:'ADC_3V3',2:'MOD_I2S_BCK',3:'ADC_BCK',5:'MOD_I2S_LRCK',6:'ADC_LRCK'})
 exact(d,'module','UADCDATA',{2:'ADC_DOUT_RAW',4:'ADC_DOUT',5:'MCU_3V3'})
 exact(d,'module','RADCSDA',{1:'ADC_SDA',2:'ADC_3V3'});exact(d,'module','RADCSCL',{1:'ADC_SCL',2:'ADC_3V3'})
 exact(d,'module','UINPUTAND',{1:'ADC_INPUT_ARM',2:'YM_RELEASE_SAFE',4:'ADC_INPUT_ENABLE',5:'ADC_3V3'})
 muxmap=[(1,2,3),(4,5,6),(10,9,8)]
 for ch,(sel,src,dst) in zip('ABC',muxmap):
  exact(d,'module','UINPUT',{sel:'ADC_INPUT_ENABLE',src:'SSG_DIV_'+ch,dst:'SSG_ISO_'+ch,14:'ADC_3V3'})
  exact(d,'module','RDIVT'+ch,{1:'SSG_'+ch,2:'SSG_DIV_'+ch});exact(d,'module','RDIVB'+ch,{1:'SSG_DIV_'+ch,2:'GND'})
  exact(d,'module','CAC'+ch,{1:'SSG_ISO_'+ch,2:'SSG_AC_'+ch});exact(d,'module','RADCLIMIT'+ch,{1:'SSG_AC_'+ch,2:'ADC_SSG_'+ch})
  require(component(d,'module','RADCLIMIT'+ch)['value']=='4.7k 1%','ADC current limit')
  exact(d,'module','DCLAMP'+ch,{1:'GND',2:'ADC_3V3',3:'ADC_SSG_'+ch})
 require(component(d,'module','UINPUT')['value']=='TMUX1511PWR','poweroff isolation part')
 exact(d,'module','ULINKTX',{1:'MOD_SPI_CS_N'});exact(d,'base','URXBUF',{1:'MOD_SPI_CS_N'})
 require(all(p['value']!='SN74LVC125APWR' for b in d.values() for p in b['parts']),'all newbuffer paths need explicitIoff part')
 # Cross-check public ABI constants from current unchanged firmware.
 h=(REPO/'projects/ym2203-sound-module/firmware-c/src/stream.h').read_text()
 for k,v in [('REVC_QUEUE_CAPACITY',1024),('REVC_STATUS_SIZE',64),('REVC_LEASE_US',1000000),('REVC_PACKET_PAYLOAD',192)]:require(re.search(r'#define\s+'+k+r'\s+'+str(v)+'u',h),'legacyABI')
 require('S_PING,S_STOP,S_BEGIN,S_PUSH,S_PLAY,S_KEEP,S_SEAL' in h,'publicopcodes')
 return True

def bounds():
 # Declared component tolerance model; not SPICE or actual silicon behavior.
 ratio_max=(1000*1.01)/(3010*.99+1000*1.01);step=5.25*ratio_max
 r_limit_min=4700*.99
 fault_current=(5.25+1.8)/r_limit_min
 cap_upper=80e-6;r_bleed_max=680*1.01;i_leak=50e-6;off_s=.250
 final=i_leak*r_bleed_max+(3.6-i_leak*r_bleed_max)*math.exp(-off_s/(r_bleed_max*cap_upper))
 require(step<3.6,'TMUX poweroff voltage');require(fault_current<.005,'ADC clamp current budget');require(final<.1,'ADC rail discharge')
 p=read('power-plan.json');totals={}
 for load in p['loads']:totals[load['rail']]=totals.get(load['rail'],0)+load['budget_ma']
 for reg in p['regulators']:require(totals[reg['rail']]<reg['rating_ma'],'rail budget')
 module=sum(v for k,v in totals.items() if k.startswith('MODULE_'));whole=sum(totals.values());admitted=whole-module+p['module_5v_admission_limit_ma']
 require(module<=500 and admitted<1250,'5V/PTC budget at40C')
 # Assumed typical ADC20k input, not an input resistance minimum specification.
 rth=(3010*1000)/(3010+1000);load_r=20000;rlimit=4700;cs=470e-12;cc=2.2e-6
 def gain(f):
  zload=1/(1/load_r+2j*math.pi*f*cs)
  zcap=1/(2j*math.pi*f*cc)
  return abs((1000/4010)*zload/(rth+4.5+rlimit+zcap+zload))
 flat=gain(1000)
 return dict(scope='conditional interval and passiveRC calculations, NOT validated analog silicon/SPICE/bench',divider_max=ratio_max,tmux_signal_bound_v=step,unclamped_adc_transient_v=[-step,1.8+step],adc_absolute_input_limits_v=[-1.7,5.0],clamp_fault_current_bound_ma=fault_current*1000,adc_internal_ESD_current_guidance_ma=5,minimum_off_ms=250,adc_cap_upper_uf=80,leakage_budget_ua=50,adc_rail_after_wait_bound_v=final,ldo_typical_120ohm_not_needed=True,rail_budgets_ma=totals,module_input_ma=module,total_input_ma=whole,with_module_500ma_limit_ma=admitted,passive_rc_typical_20k_adc_gain_1khz=flat,passive_rc_gain_relative_1khz_db={str(f):20*math.log10(gain(f)/flat) for f in [20,100,1000,10000,20000]},must_measure=['ADCrail<0.1V before reenable','off leakage<=50uA andC<=80uF','SSG/ADC transient,current andfrequencyresponse','PGA/CoreLDO thermal','5V atYM within4.75..5.25V','clock edges andreal FM/SSGbalance'])

def state_checks():
 count=0
 for base3,base_run,base_allow,mod3,core_button,local_release,adc3,adc_arm in itertools.product([False,True],repeat=8):
  # Boolean logic corresponds to checked AND/open-drain/default-clamp connections.
  permit=base3 and base_run and base_allow
  modpermit=mod3 and permit
  core_run=modpermit and not core_button
  ym_safe=mod3 and modpermit and core_run and local_release
  analog_on=adc3 and adc_arm and ym_safe
  if not base3 or not base_run or not base_allow or not mod3 or core_button:
   require(not ym_safe and not analog_on,'reset mustdominate all storedlogic')
  if not adc3 or not adc_arm:require(not analog_on,'ADCoff/unarmed isolation')
  count+=1
 return count

class Regression(unittest.TestCase):
 def setUp(self):self.d=make();validate(self.d)
 def bad(self,edit):
  edit(self.d)
  with self.assertRaises(ValueError):validate(self.d)
 def change(self,b,r,n,v):next(p for p in component(self.d,b,r)['pins'] if p['num']==str(n))['net']=v
 def test_nominal(self):validate(self.d)
 def test_uno_swap(self):self.bad(lambda d:self.change('base','JUNO_SPI',1,'EXT_D11'))
 def test_host_swap(self):self.bad(lambda d:self.change('base','JHOST',2,'HOST_SCL'))
 def test_usb_backfeed(self):self.bad(lambda d:self.change('base','JUSB','A4','V5_CARRIER'))
 def test_adopted_gpio(self):self.bad(lambda d:self.change('base','MPGA','B3','MOD_SPI_MOSI'))
 def test_core_not_pga(self):self.bad(lambda d:self.change('module','JCORE2',15,'MCU_3V3'))
 def test_key(self):self.bad(lambda d:self.change('base','JMOD',32,'V5_CARRIER'))
 def test_i2s_link(self):self.bad(lambda d:self.change('module','JMOD',17,'SSG_A'))
 def test_enable_reset_bypass(self):self.bad(lambda d:self.change('base','UPERMIT',2,'V3V3'))
 def test_dac_reset_bypass(self):self.bad(lambda d:self.change('base','UDACRUN',2,'V3V3'))
 def test_line_reset_bypass(self):self.bad(lambda d:self.change('base','ULINERUN',2,'V3V3'))
 def test_run_pushpull(self):self.bad(lambda d:next(p for p in component(d,'module','URUNOD')['pins'] if p['num']=='4').update(type='output'))
 def test_module_reset_bypass(self):self.bad(lambda d:self.change('module','UYMRUN',2,'MCU_3V3'))
 def test_5v_reset_clamp(self):self.bad(lambda d:self.change('module','R19',1,'MCU_3V3'))
 def test_adc_never_off(self):self.bad(lambda d:self.change('module','UADCPOWER',3,'MCU_3V3'))
 def test_adc_ldo_overvoltage(self):self.bad(lambda d:self.change('module','UADC',11,'ADC_3V3'))
 def test_adc_ground(self):self.bad(lambda d:self.change('module','UADC',7,'FLOAT_AGND'))
 def test_adc_digital_off_isolation(self):self.bad(lambda d:self.change('module','UADCCLK',14,'MCU_3V3'))
 def test_adc_return_off_isolation(self):self.bad(lambda d:self.change('module','UADCDATA',5,'ADC_3V3'))
 def test_adc_i2c_backfeed(self):self.bad(lambda d:self.change('module','RADCSDA',2,'MCU_3V3'))
 def test_input_unarmed(self):self.bad(lambda d:self.change('module','UINPUTAND',1,'ADC_3V3'))
 def test_input_switch_missing(self):self.bad(lambda d:component(d,'module','UINPUT').update(value='WIRE'))
 def test_ac_cap_bypassed(self):self.bad(lambda d:self.change('module','CACA',1,'SSG_DIV_A'))
 def test_clamp_reversed(self):self.bad(lambda d:self.change('module','DCLAMPA',1,'ADC_3V3'))
 def test_current_limit_removed(self):self.bad(lambda d:component(d,'module','RADCLIMITA').update(value='0'))
 def test_miso_drives_when_not_selected(self):self.bad(lambda d:self.change('module','ULINKTX',1,'GND'))
 def test_power_state_combinations(self):self.assertEqual(state_checks(),256)
 def test_analog_and_discharge_bounds(self):bounds()


def main():
 global REPO,FOOTPRINTS
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=REPO);p.add_argument('--output',type=Path);p.add_argument('--footprints',type=Path,default=FOOTPRINTS);a=p.parse_args();REPO=a.repo;FOOTPRINTS=a.footprints
 require(FOOTPRINTS is not None,'provide --footprints KiCad library directory')
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Regression))
 if not result.wasSuccessful():return 1
 circuits=make();parts=0
 for b,d in circuits.items():
  require(read(b+'/circuit.json')==d,'native circuit regeneration required')
  for c in d['parts']:
   library,name=c['footprint'].split(':')
   path=(ROOT/'carrier-p2/pcb-review-b/schematic/P2C.pretty' if library=='P2C' else FOOTPRINTS/(library+'.pretty'))/(name+'.kicad_mod')
   require(path.exists(),'missingphysicalfootprint '+str(path.name));pads=set(re.findall(r'\(pad\s+"([^\"]+)"',path.read_text()));require({p['num'] for p in c['pins']}<=pads,'physicalpin mismatch '+c['ref']);parts+=1
 native=read('native-verification.json');require(all(s['erc_violations']==0 for s in native['boards'].values()),'ERCfail')
 report=dict(schema_version=1,date='2026-11-16',python=sys.version.split()[0],kicad_version=native['kicad_version'],contract_tests_passed=result.testsRun,power_state_combinations=state_checks(),physical_pad_sets_checked=parts,boards=native['boards'],scope='nativeERC/netlist/pads and declared circuit/RC/Boolean checks; no firmware runtime, PCB or bench',gpio_user_approved=True,base_gpio=35,module_gpio=30,existing_host_firmware_changed=False,uno_geometry_changed=False,hardware_accepted=False,power_and_input_bounds=bounds())
 if a.output:a.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2));return 0
if __name__=='__main__':sys.exit(main())
