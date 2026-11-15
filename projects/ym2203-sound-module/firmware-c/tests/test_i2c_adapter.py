# SPDX-License-Identifier: MIT
"""Compile the real SDK adapter against a FIFO/IRQ-order model,not hardware."""
import ctypes as C
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();p=Path(cls.temp.name);(p/'pico').mkdir();(p/'hardware').mkdir()
        (p/'pico/i2c_slave.h').write_text('''#include <stdint.h>
typedef struct {int unused;} i2c_inst_t;
extern i2c_inst_t *i2c0;
typedef enum {I2C_SLAVE_RECEIVE,I2C_SLAVE_REQUEST,I2C_SLAVE_FINISH} i2c_slave_event_t;
unsigned i2c_get_read_available(i2c_inst_t *);
unsigned i2c_read_byte_raw(i2c_inst_t *);
void i2c_write_byte_raw(i2c_inst_t *,uint8_t);
void i2c_init(i2c_inst_t *,unsigned);
void i2c_slave_init(i2c_inst_t *,uint8_t,void(*)(i2c_inst_t *,i2c_slave_event_t));
''')
        (p/'hardware/gpio.h').write_text('#define GPIO_FUNC_I2C 3\nvoid gpio_set_function(unsigned,unsigned);\n')
        (p/'mock.c').write_text('''#include "pico/i2c_slave.h"
static i2c_inst_t bus;i2c_inst_t *i2c0=&bus;
static void(*callback)(i2c_inst_t *,i2c_slave_event_t);
static uint8_t fifo[256],last_tx;static unsigned used,pos,pins,frequency,address;
unsigned i2c_get_read_available(i2c_inst_t *b){(void)b;return used-pos;}
unsigned i2c_read_byte_raw(i2c_inst_t *b){(void)b;return fifo[pos++];}
void i2c_write_byte_raw(i2c_inst_t *b,uint8_t v){(void)b;last_tx=v;}
void i2c_init(i2c_inst_t *b,unsigned f){(void)b;frequency=f;used=pos=0;pins=0;}
void gpio_set_function(unsigned pin,unsigned function){if(function==3)pins|=1u<<pin;}
void i2c_slave_init(i2c_inst_t *b,uint8_t a,void(*cb)(i2c_inst_t *,i2c_slave_event_t)){(void)b;address=a;callback=cb;}
void mock_feed(const uint8_t *p,unsigned n){used=n;pos=0;for(unsigned i=0;i<n;i++)fifo[i]=p[i];}
void mock_event(unsigned e){callback(i2c0,(i2c_slave_event_t)e);}
unsigned mock_tx(void){return last_tx;}
unsigned mock_pins(void){return pins;}
unsigned mock_frequency(void){return frequency;}
unsigned mock_address(void){return address;}
''')
        lib=p/'adapter.so';subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','-I'+str(p),'-I'+str(ROOT/'src'),str(ROOT/'src/i2c.c'),str(ROOT/'src/transport.c'),str(p/'mock.c'),'-o',str(lib)],check=True)
        cls.c=C.CDLL(str(lib));cls.c.mock_feed.argtypes=[C.c_void_p,C.c_uint];cls.c.revc_i2c_pop.argtypes=[C.c_void_p];cls.c.revc_i2c_publish.argtypes=[C.c_void_p]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):self.c.revc_i2c_init()
    def test_approved_I2C_pins_address_and_initial_speed(self):
        self.assertEqual(self.c.mock_pins(),(1<<20)|(1<<21));self.assertEqual(self.c.mock_address(),0x42);self.assertEqual(self.c.mock_frequency(),100000)
    def test_SDK_finish_before_RX_full_drains_trailing_FIFO_before_publish(self):
        data=bytes(range(208));out=C.create_string_buffer(208)
        for i in range(0,200,8):self.c.mock_feed(data[i:i+8],8);self.c.mock_event(0)
        self.assertEqual(self.c.revc_i2c_pop(out),0)
        self.c.mock_feed(data[200:],8);self.c.mock_event(2);self.c.mock_event(0)
        self.assertEqual(self.c.revc_i2c_pop(out),208);self.assertEqual(out.raw,data);self.assertEqual(self.c.revc_i2c_pop(out),0)
    def test_read_pins_one_status_across_updates_and_restart_releases_it(self):
        self.c.revc_i2c_publish(bytes(range(64)));result=[]
        for i in range(64):
            self.c.mock_event(1);result.append(self.c.mock_tx())
            if i==10:self.c.revc_i2c_publish(bytes(reversed(range(64))))
        self.assertEqual(bytes(result),bytes(range(64)))
        self.c.mock_event(2);self.c.mock_event(1);self.assertEqual(self.c.mock_tx(),63)
