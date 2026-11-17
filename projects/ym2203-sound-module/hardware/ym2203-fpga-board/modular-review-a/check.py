#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Electrical split-boundary regressions. NOT runtime or hardware acceptance."""
import binascii,copy,json,struct,unittest
from pathlib import Path
from design import make,HERE,REFERENCE,PINFILE
from module_id import encode,decode

def validate(d,spec):
 b={p['ref']:p for p in d['base']['parts']};m={p['ref']:p for p in d['module']['parts']}
 old={p['ref']:p for p in json.loads(REFERENCE.read_text())['parts']}
 def net(parts,ref,n):return next(p['net'] for p in parts[ref]['pins'] if p['num']==str(n))
 def pair(parts,ref):return {p['net'] for p in parts[ref]['pins']}
 assert (set(b)&set(m))=={'JMOD'}
 assert set(old)<=(set(b)|set(m)) and sum(p['ref']=='U12' for p in d['module']['parts'])==1
 assert b['MPGA']['pins']==old['MPGA']['pins']
 for ref in ['JHOST','JUSB','UESD','UVBUS','U13','Y1','UPANEL','SWRESET','SWSTOP','SWTEST','SWCLOCK','U17','U18','U19','JLINE','RPDAC','RPLINE','R55','R56','R57','R42','R43','R44','UAUX','JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR','JUNO_SPI']:
  assert ref in b,ref
  if ref not in ['U13','U17','U19']:assert b[ref]['pins']==old[ref]['pins'],ref
 assert [net(b,'JHOST',n) for n in [1,2,3,4]]==['GND','HOST_SDA','HOST_SCL','GND']
 for part in b.values():
  ns={p['net'] for p in part['pins']}
  if 'USB_VBUS_RAW' in ns:assert not ns&{'V5_CARRIER','V3V3','V3_AUX','EXT5_IN'}
 assert len(spec['pins'])==60 and [p['pin'] for p in spec['pins']]==list(range(1,61))
 native={r['net']:r['gpio'] for r in json.loads(PINFILE.read_text())['gpio'] if r['net']}
 native.update(PANEL_SDA=42,PANEL_SCL=43)
 for row in spec['pins']:
  n=row['pin'];assert net(b,'JMOD',n)==row['base_net'];assert net(m,'JMOD',n)==row['module_net']
  assert row['gpio']==native.get(row['base_net'])
  if row['status'] in ['reserved_unwired','mechanical_key']:assert row['base_net'] is None and row['module_net'] is None and row['gpio'] is None
  if row['base_net'] is not None and row['module_net'] is not None:assert row['base_net']==row['module_net']
 assert net(b,'JMOD',60) is None and net(m,'JMOD',60) is None
 # Explicit5V->3V3 buffered digital return; source termination must precede connector.
 assert net(m,'U16',14)=='V3V3' and net(m,'U16',7)=='GND'
 for src,uin,uout,rs,cnum,signal,gpio in [('Y_SD',2,3,'RS3',27,'M_FM_SD',16),('Y_CLK',5,6,'RS6',29,'M_FM_CLK',17),('Y_SH',9,8,'RS8',31,'M_FM_SH',18)]:
  assert net(m,'U16',uin)==src and pair(m,rs)=={'BUF_'+signal,signal}
  assert net(m,'U16',uout)=='BUF_'+signal and net(m,'JMOD',cnum)==signal and native[signal]==gpio
 assert net(m,'U12',23)=='Y_SD' and net(m,'U12',39)=='Y_CLK' and net(m,'U12',22)=='Y_SH'
 # I2S and DAC deliberately remain on base, not just analog pass-through.
 assert [net(b,'U17',n) for n in [13,14,15,17]]==['DAC_BCK','DAC_DIN','DAC_LRCK','M_DAC_ALLOW']
 for ref,src,dst in [('R47','M_I2S_BCK','DAC_BCK'),('R48','M_I2S_LRCK','DAC_LRCK'),('R49','M_I2S_DIN','DAC_DIN')]:assert pair(b,ref)=={src,dst}
 assert net(b,'U17',7)=='DAC_R' and pair(b,'RM3R')=={'FM_FILTER_R_AC','SUM_R'}
 assert net(b,'U19',1)=='VREF' and net(b,'U19',2)=='MIX_R' and net(b,'U19',10)=='MUTE_5V'
 assert net(b,'U19',15)=='MUTED_R' and net(b,'JPOT',6)=='OUT_AC_R'
 assert not any('DAC' in p['value'] or 'PCM5102' in p['value'] for p in m.values())
 for i,ch in enumerate('ABC'):
  assert net(m,'U12',20-i)=='SSG_'+ch
  assert pair(m,'RL'+str(i))=={'SSG_'+ch,'GND'} and m['RL'+str(i)]['value']=='1k 1%'
  assert pair(b,'CA'+str(i))=={'SSG_'+ch,'SSG_'+ch+'_AC'}
  assert pair(b,'RM'+str(i))=={'SSG_'+ch+'_AC','SUM_MONO'}
  assert pair(b,'RM'+str(i)+'R')=={'SSG_'+ch+'_AC','SUM_R'}
 assert net(m,'Q1',3)==net(m,'U12',24)=='Y_RESET_N'
 assert pair(m,'R19')=={'V5_CARRIER','RESET_CLAMP_B'} and pair(m,'R23')=={'M_RESET_RELEASE','GND'}
 assert net(m,'Q2',3)=='RESET_CLAMP_B' and pair(m,'RDOE')=={'M_DATA_OE_N','V3V3'}
 assert pair(m,'RCOE')=={'M_CTRL_OE_N','V3V3'}
 assert [net(m,'U8',n) for n in [1,22,23]]==['V3V3','M_DATA_OE_N','V5_CARRIER']
 assert net(m,'U14',3)=='MOD_CLK0' and pair(b,'RCLK0')=={'SI_YM','MOD_CLK0'}
 assert net(m,'UID',8)=='V3V3' and net(m,'UID',7)=='ID_WP'
 assert [net(m,'UID',n) for n in [1,2,3]]==[None]*3
 assert pair(m,'RWP')=={'ID_WP','V3V3'}
 return len(b),len(m)

class ContractTests(unittest.TestCase):
 def setUp(self):self.d=make();self.s=json.loads((HERE/'connector.json').read_text());self.id=json.loads((HERE/'module-id.json').read_text())
 def test_nominal_and_full_pin_boundary(self):self.assertEqual(validate(self.d,self.s),(140,55))
 def bad(self,fn):
  fn()
  with self.assertRaises(AssertionError):validate(self.d,self.s)
 def change_net(self,board,ref,n,value):
  p=next(p for p in self.d[board]['parts'] if p['ref']==ref)
  next(x for x in p['pins'] if x['num']==str(n))['net']=value
 def test_connector_swapped_fm_pair(self):self.bad(lambda:self.change_net('module','JMOD',27,'M_FM_CLK'))
 def test_key_cannot_be_power(self):self.bad(lambda:self.change_net('module','JMOD',60,'V5_CARRIER'))
 def test_no5v_digital_return(self):self.bad(lambda:self.change_net('module','U16',14,'V5_CARRIER'))
 def test_existing_native_gpio_not_reassigned(self):self.bad(lambda:self.change_net('base','MPGA','C1','M_YM_CS_N'))
 def test_i2s_cannot_disappear(self):self.bad(lambda:self.change_net('base','U17',14,None))
 def test_right_channel_mute_must_follow_left(self):self.bad(lambda:self.change_net('base','U19',10,'GND'))
 def test_right_dac_output_must_reach_mixer(self):self.bad(lambda:self.change_net('base','U17',7,None))
 def test_reset_clamp_must_stay_on_module(self):self.bad(lambda:self.change_net('module','Q1',3,None))
 def test_ssg_load_and_ac_path_required(self):self.bad(lambda:self.change_net('module','RL0',2,None))
 def test_usb_vbus_not_carrier5v(self):self.bad(lambda:self.change_net('base','CVBUS',2,'V5_CARRIER'))
 def test_future_pin_not_silently_allocated(self):self.bad(lambda:self.s['pins'][50].update(base_net='M_FM_SD',gpio=16))
 def test_id_roundtrip(self):self.assertEqual(decode(encode(self.id)),self.id)
 def test_id_crc_corruption(self):
  b=bytearray(encode(self.id));b[8]^=1
  with self.assertRaises(ValueError):decode(b)
 def test_id_unknown_format_rejected_even_with_crc(self):
  b=bytearray(encode(self.id));b[7]=2;struct.pack_into('<I',b,60,binascii.crc32(b[:60])&0xffffffff)
  with self.assertRaises(ValueError):decode(b)
 def test_id_non4mhz_rejected(self):
  self.id['clock_hz']=8000000
  with self.assertRaises(ValueError):encode(self.id)
 def test_id_current_budget_rejected(self):
  self.id['budget_3v3_ma']=300
  with self.assertRaises(ValueError):encode(self.id)
 def test_id_reserved_bytes_rejected_even_with_crc(self):
  b=bytearray(encode(self.id));b[20]=1;struct.pack_into('<I',b,60,binascii.crc32(b[:60])&0xffffffff)
  with self.assertRaises(ValueError):decode(b)

if __name__=='__main__':unittest.main(verbosity=2)
