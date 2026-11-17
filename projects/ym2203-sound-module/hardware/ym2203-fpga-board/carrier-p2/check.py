#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static pin/resource/electrical contract checks; these are not a P2 firmware simulation."""
import argparse,copy,hashlib,json,re,unittest
from pathlib import Path
from design import make
from generate import check_export
HERE=Path(__file__).resolve().parent

def validate_pins(d):
 rows=d['gpio'];assert len(rows)==48
 assigned=[r for r in rows if r['net'] is not None]
 assert len(assigned)==47 and {r['gpio'] for r in assigned}==set(range(47))
 assert len({r['net'] for r in assigned})==47 and len({r['module_pad'] for r in rows})==48
 g={r['gpio']:r for r in rows};n={r['net']:r for r in assigned};ext=d['arduino_gpio'];assert set(ext)=={'D'+str(i) for i in range(14)}|{'A'+str(i) for i in range(6)}
 for label,gp in ext.items():assert n['EXT_'+label]['gpio']==gp
 needed={'D0':'uart0_rx','D1':'uart0_tx','D10':'spi1_ss_n','D11':'spi1_tx','D12':'spi1_rx','D13':'spi1_sclk','A4':'i2c1_sda','A5':'i2c1_scl'}
 for label,func in needed.items():
  r=g[ext[label]];assert r['function']==func and func in d['sdk_mux_evidence']['functions'][str(r['gpio'])].values()
 for net,func,gp in [('HOST_SDA','i2c0_sda',20),('HOST_SCL','i2c0_scl',21)]:assert n[net]['function']==func and n[net]['gpio']==gp
 for i in range(6):assert 40<=ext['A'+str(i)]<=45 and n['EXT_A'+str(i)]['adc_channel']==ext['A'+str(i)]-40
 pwms=[n['EXT_D'+str(i)]['pwm'] for i in [3,5,6,9,10,11]];
 for i in [3,5,6,9,10,11]:assert n['EXT_D'+str(i)]['pwm']==d['sdk_mux_evidence']['functions'][str(ext['D'+str(i)])]['0x04']
 assert len(set(pwms))==6 and None not in pwms
 for net in ['M_FM_SD','M_FM_CLK','M_FM_SH','M_I2S_DIN','M_I2S_BCK','M_I2S_LRCK']:assert 0<=n[net]['gpio']<32
 assert n['M_FM_CLK']['gpio']==n['M_FM_SD']['gpio']+1 and n['M_FM_SH']['gpio']==n['M_FM_SD']['gpio']+2
 assert n['M_I2S_LRCK']['gpio']==n['M_I2S_BCK']['gpio']+1
 assert [n['M_D'+str(i)]['gpio'] for i in range(8)]==list(range(8))
 assert g[47]['module_pad']=='B8' and g[47]['net'] is None
 assert d['module_fixed_pins']['A6']=='USB_DP' and d['module_fixed_pins']['A7']=='USB_DM'
 assert d['module_fixed_pins']['A3']=='V5_CARRIER' and d['module_fixed_pins']['B4']=='V3V3'
 assert set(d['module_fixed_pins'].values()) >= {'GND','RUN_N','BOOTSEL_N'}
 return n

def validate_circuit(d,pins):
 p={v['ref']:v for v in d['parts']};assert len(p)==len(d['parts'])
 def net(ref,num):return {x['num']:x['net'] for x in p[ref]['pins']}[str(num)]
 def pair(ref):return {x['net'] for x in p[ref]['pins']}
 for row in pins['gpio']:assert net('MPGA',row['module_pad'])==row['net']
 assert [net('JHOST',i) for i in range(1,5)]==['GND','HOST_SDA','HOST_SCL','GND']
 assert pair('RDOE')=={'M_DATA_OE_N','V3V3'} and pair('RCOE')=={'M_CTRL_OE_N','V3V3'}
 assert net('U8',22)=='M_DATA_OE_N' and net('U8',2)=='M_DATA_DIR' and net('U9',22)=='M_CTRL_OE_N'
 assert net('U12',24)=='Y_RESET_N' and net('Q1',3)=='Y_RESET_N' and pair('R19')=={'V5_CARRIER','RESET_CLAMP_B'}
 assert net('Q2',3)=='RESET_CLAMP_B' and pair('R20')=={'M_RESET_RELEASE','RESET_REL_B'}
 assert pair('RPDAC')=={'M_DAC_ALLOW','GND'} and pair('RPLINE')=={'M_LINE_ALLOW','GND'}
 assert net('U17',17)=='M_DAC_ALLOW' and pair('R55')=={'M_LINE_ALLOW','LINE_B'}
 assert net('U13',6) is None and net('U13',9) is None and net('U13',10)=='SI_YM'
 assert net('UVBUS',2)=='VBUS_DIV' and net('UVBUS',4)=='M_VBUS_SENSE'
 assert pair('RVB1')=={'USB_VBUS_RAW','VBUS_DIV'} and pair('RVB2')=={'VBUS_DIV','GND'}
 # No net tie or two-pin part bridges the USB supply to either carrier power rail.
 for v in p.values():
  ns={x['net'] for x in v['pins']}
  if 'USB_VBUS_RAW' in ns:assert not ns & {'V5_CARRIER','EXT5_IN','V3V3','SHIELD_5V'},v['ref']
 for ref in ['RCC1','RCC2']:assert p[ref]['value']=='5.1k 1%'
 assert pair('JP_SDA')=={'EXT_A4','PANEL_SDA'} and pair('JP_SCL')=={'EXT_A5','PANEL_SCL'}
 assert pair('R37')=={'PANEL_SCL','V3V3'} and pair('R38')=={'PANEL_SDA','V3V3'}
 assert 'Open' in p['JP5V']['footprint'] and pair('JP5V')=={'V5_CARRIER','SHIELD_5V'}
 assert net('JUNO_PWR',2)=='V3V3' and net('JUNO_PWR',3)=='RUN_N' and net('JUNO_PWR',8) is None and net('JUNO_D8',8) is None
 assert [net('JUNO_SPI',i) for i in range(1,7)]==['EXT_D12','V3V3','EXT_D13','EXT_D11','RUN_N','GND']
 assert net('JUNO_D8',9)==net('JUNO_A',5) and net('JUNO_D8',10)==net('JUNO_A',6)
 assert [net('UPANEL',i) for i in [15,16,17]]==['GND']*3 and net('UPANEL',18)=='RUN_N'
 assert net('UPANEL',28)=='RX_LED_N' and net('UPANEL',8) is None
 assert {x['num']:x['type'] for x in p['UPANEL']['pins']}['28']=='output'
 for ref in ['SWRESET','SWBOOT','SWSTOP','SWTEST']:assert {x['num'] for x in p[ref]['pins']}=={'1','2'}
 assert pair('SWRESET')=={'RUN_N','GND'} and pair('SWBOOT')=={'BOOTSEL_N','GND'}
 assert sum(v['ref'].startswith('DLED') for v in p.values())==7
 return len(p)

def validate_geometry(d,placement=None):
 g={(r['ref'],r['pin']):r for r in d['derived_board_header_facts']};assert len(g)==38
 assert abs(g['JUNO_D0',8]['x_mm']-g['JUNO_D8',1]['x_mm']-4.064)<1e-6
 assert g['JUNO_D0',1]['x_mm']==63.5 and g['JUNO_D0',1]['y_mm']==2.54
 assert g['JUNO_A',1]['x_mm']==50.8 and g['JUNO_A',1]['y_mm']==50.8
 assert g['JUNO_PWR',1]['x_mm']==27.94 and g['JUNO_PWR',2]['label']=='IOREF'
 # ICSP pin1 is upper-left in component/top view, based on official R270 rotation.
 assert g['JUNO_SPI',1]['x_mm']==63.627 and g['JUNO_SPI',1]['y_mm']==22.86
 assert g['JUNO_SPI',6]['x_mm']==66.167 and g['JUNO_SPI',6]['y_mm']==27.94
 if placement:
  assert placement['tracks']==0 and not placement['fabrication_ready']
  assert placement['pga_zone_mm'][0]>placement['shield_envelope_mm'][2]
  assert placement['header_module_clearance_x_mm']>=10
 return len(g)

class Regression(unittest.TestCase):
 def setUp(self):self.p=json.loads((HERE/'pins.json').read_text());self.d=make();self.g=json.loads((HERE/'header-geometry.json').read_text())
 def test_nominal(self):validate_pins(self.p);validate_circuit(self.d,self.p);validate_geometry(self.g)
 def bad_pin(self,fn):
  fn(self.p)
  with self.assertRaises(AssertionError):validate_pins(self.p)
 def test_duplicate_gpio(self):self.bad_pin(lambda p:p['gpio'][32].update(gpio=31))
 def test_reserved_psram(self):self.bad_pin(lambda p:p['gpio'][47].update(net='SPARE'))
 def test_wrong_spi_mux(self):self.bad_pin(lambda p:p['gpio'][11].update(function='spi0_tx'))
 def test_wrong_adc(self):self.bad_pin(lambda p:p['gpio'][40].update(adc_channel=2))
 def test_pwm_alias(self):self.bad_pin(lambda p:p['gpio'][14].update(pwm=p['gpio'][15]['pwm']))
 def test_pio_window(self):self.bad_pin(lambda p:p['gpio'][16].update(gpio=46))
 def bad_net(self,ref,num,value):
  for p in self.d['parts']:
   if p['ref']==ref:
    for r in p['pins']:
     if r['num']==str(num):r['net']=value
  with self.assertRaises(AssertionError):validate_circuit(self.d,self.p)
 def test_usb_backfeed(self):self.bad_net('JUSB','A4','V5_CARRIER')
 def test_oe_default(self):self.bad_net('RDOE',2,'GND')
 def test_panel_output_only(self):self.bad_net('UPANEL',28,'STOP_N')
 def test_header_mirrored(self):
  self.g['derived_board_header_facts'][0]['x_mm']=0
  # Deliberately move D0 contact, irrespective of serialization order.
  for r in self.g['derived_board_header_facts']:
   if r['ref']=='JUNO_D0' and r['pin']==1:r['x_mm']=0
  with self.assertRaises(AssertionError):validate_geometry(self.g)
 def test_header_gap(self):
  for r in self.g['derived_board_header_facts']:
   if r['ref']=='JUNO_D8' and r['pin']==1:r['x_mm']+=1.524
  with self.assertRaises(AssertionError):validate_geometry(self.g)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--sdk-registers',type=Path);a.add_argument('--output',type=Path,default=HERE/'schematic');a.add_argument('--report',type=Path);args=a.parse_args()
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Regression))
 if not result.wasSuccessful():raise SystemExit(1)
 pins=json.loads((HERE/'pins.json').read_text());validate_pins(pins);d=json.loads((args.output/'circuit.json').read_text());count=validate_circuit(d,pins)
 nets=check_export(d,args.output/'netlist.xml');erc=json.loads((args.output/'erc.json').read_text());assert not any(s['violations'] for s in erc['sheets'])
 footprints=json.loads((args.output/'footprint-pin-check.json').read_text());assert footprints['parts_checked']==count
 assert {r['ref']:r['logical_pins'] for r in footprints['parts']}=={r['ref']:len(r['pins']) for r in d['parts']}
 geometry=json.loads((HERE/'header-geometry.json').read_text());placement=json.loads((args.output/'placement.json').read_text());contacts=validate_geometry(geometry,placement)
 if args.sdk_registers:assert hashlib.sha256(args.sdk_registers.read_bytes()).hexdigest()==pins['sdk_mux_evidence']['sha256']
 report=dict(schema_version=1,variant='P2',revision='2.1',review='A',date='2026-11-15',status='static_checks_passed_not_hardware_acceptance',tests=result.testsRun,components=count,nets=nets,footprint_parts_checked=footprints['parts_checked'],erc_violations=0,kicad_version=erc['kicad_version'],native_gpio_used=47,gp47_reserved=True,uno_contacts=contacts,unrouted_placement=placement,firmware_implemented=False,existing_host_wire_changed=False,hardware_accepted=False)
 if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
 print('PASS P2 pin/resource, electrical contract, native netlist, ERC and geometry checks')
