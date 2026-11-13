// SPDX-License-Identifier: MIT
#include "stream.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static void put16(uint8_t *p,unsigned n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static unsigned queued(const revc_stream *s){return s->write-s->read;}
bool revc_stream_owned(const revc_stream *s){return s->state==STREAM_PREFILL||s->state==STREAM_RUNNING;}
void revc_stream_init(revc_stream *s){memset(s,0,sizeof(*s));s->ack_seq=UINT32_MAX;s->min_queue=REVC_QUEUE_CAPACITY;}
void revc_stream_stop(revc_stream *s){s->state=STREAM_STOPPED;s->read=s->write;s->sealed=false;s->error=0;}
void revc_stream_fail(revc_stream *s,unsigned error){s->state=STREAM_FAULT;s->error=(uint8_t)error;s->read=s->write;}
static void expire(revc_stream *s,uint64_t now){if(revc_stream_owned(s)&&now-s->lease_us>=REVC_LEASE_US)revc_stream_fail(s,S_LEASE);}
void revc_stream_command(revc_stream *s,const uint8_t *p,unsigned n,uint64_t now,revc_prepare prepare,void *ctx){
    s->action=S_ACTION_NONE;expire(s,now);
    if(n<16||n>REVC_PACKET_MAX||p[0]!='Y'||p[1]!='2'||p[2]!=2||p[10]||p[11]){s->result=S_SHAPE;return;}
    unsigned len=(unsigned)p[8]|(unsigned)p[9]<<8;
    if(len>REVC_PACKET_PAYLOAD||n!=16u+len){s->result=S_SHAPE;return;}
    if(revc_crc32(p,n-4)!=get32(p+n-4)){s->result=S_CRC;return;}
    uint32_t seq=get32(p+4);unsigned op=p[3];const uint8_t *payload=p+12;s->ack_seq=seq;
    if(s->have_last&&seq==s->last_seq){
        s->result=n==s->last_length&&!memcmp(p,s->last_packet,n)?S_OK:S_SEQUENCE;return;
    }
    // A valid STOP may resynchronise a host after an uncertain response.
    if(seq!=s->next_seq&&op!=S_STOP){s->result=S_SEQUENCE;return;}
    s->result=S_OK;
    if(op==S_STOP){if(len){s->result=S_SHAPE;return;}revc_stream_stop(s);s->action=S_ACTION_STOP;}
    else if(op==S_PING){if(len){s->result=S_SHAPE;return;}}
    else if(op==S_BEGIN){
        if(len!=20||memcmp(payload,"WYM1",4)){s->result=S_SHAPE;return;}
        uint32_t count=get32(payload+4),period=get32(payload+8);
        if(!count||count>WYM1_MAX_EVENTS||!period||get32(payload+12)!=4000000){s->result=S_DATA;return;}
        if(revc_stream_owned(s)||s->state==STREAM_FAULT){s->result=S_STATE;return;}
        unsigned preparation=prepare?prepare(ctx):S_OK;
        if(preparation!=S_OK){
            s->result=(uint8_t)preparation;
            if(preparation==S_AUDIO)revc_stream_fail(s,S_AUDIO);
            return;
        }
        s->read=s->write=s->received=s->executed=s->last_ms=s->max_late_us=0;
        memset(s->late_hist,0,sizeof(s->late_hist));s->min_queue=REVC_QUEUE_CAPACITY;
        s->total=count;s->period=period;s->expected_crc=get32(payload+16);
        s->crc=revc_crc32_append(~0u,payload,16);s->sealed=false;s->state=STREAM_PREFILL;s->error=0;
    }
    else if(op==S_PUSH){
        if(!len||len%6){s->result=S_SHAPE;return;}
        unsigned count=len/6;
        if(!revc_stream_owned(s)||s->sealed){s->result=S_STATE;return;}
        if(count>s->total-s->received){s->result=S_DATA;return;}
        if(count>REVC_QUEUE_CAPACITY-queued(s)){s->result=S_FULL;return;}
        uint32_t last=s->last_ms;
        for(unsigned i=0;i<count;i++){
            const uint8_t *e=payload+6*i;uint32_t ms=get32(e);
            if(ms<last||ms>s->period||!revc_valid_register(e[4],e[5])){s->result=S_DATA;return;}last=ms;
        }
        // Publish only after every event and available slot has been checked.
        for(unsigned i=0;i<count;i++){
            const uint8_t *e=payload+6*i;s->queue[(s->write+i)&(REVC_QUEUE_CAPACITY-1)]=(revc_event){get32(e),e[4],e[5]};
        }
        s->write+=count;s->received+=count;s->last_ms=last;s->crc=revc_crc32_append(s->crc,payload,len);
    }
    else if(op==S_PLAY){
        unsigned required=s->total<REVC_PREFILL?s->total:REVC_PREFILL;
        if(len||s->state!=STREAM_PREFILL||queued(s)<required){s->result=S_STATE;return;}
        s->origin_us=now+250000;s->state=STREAM_RUNNING;s->min_queue=queued(s);
    }
    else if(op==S_KEEP){if(len||!revc_stream_owned(s)){s->result=S_STATE;return;}}
    else if(op==S_SEAL){
        if(len||!revc_stream_owned(s)||s->received!=s->total){s->result=S_STATE;return;}
        if((~s->crc)!=s->expected_crc){revc_stream_fail(s,S_INTEGRITY);s->result=S_INTEGRITY;return;}
        s->sealed=true;
    }
    else{s->result=S_SHAPE;return;}
    s->last_seq=seq;s->last_length=n;memcpy(s->last_packet,p,n);s->have_last=true;s->next_seq=seq+1u;
    if(op!=S_PING&&revc_stream_owned(s))s->lease_us=now;
}
void revc_stream_tick(revc_stream *s,uint64_t now,revc_writer writer,void *ctx){
    expire(s,now);
    if(s->state!=STREAM_RUNNING||now<s->origin_us)return;
    unsigned count=queued(s);
    if(count<s->min_queue)s->min_queue=count;
    if(!count){
        if(s->received<s->total){revc_stream_fail(s,S_UNDERRUN);return;}
        if(s->sealed&&s->executed==s->total&&now-s->origin_us>=(uint64_t)s->period*1000)s->state=STREAM_DONE;
        return;
    }
    const revc_event *e=&s->queue[s->read&(REVC_QUEUE_CAPACITY-1)];uint64_t due=s->origin_us+(uint64_t)e->ms*1000;
    if(now<due)return;
    uint64_t late=now-due;
    if(late>REVC_LATE_US){revc_stream_fail(s,S_LATE);return;}
    int applied=writer(ctx,e->reg,e->value);
    if(applied<0){revc_stream_fail(s,S_IO);return;}
    if(!applied)return;
    s->read++;s->executed++;
    if(late>s->max_late_us)s->max_late_us=(uint32_t)late;
    s->late_hist[late<1000?0:late<5000?1:late<10000?2:late<20000?3:4]++;
}
void revc_stream_status(revc_stream *s,uint8_t out[REVC_STATUS_SIZE],uint64_t now,bool audio_ok){
    memset(out,0,REVC_STATUS_SIZE);memcpy(out,"YM22S002",8);out[8]=2;out[9]=s->state;out[10]=s->result;
    out[11]=1u|(audio_ok?2u:0u)|(s->state==STREAM_RUNNING?4u:0u)|(s->sealed?8u:0u)|(revc_stream_owned(s)?16u:0u)|(s->error==S_LEASE?32u:0u);
    put32(out+12,s->ack_seq);put32(out+16,s->next_seq);put32(out+20,s->received);put32(out+24,s->executed);
    put32(out+28,s->total);put32(out+32,s->period);put16(out+36,queued(s));put16(out+38,REVC_QUEUE_CAPACITY-queued(s));
    put32(out+40,s->state>=STREAM_RUNNING&&now>=s->origin_us?(uint32_t)((now-s->origin_us)/1000):0);
    put16(out+44,s->error);put16(out+46,s->min_queue);put32(out+48,s->max_late_us);put32(out+52,~s->crc);
    put32(out+56,s->generation++);put32(out+60,revc_crc32(out,60));
}
