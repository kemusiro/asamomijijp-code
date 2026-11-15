// SPDX-License-Identifier: MIT
#include "diagnostic.h"
#include <stddef.h>
#include <stdatomic.h>
#include <string.h>
static uint8_t data[REVC_DIAG_BYTES];
static atomic_uint state;
static uint64_t origin_us;
static uint32_t start_us,trace_count,raw_frames,chunk_frames,flags;
static void put32(unsigned offset,uint32_t v){for(unsigned b=0;b<4;b++)data[offset+b]=(uint8_t)(v>>(8*b));}
void revc_diag_reset(void){atomic_store(&state,0);memset(data,0,sizeof(data));trace_count=raw_frames=chunk_frames=flags=0;}
bool revc_diag_arm(uint64_t origin,unsigned second,unsigned gain,bool fast,uint32_t crc,uint32_t events){
    if(second<30||second>33||gain>16||atomic_load(&state)!=0)return false;
    origin_us=origin;start_us=second*1000000u;
    memcpy(data,"RCD1",4);put32(4,REVC_DIAG_HEADER);put32(8,REVC_DIAG_BYTES);
    put32(12,4000000);put32(16,72);put32(20,625);put32(24,REVC_DIAG_BLOCKS);
    put32(36,REVC_DIAG_HEADER);put32(40,REVC_DIAG_RAW_OFFSET);put32(44,6);put32(48,3);
    put32(52,start_us);put32(64,gain);put32(68,fast);put32(72,crc);put32(76,events);
    atomic_store_explicit(&state,1,memory_order_release);return true;
}
unsigned revc_diag_state(void){return atomic_load_explicit(&state,memory_order_acquire);}
void revc_diag_abort(void){unsigned s=revc_diag_state();if(s==1||s==2)atomic_store_explicit(&state,0,memory_order_release);}
void revc_diag_trace(uint64_t now,uint8_t reg,uint8_t value){
    unsigned s=revc_diag_state();if((s!=1&&s!=2)||now<origin_us)return;
    if(trace_count==REVC_DIAG_TRACE_CAPACITY){flags|=1;return;}
    unsigned offset=REVC_DIAG_HEADER+6u*trace_count;
    put32(offset,(uint32_t)(now-origin_us));data[offset+4]=reg;data[offset+5]=value;trace_count++;
}
void revc_diag_rx(const uint32_t *raw,uint64_t now){revc_diag_rx_frames(raw,625,now);}
void revc_diag_rx_frames(const uint32_t *raw,unsigned frames,uint64_t now){
    if(revc_diag_state()!=1)return;
    if((frames!=125&&frames!=625)||(chunk_frames&&frames!=chunk_frames)){revc_diag_abort();return;}
    if(now<origin_us+start_us+(uint64_t)frames*18u)return;
    chunk_frames=frames;
    uint32_t relative=(uint32_t)(now-origin_us);
    unsigned offset=REVC_DIAG_RAW_OFFSET+raw_frames*3u;
    for(unsigned i=0;i<frames;i++){
        uint32_t word=raw[i]>>8;
        for(unsigned b=0;b<3;b++)data[offset++]=(uint8_t)(word>>(8*b));
    }
    raw_frames+=frames;
    if(raw_frames==625)put32(56,relative);
    put32(60,relative);
    if(raw_frames==REVC_DIAG_FRAMES){
        unsigned expected=1;atomic_compare_exchange_strong_explicit(&state,&expected,2,memory_order_release,memory_order_relaxed);
    }
}
bool revc_diag_seal(void){
    if(revc_diag_state()!=2)return false;
    put32(28,raw_frames);put32(32,trace_count);put32(80,flags);
    atomic_store_explicit(&state,3,memory_order_release);return true;
}
const uint8_t *revc_diag_data(void){return revc_diag_state()==3?data:NULL;}
bool revc_parse_capture(const char *s,unsigned *second){
    if(strlen(s)!=10||strncmp(s,"capture 3",9)||s[9]<'0'||s[9]>'3')return false;
    *second=30u+(unsigned)(s[9]-'0');return true;
}
