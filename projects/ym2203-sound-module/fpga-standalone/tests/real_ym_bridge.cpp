// SPDX-License-Identifier: MIT
// Cycle-accurate two-clock harness with a bus/serial behavioral peripheral.
// This is NOT a YM2203 sound synthesizer or an analog/electrical model.
#include <memory>
#ifdef F1_USB
#include "Vrevc_usb_ym_top.h"
using Vrevc_real_ym_top=Vrevc_usb_ym_top;
#include "usb_host.h"
#include "si5351_fixture.h"
static std::unique_ptr<Si5351Fixture> si;
static UsbHost usb;
static std::deque<unsigned> auto_symbols;
static unsigned auto_repeat,auto_frame;
static uint64_t auto_next;
static bool auto_sof,usb_pause;
#elif defined(F1_CLOCKED)
#include "Vrevc_clocked_ym_top.h"
using Vrevc_real_ym_top=Vrevc_clocked_ym_top;
#include "si5351_fixture.h"
static std::unique_ptr<Si5351Fixture> si;
#else
#include "Vrevc_real_ym_top.h"
#endif
#include "verilated.h"
#include <array>
#include <cstdint>
#include <memory>
#include <vector>
static std::unique_ptr<Vrevc_real_ym_top> d;
// 12.288GHz integer time grid: control half-period128, audio half-period125.
static uint64_t time_tick,next_c,next_a,busy_until,fm_base,last_frame;
static bool run_c,run_a,master_scl,master_sda,old_wr,old_reset,bad_serial;
static unsigned address,key_mask,word_current,word_previous,prior_executed;
static unsigned violations,left_nonzero,bit_offset;
static bool old_bclk,old_ws,old_data;
#ifdef F1_CLOCKED
static bool config_observed;
static unsigned config_result;
#endif
static uint16_t serial_left;
static std::array<uint8_t,256> registers;
static std::vector<uint8_t> trace;
static void advance(uint64_t us);
static void inputs(){
#ifdef F1_CLOCKED
    si->update(time_tick/256,d->si_scl_low,d->si_sda_low);
    d->si_scl_in=si->scl;d->si_sda_in=si->sda;
#endif
#ifdef F1_USB
    d->usb_dp_in=d->usb_tx_enable?d->usb_dp_out:usb.dp;
    d->usb_dn_in=d->usb_tx_enable?d->usb_dn_out:usb.dn;
#endif
    d->scl_in=!(master_scl||d->scl_low);d->sda_in=!(master_sda||d->sda_low);
    d->ym_data_in=(!d->ym_cs_n&&!d->ym_rd_n)?(d->ym_a0?registers[address]:(time_tick<busy_until?128:0)):255;
    d->fm_sd=0;d->fm_clk=0;d->fm_sh=0;
    if(d->ym_reset_n){
        if(time_tick<fm_base){d->fm_sh=1;return;}
        const uint64_t rel=time_tick-fm_base;
#ifdef F1_CLOCKED
        const uint64_t frequency=d->ym_frequency;
#else
        const uint64_t frequency=4000000;
#endif
        const uint64_t t=rel*frequency,period=36864000000ull,half=period/2,frame_period=period*24,frame=t/frame_period;
        if(frame!=last_frame){
            word_previous=word_current;
            const int m=512+(int(frame%32)-16)*8;
            word_current=bad_serial?0:(key_mask?unsigned((6<<10)|m)<<11:0x600u<<11);
            last_frame=frame;
        }
        d->fm_clk=(t/half)&1;d->fm_sh=t%frame_period>=frame_period-period;
        if(t>=half){const uint64_t pos=(t-half)/period;
            d->fm_sd=((pos/24==frame?word_current:word_previous)>>(pos%24))&1;
        }
    }
}
static void step(){
    const uint64_t c=run_c?next_c:UINT64_MAX,a=run_a?next_a:UINT64_MAX;
    time_tick=c<a?c:a;
    const bool cedge=c==time_tick,aedge=a==time_tick;
#ifdef F1_USB
    const bool usb_edge=cedge&&!d->clk;
    if(usb_edge){
        if(auto_symbols.empty()&&!usb_pause&&auto_sof&&d->usb_vbus&&time_tick>=auto_next&&!d->usb_tx_enable){
            unsigned v=(++auto_frame)&2047;v|=UsbHost::crc5(v)<<11;
            auto symbols=UsbHost::encode({128,0xa5,uint8_t(v),uint8_t(v>>8)});
            auto_symbols.insert(auto_symbols.end(),symbols.begin(),symbols.end());auto_repeat=0;auto_next=time_tick+12288000;
        }
        if(!auto_symbols.empty()){
            auto v=auto_symbols.front();usb.dp=(v&2)!=0;usb.dn=(v&1)!=0;usb.host_enable=true;
            if(++auto_repeat==4){auto_repeat=0;auto_symbols.pop_front();}
        }else if(!usb_pause){usb.dp=true;usb.dn=false;usb.host_enable=false;}
    }
#endif
    inputs();d->eval();
    if(cedge){d->clk=!d->clk;next_c+=128;}
    if(aedge){
#ifdef F1_CLOCKED
        const bool output_enabled=si->reset_at&&!(si->regs[3]&2)&&!(si->regs[17]&128);
        d->audio_clk=output_enabled ? !d->audio_clk : 0;
#else
        d->audio_clk=!d->audio_clk;
#endif
        next_a+=125;
    }
    d->eval();
#ifdef F1_CLOCKED
    if(d->config_done){config_observed=true;config_result=d->config_error;}
#endif
#ifdef F1_USB
    if(usb_edge)usb.observe(d->usb_tx_enable,d->usb_dp_out,d->usb_dn_out);
#endif
    if(d->ym_reset_n&&!old_reset){fm_base=time_tick+9216;last_frame=UINT64_MAX;word_current=word_previous=0x600u<<11;}
    if(!d->ym_reset_n){registers.fill(0);key_mask=0;busy_until=0;}
    else if(!old_wr&&d->ym_wr_n&&!d->ym_cs_n){
        if(!d->ym_data_oe||!d->translator_dir||d->translator_oe_n||time_tick<busy_until)++violations;
        if(!d->ym_a0){address=d->ym_data_out;busy_until=time_tick+15*12288;}
        else{
            registers[address]=d->ym_data_out;busy_until=time_tick+35*12288;
            if(address==0x28){unsigned ch=d->ym_data_out&3;if(ch<3){if(d->ym_data_out&0xf0)key_mask|=1u<<ch;else key_mask&=~(1u<<ch);}}
        }
    }
    if(d->executed>prior_executed){
        if(d->executed!=prior_executed+1)++violations;
        trace.push_back(uint8_t(address));trace.push_back(registers[address]);
    }
    prior_executed=d->executed;
    if(!old_bclk&&d->i2s_bclk){
        if(d->i2s_lrck!=old_ws){old_ws=d->i2s_lrck;bit_offset=0;serial_left=0;}
        else{
            if(bit_offset<16){serial_left=uint16_t((serial_left<<1)|d->i2s_data);
                if(bit_offset==15&&!old_ws&&serial_left&&d->line_allow)++left_nonzero;}
            ++bit_offset;
        }
    }
    if(!d->reset&&d->permit&&d->i2s_data!=old_data&&!(old_bclk&&!d->i2s_bclk))++violations;
    old_wr=d->ym_wr_n;old_reset=d->ym_reset_n;old_bclk=d->i2s_bclk;old_data=d->i2s_data;
}
static void advance(uint64_t us){
    const uint64_t until=time_tick+us*12288;
    while((run_c?next_c:UINT64_MAX)<until||(run_a?next_a:UINT64_MAX)<until)step();
    time_tick=until;inputs();d->eval();
}
static bool high(){
    master_scl=false;
    for(unsigned i=0;i<120000;++i){advance(1);if(!d->scl_low){advance(5);return true;}}
    return false;
}
static bool start(){master_sda=false;if(!high())return false;master_sda=true;advance(5);master_scl=true;advance(1);return true;}
static bool stop(){master_scl=true;master_sda=true;advance(4);if(!high())return false;master_sda=false;advance(5);return true;}
static bool send(uint8_t b){
    for(unsigned i=0;i<8;++i){master_sda=!(b&128);advance(4);if(!high())return false;master_scl=true;advance(1);b<<=1;}
    master_sda=false;advance(4);if(!high())return false;bool ack=d->sda_low;master_scl=true;advance(1);return ack;
}
static int receive(bool ack){
    unsigned b=0;master_sda=false;
    for(unsigned i=0;i<8;++i){advance(4);if(!high())return -1;b=(b<<1)|!d->sda_low;master_scl=true;advance(1);}
    master_sda=ack;advance(4);if(!high())return -1;master_scl=true;advance(1);master_sda=false;return int(b);
}
extern "C" {
void real_destroy(){d.reset();}
void real_init(){
    d=std::make_unique<Vrevc_real_ym_top>();
#ifdef F1_CLOCKED
    si=std::make_unique<Si5351Fixture>();
#endif
    time_tick=0;next_c=128;next_a=125;busy_until=0;fm_base=0;last_frame=UINT64_MAX;
    run_c=run_a=true;master_scl=master_sda=false;old_wr=true;old_reset=false;bad_serial=false;
    address=key_mask=word_current=word_previous=prior_executed=0;violations=left_nonzero=bit_offset=0;
    old_bclk=old_ws=old_data=false;trace.clear();registers.fill(0);
#ifdef F1_USB
    usb=UsbHost();usb.tick=[] {advance(0);const uint64_t end=time_tick+256;while(next_c<=end||next_a<=end)step();};
    auto_sof=true;usb_pause=false;auto_symbols.clear();auto_repeat=auto_frame=0;auto_next=12288000;d->usb_vbus=1;
#endif
    d->permit=1;
#ifndef F1_CLOCKED
    d->clock_good=1;
#endif
    d->reset=1;advance(2);d->reset=0;
#ifdef F1_CLOCKED
    for(unsigned i=0;i<500&&!d->audio_ok;++i)advance(1000);
#else
    advance(10000);
#endif
}
uint64_t real_now(){return time_tick/12288;}
void real_advance(uint64_t us){advance(us);}
int real_write(unsigned a,const uint8_t*p,unsigned n){if(!start())return -1;if(!send(uint8_t(a<<1))){stop();return -2;}
    for(unsigned i=0;i<n;++i)if(!send(p[i])){stop();return -3;}return stop()?int(n):-4;}
int real_read(unsigned a,uint8_t*p,unsigned n){if(!start())return -1;if(!send(uint8_t((a<<1)|1))){stop();return -2;}
    for(unsigned i=0;i<n;++i){int b=receive(i+1<n);if(b<0){stop();return -3;}p[i]=uint8_t(b);}return stop()?int(n):-4;}
unsigned real_healthy(){return d->audio_ok;}
unsigned real_fault(){return d->audio_fault;}
unsigned real_gate(){return d->line_allow||d->dac_allow;}
unsigned real_state(){return d->session_state;}
unsigned real_backend(){return d->backend_state;}
unsigned real_violations(){return violations;}
unsigned real_nonzero(){return left_nonzero;}
unsigned real_trace_count(){return unsigned(trace.size()/2);}
const uint8_t*real_trace(){return trace.data();}
unsigned real_pcm_level(){return d->pcm_level;}
unsigned real_sources(){return key_mask|((registers[8]&31)?8u:0u)|((registers[9]&31)?16u:0u)|((registers[10]&31)?32u:0u);}
void real_bad_serial(){bad_serial=true;}
void real_audio_clock(unsigned enabled){run_a=enabled;if(enabled)next_a=time_tick+125;}
void real_control_clock(unsigned enabled){run_c=enabled;if(enabled)next_c=time_tick+128;}
void real_permit(unsigned enabled){d->permit=enabled;d->eval();}
#ifdef F1_CLOCKED
unsigned real_clock_profile(){return d->active_profile;}
unsigned real_clock_frequency(){return d->ym_frequency;}
unsigned real_clock_error(){return d->clock_error;}
void real_clock_loss(unsigned loss){si->loss=loss!=0;}
void real_other_owned(unsigned owned){d->other_owned=owned!=0;d->eval();}
void real_config_start(unsigned profile){
    for(unsigned i=0;i<10000&&d->clock_state!=18&&d->clock_state!=23;++i)advance(1);
    config_observed=false;config_result=255;d->config_profile=profile;d->config_valid=1;
    for(unsigned i=0;i<2;++i)advance(1);
}
unsigned real_config_finish(){
    if(!config_observed)for(unsigned i=0;i<600000&&!config_observed;++i)advance(1);
    const unsigned result=config_result;
    if(!config_observed)return 255;
    d->config_valid=0;advance(1);
    for(unsigned i=0;i<10000&&!d->audio_ok&&d->clock_good;++i)advance(1);
    return result;
}
unsigned real_config(unsigned profile){real_config_start(profile);return real_config_finish();}
#endif

#ifdef F1_USB
void usb_pause_begin(){usb_pause=true;while(!auto_symbols.empty()||usb.host_enable){
    // Finish an already-started automatic SOF before issuing host transactions.
    if(auto_symbols.empty()){usb.host_enable=false;usb.dp=true;usb.dn=false;break;}
    usb.tick();
}usb.cycles(16);}
void usb_pause_end(){usb.cycles(32);usb_pause=false;}
int usb_enumerate(){try{usb_pause_begin();usb.address=0;
    auto desc=usb.control_in(0x80,6,0x100,0,18);if(desc.size()!=18)return -2;
    usb.no_data(0,5,7);usb.address=7;
    if(usb.control_in(0x80,6,0x200,0,255).size()!=175)return -3;
    usb.no_data(0,9,1);usb.no_data(0x21,0x22,3);usb.sof(++auto_frame);
    usb_pause_end();advance(201000);return 0;
}catch(...){usb_pause_end();return -1;}}
int usb_midi(unsigned word,unsigned toggle){try{usb_pause_begin();auto r=usb.out(3,{uint8_t(word),uint8_t(word>>8),uint8_t(word>>16),uint8_t(word>>24)},toggle);usb_pause_end();return r==std::vector<uint8_t>{0xd2}?0:-2;}catch(...){usb_pause_end();return -1;}}
int usb_cdc(const uint8_t*p,unsigned n,unsigned toggle){try{usb_pause_begin();auto r=usb.out(2,std::vector<uint8_t>(p,p+n),toggle);usb_pause_end();return r==std::vector<uint8_t>{0xd2}?0:-2;}catch(...){usb_pause_end();return -1;}}
int usb_cdc_read(uint8_t*p){try{usb_pause_begin();auto r=usb.in(2);usb_pause_end();if(r.empty())return -1;if(r[0]==0x5a)return 0;if(r[0]!=0xc3&&r[0]!=0x4b)return -2;std::copy(r.begin()+1,r.end()-2,p);return int(r.size()-3);}catch(...){usb_pause_end();return -3;}}
void usb_vbus(unsigned v){d->usb_vbus=v;d->eval();}
void usb_sof_enable(unsigned v){auto_sof=v;}
void usb_bus_reset(){usb_pause_begin();usb.dp=usb.dn=false;usb.host_enable=true;usb.cycles(600);usb.dp=true;usb.dn=false;usb.host_enable=false;usb.cycles(64);usb_pause_end();usb.address=0;}
unsigned usb_midi_owned(){return d->midi_owned;}
unsigned usb_midi_mask(){return d->midi_mask;}
unsigned usb_midi_state(){return d->midi_state;}
unsigned usb_midi_fault(){return d->midi_fault;}
unsigned usb_midi_received(){return d->midi_received;}
unsigned usb_configured(){return d->usb_configured;}
unsigned usb_online(){return d->usb_online;}
#endif

}
