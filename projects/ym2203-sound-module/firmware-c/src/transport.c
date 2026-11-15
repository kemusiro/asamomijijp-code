// SPDX-License-Identifier: MIT
#include "transport.h"
#include <string.h>
void revc_transport_init(revc_transport *t){memset(t,0,sizeof(*t));}
void revc_transport_byte(revc_transport *t,uint8_t value){
    if(t->length<REVC_PACKET_MAX)t->assembling[t->length++]=value;else t->oversized=true;
}
void revc_transport_finish(revc_transport *t){
    if(t->length||t->oversized){
        unsigned h=atomic_load_explicit(&t->head,memory_order_relaxed),tail=atomic_load_explicit(&t->tail,memory_order_acquire);
        if(t->oversized||h-tail>=4)atomic_fetch_add(&t->overflow,1);
        else{memcpy(t->packets[h&3],t->assembling,t->length);t->lengths[h&3]=t->length;atomic_store_explicit(&t->head,h+1,memory_order_release);}
    }
    t->length=0;t->oversized=false;t->reading=false;t->read_pos=0;
}
int revc_transport_pop(revc_transport *t,uint8_t out[REVC_PACKET_MAX]){
    if(atomic_exchange(&t->overflow,0))return -1;
    unsigned tail=atomic_load_explicit(&t->tail,memory_order_relaxed),h=atomic_load_explicit(&t->head,memory_order_acquire);
    if(tail==h)return 0;
    unsigned n=t->lengths[tail&3];memcpy(out,t->packets[tail&3],n);
    atomic_store_explicit(&t->tail,tail+1,memory_order_release);return (int)n;
}
void revc_transport_publish(revc_transport *t,const uint8_t status[REVC_STATUS_SIZE]){
    unsigned next=atomic_load_explicit(&t->current_status,memory_order_relaxed)^1u;
    memcpy(t->status[next],status,REVC_STATUS_SIZE);atomic_store_explicit(&t->current_status,next,memory_order_release);
}
uint8_t revc_transport_read(revc_transport *t){
    // Called only from the core0 ISR. Core0 main cannot overwrite the source
    // while this first-request copy is in progress. Subsequent bytes are pinned.
    if(!t->reading){unsigned i=atomic_load_explicit(&t->current_status,memory_order_acquire);memcpy(t->read_status,t->status[i],REVC_STATUS_SIZE);t->read_pos=0;t->reading=true;}
    return t->read_pos<REVC_STATUS_SIZE?t->read_status[t->read_pos++]:255;
}
