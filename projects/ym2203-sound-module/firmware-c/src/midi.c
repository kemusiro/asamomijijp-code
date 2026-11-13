// SPDX-License-Identifier: MIT
#include "midi.h"
#include <string.h>
#include "midi_pitch.h"

void revc_midi_cancel(revc_midi *m){
    memset(m->notes,REVC_MIDI_OFF,sizeof(m->notes));
    memset(m->applied_notes,REVC_MIDI_OFF,sizeof(m->applied_notes));
    memset(m->revision,0,sizeof(m->revision));memset(m->done_revision,0,sizeof(m->done_revision));
    m->state=MIDI_IDLE;m->owned=m->gate=m->inflight=m->job=m->releasing=false;
    m->setup=m->cursor=m->step=0;m->ready_at=m->release_at=m->io_since=0;
}
void revc_midi_init(revc_midi *m){memset(m,0,sizeof(*m));revc_midi_cancel(m);}
bool revc_midi_pitch(unsigned voice,unsigned note,uint8_t *first,uint8_t *second){
    if(voice>=6||note>=128)return false;
    if(voice<3){if(midi_high[note]==255)return false;*first=midi_high[note];*second=midi_low[note];}
    else{unsigned p=midi_period[note];if(!p)return false;*first=(uint8_t)p;*second=(uint8_t)(p>>8);}
    return true;
}
unsigned revc_midi_mask(const revc_midi *m){
    unsigned mask=0;for(unsigned i=0;i<6;i++)if(m->notes[i]!=REVC_MIDI_OFF)mask|=1u<<i;return mask;
}
unsigned revc_midi_message(revc_midi *m,const uint8_t p[4],bool blocked){
    m->received++;
    if(p[0]>>4){m->ignored++;return MIDI_NONE;}
    unsigned cin=p[0]&15,status=p[1],voice=status&15;
    if(cin==15&&status==255){if(m->owned){m->panics++;return MIDI_PANIC;}return MIDI_NONE;}
    if(cin!=8&&cin!=9&&cin!=11){m->ignored++;return MIDI_NONE;}
    if(status>>4!=cin||p[2]>127||p[3]>127){
        m->invalid++;if(m->owned){m->panics++;return MIDI_PANIC;}return MIDI_NONE;
    }
    if(voice>=6){m->ignored++;return MIDI_NONE;}
    if(cin==11&&p[2]==120){if(m->owned){m->panics++;return MIDI_PANIC;}return MIDI_NONE;}
    bool on=cin==9&&p[3]!=0;
    if(cin==11&&p[2]!=123){m->ignored++;return MIDI_NONE;}
    unsigned note=p[2];
    if(cin==11)note=REVC_MIDI_OFF;
    uint8_t first,second;
    if(on&&!revc_midi_pitch(voice,note,&first,&second)){on=false;note=REVC_MIDI_OFF;}
    if(!on&&(!m->owned||(note!=REVC_MIDI_OFF&&note!=m->notes[voice])))return MIDI_NONE;
    unsigned result=MIDI_NONE;
    if(on&&!m->owned){
        if(blocked||m->state==MIDI_FAULT){m->rejected++;return MIDI_NONE;}
        revc_midi_cancel(m);m->owned=true;m->state=MIDI_SETUP;result=MIDI_START;
    }
    if(m->state==MIDI_FAULT)return MIDI_NONE;
    m->notes[voice]=on?(uint8_t)note:REVC_MIDI_OFF;m->revision[voice]++;m->releasing=false;
    return result;
}
static void setup_register(unsigned index,uint8_t *r,uint8_t *v){
    static const uint8_t bases[]={0x30,0x40,0x50,0x60,0x70,0x80,0x90};
    static const uint8_t values[]={1,127,31,0,0,15,0};
    if(index==87){*r=7;*v=0x38;return;}
    unsigned ch=index/29,part=index%29;
    if(part==28){*r=(uint8_t)(0xb0+ch);*v=7;return;}
    unsigned slot=part/7,group=part%7;*r=(uint8_t)(bases[group]+slot*4+ch);
    *v=group==1&&slot==0?0:values[group];
}
static bool pending(const revc_midi *m){
    for(unsigned i=0;i<6;i++)if(m->revision[i]!=m->done_revision[i])return true;
    return false;
}
static void finish_write(revc_midi *m){
    if(m->state==MIDI_READY&&m->step==3&&m->note!=REVC_MIDI_OFF&&m->job_revision==m->revision[m->voice])m->gate=true;
    m->applied++;m->inflight=false;m->io_since=0;
    if(m->state==MIDI_SETUP){m->setup++;return;}
    if(m->step==3||m->note==REVC_MIDI_OFF){
        m->applied_notes[m->voice]=m->note;m->done_revision[m->voice]=m->job_revision;
        m->cursor=(uint8_t)((m->voice+1)%6);m->job=false;
    }else m->step++;
}
void revc_midi_tick(revc_midi *m,uint64_t now,revc_writer writer,void *ctx){
    if(!m->owned||m->state==MIDI_FAULT)return;
    if(m->inflight){
        int result=writer(ctx,m->reg,m->value);
        if(result<0||(!result&&now-m->io_since>=100000u)){m->state=MIDI_FAULT;m->gate=false;return;}
        if(result)finish_write(m);
        return;
    }
    if(m->state==MIDI_SETUP){
        if(m->setup==REVC_MIDI_SETUP_WRITES){m->state=MIDI_PRIME;m->ready_at=now+REVC_MIDI_PRIME_US;return;}
        setup_register(m->setup,&m->reg,&m->value);
    }else{
        if(m->state==MIDI_PRIME){if(now<m->ready_at)return;m->state=MIDI_READY;}
        // A superseded job may be dropped only between complete register writes.
        if(m->job&&m->job_revision!=m->revision[m->voice])m->job=false;
        if(!m->job){
            unsigned i=0;
            for(;i<6;i++){unsigned v=(m->cursor+i)%6;if(m->revision[v]!=m->done_revision[v]){
                m->voice=(uint8_t)v;m->note=m->notes[v];m->job_revision=m->revision[v];m->step=0;m->job=true;break;
            }}
            if(!m->job){
                if(!revc_midi_mask(m)&&!pending(m)){
                    if(!m->releasing){m->releasing=true;m->release_at=now+REVC_MIDI_RELEASE_US;}
                    if(now>=m->release_at)revc_midi_cancel(m);
                }
                return;
            }
        }
        unsigned v=m->voice,ch=v<3?v:v-3;
        uint8_t a=0,b=0;if(m->note!=REVC_MIDI_OFF)revc_midi_pitch(v,m->note,&a,&b);
        if(v<3){
            m->reg=m->step==0||m->step==3?0x28:(uint8_t)((m->step==1?0xa4:0xa0)+ch);
            m->value=m->step==0?(uint8_t)ch:m->step==1?a:m->step==2?b:(uint8_t)(0xf0|ch);
        }else{
            m->reg=m->step==0||m->step==3?(uint8_t)(8+ch):(uint8_t)(2*ch+(m->step==2));
            m->value=m->step==0?0:m->step==1?a:m->step==2?b:7;
        }
    }
    m->inflight=true;m->io_since=now;
    int result=writer(ctx,m->reg,m->value);
    if(result<0){m->state=MIDI_FAULT;m->gate=false;return;}
    if(result)finish_write(m);
}
