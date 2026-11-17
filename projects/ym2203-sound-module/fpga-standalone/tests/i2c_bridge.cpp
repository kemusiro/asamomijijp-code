// SPDX-License-Identifier: MIT
// Open-drain line simulation at 100 kHz, sampled by a 16 MHz RTL clock.
#include "Vrevc_i2c_stream.h"
#include "verilated.h"
#include <cstdint>
#include <memory>
#include <vector>
static std::unique_ptr<Vrevc_i2c_stream> d;
static uint64_t now_us, busy_until;
static unsigned fraction;
static bool master_scl_low, master_sda_low;
static std::vector<uint8_t> trace;
static void tick(bool realtime=true) {
    if (realtime && ++fraction==16) { ++now_us; fraction=0; }
    d->now_us=now_us; d->event_ready=now_us>=busy_until;
    d->scl_in=!(master_scl_low||d->scl_low);
    d->sda_in=!(master_sda_low||d->sda_low);
    d->clk=0;d->eval();
    if(!d->reset&&d->event_valid&&d->event_ready){trace.push_back(d->event_register);trace.push_back(d->event_value);busy_until=now_us+50;}
    d->clk=1;d->eval();d->clk=0;d->eval();
}
static void wait(unsigned n) { for(unsigned i=0;i<n;++i)tick(); }
static bool high() {
    master_scl_low=false;
    for(unsigned i=0;i<2000000;++i){tick();if(!d->scl_low){wait(80);return true;}}
    return false;
}
static bool start() {
    master_sda_low=false;if(!high())return false;
    master_sda_low=true;wait(80);master_scl_low=true;wait(80);return true;
}
static bool stop() {
    master_scl_low=true;master_sda_low=true;wait(80);
    if(!high())return false;
    master_sda_low=false;wait(80);return true;
}
static bool send(uint8_t b) {
    for(unsigned i=0;i<8;++i){
        master_sda_low=!(b&0x80);wait(64);if(!high())return false;
        master_scl_low=true;wait(16);b<<=1;
    }
    master_sda_low=false;wait(64);if(!high())return false;
    const bool ack=d->sda_low;
    master_scl_low=true;wait(16);return ack;
}
static int receive(bool ack) {
    uint8_t value=0;master_sda_low=false;
    for(unsigned i=0;i<8;++i){
        wait(64);if(!high())return -1;
        value=uint8_t((value<<1)|(!d->sda_low));master_scl_low=true;wait(16);
    }
    master_sda_low=ack;wait(64);if(!high())return -1;
    master_scl_low=true;wait(16);master_sda_low=false;return value;
}
extern "C" {
void wire_destroy(){d.reset();}
void wire_init(){
    d=std::make_unique<Vrevc_i2c_stream>();now_us=busy_until=0;fraction=0;
    master_scl_low=master_sda_low=false;trace.clear();
    d->audio_ok=1;d->prepare_done=1;d->silence_done=1;
    d->reset=1;wait(20);d->reset=0;wait(20);
}
uint64_t wire_now(){return now_us;}
int wire_write(unsigned address,const uint8_t *p,unsigned n){
    if(!start())return -1;
    if(!send(uint8_t(address<<1))){stop();return -2;}
    for(unsigned i=0;i<n;++i)if(!send(p[i])){stop();return -3;}
    return stop()?int(n):-4;
}
int wire_read(unsigned address,uint8_t *p,unsigned n){
    if(!start())return -1;
    if(!send(uint8_t((address<<1)|1))){stop();return -2;}
    for(unsigned i=0;i<n;++i){int b=receive(i+1<n);if(b<0){stop();return -3;}p[i]=uint8_t(b);}
    return stop()?int(n):-4;
}
void wire_advance(uint64_t delta){
    const uint64_t until=now_us+delta;
    while(now_us<until){now_us+=until-now_us>20?20:until-now_us;for(unsigned i=0;i<4;++i)tick(false);}
}
unsigned wire_trace_count(){return unsigned(trace.size()/2);}
const uint8_t *wire_trace(){return trace.data();}
unsigned wire_gate(){return d->gate_request;}
void wire_controls(unsigned audio,unsigned other,unsigned prep_done,unsigned silence_done){
    d->audio_ok=audio;d->other_owned=other;d->prepare_done=prep_done;d->silence_done=silence_done;
}
void wire_glitch(){
    master_sda_low=true;wait(1);master_sda_low=false;wait(40);
}
}
