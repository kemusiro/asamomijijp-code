# SPDX-License-Identifier: MIT
"""Actual production startup helper against asynchronous DMA/FIFO model."""
import ctypes as C
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class AudioStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();p=Path(cls.temp.name);(p/'hardware').mkdir();(p/'pico').mkdir()
        (p/'hardware/pio.h').write_text('''#ifndef TEST_PIO_H
#define TEST_PIO_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {uint32_t fdebug;} pio_hw_t;
typedef pio_hw_t *PIO;
bool pio_sm_is_tx_fifo_full(PIO,unsigned);
void pio_sm_set_enabled(PIO,unsigned,bool);
#endif
''')
        (p/'hardware/dma.h').write_text('#include <stdint.h>\nvoid dma_start_channel_mask(uint32_t);\n')
        (p/'pico/stdlib.h').write_text('#include <stdint.h>\nuint32_t time_us_32(void);\nvoid tight_loop_contents(void);\n')
        (p/'mock.c').write_text('''#include "audio_start.h"
#include <stdint.h>
static pio_hw_t hw;static uint32_t now,origin,latency,elapsed_at_enable;
static unsigned level,enabled,stall,started,early_clear;
void model_reset(uint32_t initial,uint32_t delay){hw.fdebug=0xa5a5a5a5;now=origin=initial;latency=delay;elapsed_at_enable=0;level=enabled=stall=started=early_clear=0;}
uint32_t time_us_32(void){return now;}
void tight_loop_contents(void){now++;}
void dma_start_channel_mask(uint32_t mask){if(mask==(1u<<3))started=1;}
static void update(void){if(started&&latency!=UINT32_MAX&&(uint32_t)(now-origin)>=latency)level=8;}
bool pio_sm_is_tx_fifo_full(PIO p,unsigned sm){(void)p;(void)sm;update();if(level<8&&hw.fdebug!=0xa5a5a5a5)early_clear++;return level==8;}
void pio_sm_set_enabled(PIO p,unsigned sm,bool on){(void)p;(void)sm;update();enabled=on;if(on){elapsed_at_enable=now-origin;if(!level)stall=1;}}
unsigned model_start(void){return revc_i2s_start(&hw,0,3);}
unsigned model_enabled(void){return enabled;}
unsigned model_stall(void){return stall;}
unsigned model_level(void){return level;}
unsigned model_elapsed(void){return elapsed_at_enable;}
unsigned model_early_clear(void){return early_clear;}
unsigned model_fdebug(void){return hw.fdebug;}
''')
        lib=p/'start.so';subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','-I'+str(p),'-I'+str(ROOT/'src'),str(ROOT/'src/audio_start.c'),str(p/'mock.c'),'-o',str(lib)],check=True)
        cls.c=C.CDLL(str(lib));cls.c.model_reset.argtypes=[C.c_uint32,C.c_uint32];cls.c.model_fdebug.restype=C.c_uint32
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_DMA_is_primed_before_PIO_runs_at_all_modelled_start_latencies(self):
        for latency in [0,1,3,20,80,900]:
            self.c.model_reset(100,latency);self.assertEqual(self.c.model_start(),1)
            self.assertEqual(self.c.model_level(),8,latency);self.assertEqual(self.c.model_stall(),0,latency)
            self.assertGreaterEqual(self.c.model_elapsed(),latency);self.assertEqual(self.c.model_early_clear(),0)
            self.assertEqual(self.c.model_fdebug(),1<<24)
    def test_failed_DMA_prime_does_not_enable_clocks(self):
        self.c.model_reset(100,0xffffffff);self.assertEqual(self.c.model_start(),0)
        self.assertEqual(self.c.model_enabled(),0);self.assertEqual(self.c.model_stall(),0)
        self.assertEqual(self.c.model_fdebug(),0xa5a5a5a5)
    def test_prime_deadline_crosses_uint32_clock_wrap(self):
        self.c.model_reset(0xfffffffa,20);self.assertEqual(self.c.model_start(),1)
        self.assertEqual(self.c.model_level(),8);self.assertEqual(self.c.model_stall(),0)
        self.assertEqual(self.c.model_elapsed(),20)
