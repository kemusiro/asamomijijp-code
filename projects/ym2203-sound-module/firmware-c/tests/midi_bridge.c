// SPDX-License-Identifier: MIT
// Native MIDI model: no SDK, GPIO or USB hardware. Real midi.c runs unchanged.
#include "midi.h"
#include <string.h>
static revc_midi m;
static uint64_t now,busy_until;
static uint8_t trace[16384];
static unsigned count,busy_calls;
static int latched_reg=-1,latched_value=-1;
static int writer(void *ctx,uint8_t reg,uint8_t value){
    (void)ctx;
    if(!revc_valid_register(reg,value)||count+2>sizeof(trace))return -1;
    if(latched_reg>=0&&(latched_reg!=reg||latched_value!=value))return -1;
    if(busy_calls||now<busy_until){
        latched_reg=reg;latched_value=value;if(busy_calls)busy_calls--;return 0;
    }
    trace[count++]=reg;trace[count++]=value;latched_reg=latched_value=-1;busy_until=now+50;return 1;
}
void mm_init(void){revc_midi_init(&m);now=busy_until=count=busy_calls=0;latched_reg=latched_value=-1;}
unsigned mm_packet(const uint8_t p[4],bool blocked){return revc_midi_message(&m,p,blocked);}
void mm_tick(void){revc_midi_tick(&m,now,writer,0);}
void mm_advance(uint64_t us){uint64_t end=now+us;while(now<end){now+=end-now>20?20:end-now;mm_tick();}}
void mm_busy(unsigned n){busy_calls=n;}
void mm_cancel(void){revc_midi_cancel(&m);latched_reg=latched_value=-1;}
unsigned mm_get(unsigned which){
    switch(which){case 0:return m.state;case 1:return m.owned;case 2:return m.gate;
    case 3:return revc_midi_mask(&m);case 4:return count/2;case 5:return m.rejected;
    case 6:return m.invalid;case 7:return m.panics;case 8:return m.inflight;
    case 9:return m.step;case 10:return m.setup;case 11:return m.received;
    default:return 0;}
}
unsigned mm_note(unsigned v){return m.notes[v];}
const uint8_t *mm_trace(void){return trace;}
