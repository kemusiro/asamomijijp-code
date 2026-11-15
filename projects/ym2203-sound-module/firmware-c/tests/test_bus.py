# SPDX-License-Identifier: MIT
"""Actual board.c with a timed GPIO/BUSY model;does not claim electrical validation."""
import ctypes as C
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HEADER='''#pragma once
#include <stdbool.h>
#include <stdint.h>
#define GPIO_IN false
#define GPIO_OUT true
void busy_wait_us_32(uint32_t);void busy_wait_ms(uint32_t);uint32_t time_us_32(void);uint64_t time_us_64(void);
void gpio_init(unsigned);void gpio_put(unsigned,bool);void gpio_set_dir(unsigned,bool);
void gpio_disable_pulls(unsigned);void gpio_set_dir_in_masked(uint32_t);void gpio_set_dir_out_masked(uint32_t);
void gpio_put_masked(uint32_t,uint32_t);uint32_t gpio_get_all(void);
'''
MOCK='''#include "revc.h"
#include <string.h>
revc_audio_state revc_audio;
uint32_t clock_us,pins,dirs,errors,commits,address_writes;
static uint32_t busy_until,wr_at,cs_at,changed_at,read_at;
static unsigned address;static uint8_t registers[256];
void busy_wait_us_32(uint32_t n){clock_us+=n;}
void busy_wait_ms(uint32_t n){clock_us+=1000*n;}
uint32_t time_us_32(void){return clock_us;}
uint64_t time_us_64(void){return clock_us;}
void gpio_init(unsigned p){(void)p;}
void gpio_disable_pulls(unsigned p){(void)p;}
void gpio_set_dir(unsigned p,bool out){if(out)dirs|=1u<<p;else dirs&=~(1u<<p);}
void gpio_set_dir_in_masked(uint32_t m){dirs&=~m;}
void gpio_set_dir_out_masked(uint32_t m){dirs|=m;}
void gpio_put_masked(uint32_t m,uint32_t v){pins=(pins&~m)|(v&m);changed_at=clock_us;}
void gpio_put(unsigned p,bool high){
 bool before=(pins>>p)&1;
 if(high)pins|=1u<<p;else pins&=~(1u<<p);
 if(before==high)return;
 if(p==8)changed_at=clock_us;
 if(p==13&&!high)cs_at=clock_us;
 if(p==15&&!high)read_at=clock_us;
 if(p==14&&!high){wr_at=clock_us;if(clock_us-changed_at<1)errors++;}
 if(p==14&&high&&!(pins&(1u<<13))){
  if(clock_us-wr_at<1||clock_us-cs_at<1||clock_us<busy_until||(dirs&255)!=255)errors++;
  if(pins&(1u<<8)){registers[address]=pins&255;commits++;busy_until=clock_us+48;}
  else {address=pins&255;address_writes++;busy_until=clock_us+5;}
 }
}
uint32_t gpio_get_all(void){
 if((pins&((1u<<13)|(1u<<15)))||(dirs&255)||clock_us-cs_at<1||clock_us-read_at<1)errors++;
 return (pins&~255u)|((pins&(1u<<8))?registers[address]:(clock_us<busy_until?128:0));
}
void model_reset(void){clock_us=pins=dirs=errors=commits=address_writes=busy_until=0;memset(registers,0,sizeof(registers));atomic_store(&revc_audio.fault,0);revc_safe_gpio();revc_bus_clear_stats();}
void model_busy(uint32_t n){busy_until=clock_us+n;}
uint32_t model_reg(uint8_t r){return registers[r];}
'''
class BusTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='revc-bus-');p=Path(cls.temp.name)
  for d in ('pico','hardware'):(p/d).mkdir()
  (p/'pico/stdlib.h').write_text(HEADER);(p/'hardware/gpio.h').write_text(HEADER);(p/'model.c').write_text(MOCK)
  subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','-I'+str(p),'-I'+str(ROOT/'src'),str(ROOT/'src/board.c'),str(p/'model.c'),'-o',str(p/'bus.so')],check=True)
  cls.lib=C.CDLL(str(p/'bus.so'));cls.lib.revc_bus_write.argtypes=[C.c_void_p,C.c_uint8,C.c_uint8]
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def val(self,name):return C.c_uint32.in_dll(self.lib,name).value
 def mode(self,fast):C.c_bool.in_dll(self.lib,'revc_bus_fast').value=fast
 def test_fast_and_slow_preserve_busy_retry_data_order_and_1us_pin_margins(self):
  durations=[]
  for fast in (True,False):
   self.lib.model_reset();self.mode(fast);start=self.val('clock_us')
   self.lib.model_busy(100)
   self.assertEqual(self.lib.revc_bus_write(None,0x40,0x55),0)
   self.assertEqual(self.val('commits'),0);self.assertEqual(self.val('address_writes'),0)
   for reg,value in ((0x40,0x55),(0xa4,0x22),(0xa0,0x34),(0x28,0xf0)):
    for retry in range(1000):
     result=self.lib.revc_bus_write(None,reg,value)
     self.assertGreaterEqual(result,0)
     if result:break
    else:self.fail('BUSY did not clear')
    self.assertEqual(self.lib.model_reg(reg),value)
   self.assertEqual(self.val('commits'),4);self.assertEqual(self.val('address_writes'),4)
   self.assertEqual(self.val('errors'),0);durations.append(self.val('clock_us')-start)
  self.assertLess(durations[0],durations[1]//2)
 def test_boot_bus_readback_and_all_off_close_gates_in_both_modes(self):
  for fast in (True,False):
   self.lib.model_reset();self.mode(fast)
   self.assertTrue(self.lib.revc_bus_start());self.assertTrue(self.lib.revc_bus_check())
   self.lib.revc_gates(True);self.lib.revc_all_off()
   self.assertEqual(self.val('pins')&((1<<19)|(1<<26)),0)
   self.assertEqual(self.val('errors'),0)
