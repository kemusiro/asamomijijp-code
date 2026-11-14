// SPDX-License-Identifier: MIT
#include "wym1.h"
#include <string.h>
static uint32_t le32(const uint8_t *p) {
    return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
bool revc_valid_register(uint8_t r, uint8_t v) {
    if(r<=13) {
        if(r==1||r==3||r==5||r==13) return v<=15;
        if(r==6) return v<=31;
        if(r==7) return v<=63;
        if(r>=8&&r<=10) return v<=31;
        return true;
    }
    if(r==0x28) return !(v&12) && (v&3)!=3;
    if(r==0x24||r==0x26) return true;
    if(r==0x25) return v<=3;
    if(r==0x27) return v<=63;
    if(r>=0x30&&r<=0x9e&&(r&3)!=3) {
        unsigned g=r>>4,mask=g<=4?127:g==5?223:g==6?159:g==7?31:g==8?255:15;
        return !(v&~mask);
    }
    if(r>=0xa0&&r<=0xa2) return true;
    if((r>=0xa4&&r<=0xa6)||(r>=0xb0&&r<=0xb2)) return v<=63;
    return false;
}
void wym1_event(const wym1_file *f,uint32_t i,uint32_t *ms,uint8_t *r,uint8_t *v) {
    const uint8_t *p=f->bytes+16u+6u*i; *ms=le32(p);*r=p[4];*v=p[5];
}
wym1_error wym1_open(wym1_file *out,const uint8_t *data,size_t size) {
    if(size<16||memcmp(data,"WYM1",4)) return WYM_SHAPE;
    uint32_t n=le32(data+4),period=le32(data+8);
    if(!n||n>WYM1_MAX_EVENTS||!period||size!=16u+6u*n) return WYM_SHAPE;
    if(le32(data+12)!=4000000u) return WYM_CLOCK;
    wym1_file candidate={data,n,period};uint32_t last=0;
    for(uint32_t i=0;i<n;i++) {
        uint32_t t;uint8_t r,v;wym1_event(&candidate,i,&t,&r,&v);
        if(t<last||t>period) return WYM_TIME;
        if(!revc_valid_register(r,v)) return WYM_REGISTER;
        last=t;
    }
    *out=candidate;return WYM_OK;
}
uint32_t revc_crc32_append(uint32_t c,const uint8_t *data,size_t n) {
    while(n--) {c^=*data++;for(unsigned b=0;b<8;b++) c=(c>>1)^((0u-(c&1u))&0xedb88320u);}
    return c;
}
uint32_t revc_crc32(const uint8_t *data,size_t n){return ~revc_crc32_append(~0u,data,n);}
static int32_t floor_div(int32_t value,int32_t divisor) {
    return value>=0?value/divisor:-((-value+divisor-1)/divisor);
}
uint32_t revc_convert(const uint32_t *input,uint32_t *output,uint32_t *peak_out) {
    return revc_convert_gain(input,output,peak_out,8,8);
}
uint32_t revc_convert_gain(const uint32_t *input,uint32_t *output,uint32_t *peak_out,unsigned start,unsigned end) {
    return revc_convert_gain_ex(input,output,peak_out,start,end,NULL);
}
static uint32_t convert_frames(const uint32_t *input,uint32_t *output,unsigned frames,uint32_t *peak_out,unsigned start,unsigned end,uint32_t *clipped) {
    if(clipped)*clipped=0;
    if(start>2048||end>2048){memset(output,0,frames*sizeof(*output));*peak_out=0;return 4;}
    uint32_t position=0,flags=0,peak=0;
    for(unsigned i=0;i<frames;i++,position+=125) {
        unsigned index=position/108,fraction=position%108;
        uint32_t wa=(input[index]>>19)&8191,wb=(input[index+1]>>19)&8191;
        unsigned ea=wa>>10,eb=wb>>10;int32_t value=0;
        if(!ea||!eb) flags|=1;
        else {
            int32_t a=((int32_t)(wa&1023)-512)*(1<<(ea-1));
            int32_t b=((int32_t)(wb&1023)-512)*(1<<(eb-1));
            value=floor_div(a*(int32_t)(108-fraction)+b*(int32_t)fraction,108);
            unsigned gain=start==end?end:(start*(frames-1u-i)+end*i)/(frames-1u);
            value=floor_div(value*(int32_t)gain,1024);
            if(value>REVC_PCM_MAX){value=REVC_PCM_MAX;flags|=2;if(clipped)(*clipped)++;}
            if(value<REVC_PCM_MIN){value=REVC_PCM_MIN;flags|=2;if(clipped)(*clipped)++;}
        }
        uint32_t mag=(uint32_t)(value<0?-value:value);if(mag>peak) peak=mag;
        output[i]=(uint32_t)(uint16_t)value<<16;
    }
    *peak_out=peak;return flags;
}
uint32_t revc_convert_gain_ex(const uint32_t *input,uint32_t *output,uint32_t *peak,unsigned start,unsigned end,uint32_t *clipped) {
    if(start>16||end>16)return convert_frames(input,output,REVC_OUTPUT_FRAMES,peak,2049,2049,clipped);
    return convert_frames(input,output,REVC_OUTPUT_FRAMES,peak,start*128u,end*128u,clipped);
}
uint32_t revc_convert_stream(const uint32_t *input,uint32_t *output,uint32_t *peak,unsigned start,unsigned end,uint32_t *clipped) {
    return convert_frames(input,output,REVC_STREAM_OUTPUT_FRAMES,peak,start,end,clipped);
}
bool revc_gain_step(revc_gain_ramp *r,unsigned eighths,unsigned *start,unsigned *end){
    if(eighths>16)return false;
    unsigned target=eighths*128u;
    if(target!=r->target){r->start=r->current;r->target=target;r->step=0;}
    *start=r->current;
    if(r->step<5){r->step++;r->current=(r->start*(5u-r->step)+r->target*r->step)/5u;}
    *end=r->current;return true;
}
bool revc_find_bad_frame(const uint32_t *raw,unsigned frames,revc_bad_frame *out){
    for(unsigned i=0;i<frames;i++)if(!((raw[i]>>29)&7u)){
        *out=(revc_bad_frame){i,raw[i],i?raw[i-1]:0,i+1<frames?raw[i+1]:0};return true;
    }
    return false;
}
int revc_tx_slot(revc_tx_cursor *c,uint32_t produced){
    if(!c->pending){c->consumed++;c->pending=true;}
    uint32_t available=produced-c->consumed;
    if(available>7)return -2;
    if(available<2)return -1;
    c->pending=false;return (int)((c->consumed+1u)&7u);
}
void revc_player_start(revc_player *p,const wym1_file *f,uint64_t origin) {
    memset(p,0,sizeof(*p));p->file=f;p->origin_us=origin;p->state=PLAYER_RUNNING;
}
void revc_player_stop(revc_player *p) {
    if(p->state==PLAYER_RUNNING) p->state=PLAYER_STOPPED;
}
void revc_player_tick(revc_player *p,uint64_t now,revc_writer write,void *ctx) {
    if(p->state!=PLAYER_RUNNING||now<p->origin_us) return;
    if(p->index==p->file->count) {
        if(now-p->origin_us>=(uint64_t)p->file->period_ms*1000u) p->state=PLAYER_DONE;
        return;
    }
    uint32_t t;uint8_t r,v;wym1_event(p->file,p->index,&t,&r,&v);
    uint64_t due=p->origin_us+(uint64_t)t*1000u;
    if(now<due) return;
    uint64_t late=now-due;
    if(late>REVC_LATE_US){p->state=PLAYER_FAULT;return;}
    int result=write(ctx,r,v);
    if(result<0){p->state=PLAYER_FAULT;return;}
    if(!result) return;
    if(late>p->max_late_us) p->max_late_us=(uint32_t)late;
    p->late_hist[late<1000?0:late<5000?1:late<10000?2:late<20000?3:4]++;
    p->index++;
}

bool revc_usb_alive(revc_usb_guard *g,uint64_t now,uint16_t sof,bool connected) {
    if(!connected){g->valid=false;return false;}
    sof&=2047u;
    if(!g->valid||g->sof!=sof){g->last_progress_us=now;g->sof=sof;g->valid=true;}
    return now-g->last_progress_us<250000u;
}

uint32_t revc_i2s_div256(uint32_t system_hz,uint32_t elapsed_us) {
    //640 short DMA blocks=1.44s;64 PIO cycles per stereo output frame.
    if(system_hz<100000000u||system_hz>300000000u||elapsed_us<1000000u||elapsed_us>2000000u)return 0;
    const uint64_t denominator=(uint64_t)REVC_STREAM_OUTPUT_FRAMES*REVC_CLOCK_BLOCKS*64u*1000000u;
    uint64_t numerator=(uint64_t)system_hz*256u*elapsed_us;
    uint32_t divider=(uint32_t)((numerator+denominator/2u)/denominator);
    uint32_t nominal=(uint32_t)(((uint64_t)system_hz*256u+1536000u)/3072000u);
    if(divider<nominal-nominal/200u||divider>nominal+nominal/200u)return 0;
    return divider;
}

uint32_t revc_i2s_div256_carry(uint32_t system_hz,uint32_t elapsed_us,uint64_t *remainder){
    const uint64_t denominator=(uint64_t)REVC_STREAM_OUTPUT_FRAMES*REVC_CLOCK_BLOCKS*64u*1000000u;
    if(!remainder||*remainder>=denominator||!revc_i2s_div256(system_hz,elapsed_us))return 0;
    uint64_t numerator=(uint64_t)system_hz*256u*elapsed_us+*remainder;
    uint32_t divider=(uint32_t)(numerator/denominator);
    uint32_t nominal=(uint32_t)(((uint64_t)system_hz*256u+1536000u)/3072000u);
    if(divider<nominal-nominal/200u||divider>nominal+nominal/200u)return 0;
    *remainder=numerator%denominator;
    return divider;
}

bool revc_parse_fm_gain(const char *command,unsigned *gain) {
    size_t n=strlen(command);
    if(n<4||n>5||strncmp(command,"fm ",3)||command[3]<'0'||command[3]>'9')return false;
    unsigned value=(unsigned)(command[3]-'0');
    if(n==5){if(command[3]!='1'||command[4]<'0'||command[4]>'6')return false;value=10u+(unsigned)(command[4]-'0');}
    *gain=value;return true;
}
