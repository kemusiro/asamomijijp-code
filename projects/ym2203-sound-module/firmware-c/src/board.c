// SPDX-License-Identifier: MIT
#include "revc.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"
static int latched=-1;
bool revc_bus_fast=true;
revc_bus_stats revc_bus;
void revc_bus_clear_stats(void){revc_bus=(revc_bus_stats){0};}
// Yamaha YM2203 Nov1989 p9:FM/SSG write>=200/250ns,read>=250/400ns.
// 1us phases exceed both limits and leave margin for the Rev C level shifters.
// BUSY is still polled before address/data;this does not assume a fixed FM wait.
// Slow retains alpha2's10us phases and20us recovery for an audible A/B test.
static void settle(void){busy_wait_us_32(revc_bus_fast?1:10);}
void revc_safe_gpio(void) {
    const unsigned low[]={PIN_ARM,PIN_LINE,PIN_DAC,PIN_RESET,PIN_DATA,PIN_BCLK,PIN_LRCK};
    for(unsigned i=0;i<sizeof(low)/sizeof(*low);i++){gpio_init(low[i]);gpio_put(low[i],0);gpio_set_dir(low[i],GPIO_OUT);}
    const unsigned high[]={PIN_CS,PIN_WR,PIN_RD};
    for(unsigned i=0;i<3;i++){gpio_init(high[i]);gpio_put(high[i],1);gpio_set_dir(high[i],GPIO_OUT);}
    gpio_init(PIN_A0);gpio_put(PIN_A0,0);gpio_set_dir(PIN_A0,GPIO_OUT);
    for(unsigned i=0;i<8;i++){gpio_init(i);gpio_disable_pulls(i);gpio_set_dir(i,GPIO_IN);}
    const unsigned inputs[]={16,17,18,20,21,27,28};
    for(unsigned i=0;i<sizeof(inputs)/sizeof(*inputs);i++){gpio_init(inputs[i]);gpio_disable_pulls(inputs[i]);gpio_set_dir(inputs[i],GPIO_IN);}
}
void revc_emergency(unsigned code) {
    gpio_put(PIN_LINE,0);gpio_put(PIN_DAC,0);gpio_put(PIN_ARM,0);gpio_put(PIN_RESET,0);
    unsigned expected=0;
    atomic_compare_exchange_strong_explicit(&revc_audio.fault,&expected,code,memory_order_release,memory_order_relaxed);
}
static uint8_t read_port(unsigned port) {
    gpio_put(PIN_CS,1);gpio_put(PIN_WR,1);gpio_set_dir_in_masked(255);
    gpio_put(PIN_A0,port);settle();gpio_put(PIN_RD,0);settle();gpio_put(PIN_CS,0);settle();
    uint8_t value=(uint8_t)gpio_get_all();
    gpio_put(PIN_CS,1);settle();gpio_put(PIN_RD,1);settle();return value;
}
static void write_port(unsigned port,uint8_t value) {
    gpio_put(PIN_CS,1);gpio_put(PIN_WR,1);gpio_put(PIN_RD,1);settle();
    gpio_put_masked(255,value);gpio_set_dir_out_masked(255);gpio_put(PIN_A0,port);settle();
    gpio_put(PIN_CS,0);settle();gpio_put(PIN_WR,0);settle();
    gpio_put(PIN_WR,1);settle();gpio_put(PIN_CS,1);busy_wait_us_32(revc_bus_fast?2:20);
}
static int bus_write(uint8_t reg,uint8_t value) {
    if(atomic_load_explicit(&revc_audio.fault,memory_order_acquire)) return -1;
    if(read_port(0)&128){revc_bus.busy_retries++;return 0;}
    if(latched<0){write_port(0,reg);latched=reg;if(read_port(0)&128){revc_bus.busy_retries++;return 0;}}
    if(latched!=reg) return -1;
    write_port(1,value);latched=-1;revc_bus.writes++;return 1;
}
int revc_bus_write(void *unused,uint8_t reg,uint8_t value) {
    (void)unused;uint32_t started=time_us_32();int result=bus_write(reg,value);
    uint32_t elapsed=time_us_32()-started;
    if(elapsed>revc_bus.max_call_us)revc_bus.max_call_us=elapsed;
    return result;
}
bool revc_bus_write_wait(uint8_t r,uint8_t v) {
    uint64_t deadline=time_us_64()+100000;
    do {int result=revc_bus_write(NULL,r,v);if(result) return result==1;} while(time_us_64()<deadline);
    return false;
}
void revc_gates(bool enable) {
    if(!enable){gpio_put(PIN_LINE,0);gpio_put(PIN_DAC,0);return;}
    if(!atomic_load_explicit(&revc_audio.fault,memory_order_acquire)) {
        gpio_put(PIN_DAC,1);gpio_put(PIN_LINE,1);
    }
}
void revc_all_off(void) {
    revc_gates(false);latched=-1;
    for(unsigned c=0;c<3;c++) {
        if(!revc_bus_write_wait(0x28,(uint8_t)c)||!revc_bus_write_wait((uint8_t)(8+c),0)){revc_emergency(10);break;}
    }
}
bool revc_bus_reset(void) {
    revc_gates(false);gpio_put(PIN_CS,1);gpio_put(PIN_WR,1);gpio_put(PIN_RD,1);
    gpio_set_dir_in_masked(255);latched=-1;gpio_put(PIN_RESET,0);busy_wait_ms(2);
    gpio_put(PIN_RESET,1);busy_wait_ms(2);
    if(!revc_bus_write_wait(0x27,0)||!revc_bus_write_wait(7,63)) return false;
    revc_all_off();return !atomic_load(&revc_audio.fault);
}
bool revc_bus_start(void) {
    busy_wait_ms(2);gpio_put(PIN_ARM,1);busy_wait_ms(2);return revc_bus_reset();
}
bool revc_bus_check(void) {
    const uint8_t patterns[]={0,255,85,170,1,128,15,240};
    for(unsigned r=0;r<=4;r+=2) for(unsigned i=0;i<sizeof(patterns);i++) {
        if(!revc_bus_write_wait((uint8_t)r,patterns[i])) return false;
        // The readback address is also a bus write:wait for the previous data.
        // Long diagnostic delays used to mask this requirement.
        uint64_t deadline=time_us_64()+100000u;
        while(read_port(0)&128)if(time_us_64()>=deadline)return false;
        write_port(0,r);if(read_port(1)!=patterns[i]) return false;
    }
    for(unsigned r=0;r<=4;r+=2) if(!revc_bus_write_wait((uint8_t)r,0)) return false;
    return true;
}
