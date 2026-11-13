// SPDX-License-Identifier: MIT
// Native-only harness. Firmware never includes these globals or model clocks.
#include "stream.h"
#include "transport.h"
#include <string.h>
static revc_stream s;
static revc_transport t;
static uint64_t now,busy_until;
static unsigned service_us,trace_n,preparation_result;
static unsigned prepare(void *ctx){(void)ctx;return preparation_result;}
static uint8_t trace[2*WYM1_MAX_EVENTS];
static int writer(void *ctx,uint8_t r,uint8_t v){
    (void)ctx;if(now<busy_until)return 0;
    if(trace_n>=sizeof(trace))return -1;
    trace[trace_n++]=r;trace[trace_n++]=v;busy_until=now+service_us;return 1;
}
void model_init(unsigned cost){revc_stream_init(&s);revc_transport_init(&t);now=busy_until=0;trace_n=0;service_us=cost;preparation_result=S_OK;}
void model_advance(uint64_t delta){
    uint64_t until=now+delta;
    while(now<until){now=until-now>20?now+20:until;revc_stream_tick(&s,now,writer,0);}
}
uint64_t model_now(void){return now;}
void model_clock(uint64_t value){now=value;}
void model_command(const uint8_t *p,unsigned n){revc_stream_command(&s,p,n,now,prepare,0);}
void model_status(uint8_t *p){revc_stream_status(&s,p,now,true);}
unsigned model_trace_count(void){return trace_n/2;}
const uint8_t *model_trace(void){return trace;}
void model_sequence(uint32_t n){s.next_seq=n;s.have_last=false;}
void model_transport_byte(unsigned b){revc_transport_byte(&t,(uint8_t)b);}
void model_transport_finish(void){revc_transport_finish(&t);}
int model_transport_pop(uint8_t *out){return revc_transport_pop(&t,out);}
void model_transport_publish(const uint8_t *p){revc_transport_publish(&t,p);}
unsigned model_transport_read(void){return revc_transport_read(&t);}

void model_prepare_result(unsigned code){preparation_result=code;}
