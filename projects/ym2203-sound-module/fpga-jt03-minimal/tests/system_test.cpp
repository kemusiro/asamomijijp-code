// SPDX-License-Identifier: GPL-3.0-or-later
#include "Vjt03_minimal.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

static void require(bool b,const std::string& why){if(!b)throw std::runtime_error(why);}
static uint8_t crc8(const uint8_t* p,unsigned n){uint8_t c=0;for(unsigned j=0;j<n;j++){c^=p[j];for(int k=0;k<8;k++)c=(c&128)?uint8_t((c<<1)^7):uint8_t(c<<1);}return c;}
class Sim {
public:
    Vjt03_minimal top;
    // Unit = 1/1536 ns. Exact 16 MHz / 49.152 MHz, independent initial phase.
    uint64_t time=0, sys_next=48000, aud_next=15625;
    bool sys_on=true,aud_on=true;
    std::vector<std::pair<uint32_t,uint16_t>> writes;
    std::vector<int16_t> left,right;
    unsigned bit=0; uint32_t word=0; bool aligned=false; uint64_t prev_ws_time=0;
    std::vector<uint64_t> ws_periods, continuous_periods;
    uint64_t previous_continuous=0;int16_t last_left=0;bool has_left=false;
    Sim(uint64_t phase=731){aud_next+=phase;top.synth_clk=0;top.audio_clk=0;top.reset_n=0;top.permit=1;top.spi_cs_n=1;top.spi_sck=0;top.spi_mosi=0;top.debug_force_busy=0;top.eval();wait_us(20);top.reset_n=1;top.eval();wait_us(500);}
    void advance(uint64_t until){
        while(true){
            uint64_t next=std::min(sys_on?sys_next:UINT64_MAX,aud_on?aud_next:UINT64_MAX);
            if(next>until)break;
            time=next;bool sc=sys_on&&next==sys_next, ac=aud_on&&next==aud_next;
            bool old_bclk=top.i2s_bclk,old_ws=top.i2s_lrck;
            if(sc){top.synth_clk=!top.synth_clk;sys_next+=48000;}
            if(ac){top.audio_clk=!top.audio_clk;aud_next+=15625;}
            top.eval();
            if(sc&&top.synth_clk&&top.debug_commit)writes.push_back({top.debug_us,top.debug_pair});
            if(ac&&!old_ws&&top.i2s_lrck){
                if(previous_continuous)continuous_periods.push_back(time-previous_continuous);
                previous_continuous=time;
            }
            if(top.debug_clear){prev_ws_time=0;aligned=false;has_left=false;}
            if(ac&&!top.debug_clear&&!old_ws&&top.i2s_lrck){
                if(prev_ws_time)ws_periods.push_back(time-prev_ws_time);
                prev_ws_time=time;
            }
            if(ac&&!top.debug_clear&&!old_bclk&&top.i2s_bclk){
                // First bit after WS transition is the previous channel's final bit.
                if(top.i2s_lrck!=last_ws){last_ws=top.i2s_lrck;bit=0;word=0;aligned=true;}
                else if(aligned){
                    bit++;
                    if(bit<=16)word=(word<<1)|top.i2s_data;
                    if(bit==16){
                        (top.i2s_lrck?right:left).push_back(int16_t(word));
                        if(!top.i2s_lrck){last_left=int16_t(word);has_left=true;}
                        else if(has_left&&top.line_allow)require(int16_t(word)==last_left,"I2S L/R mismatch");
                    }
                    if(bit>16)require(top.i2s_data==0,"I2S nonzero padding");
                }
            }
        }
        time=until;
    }
    bool last_ws=false;
    void wait_us(uint64_t us){advance(time+us*1536000ull);}
    std::array<uint8_t,8> command(uint8_t op,uint8_t reg=0,uint8_t data=0,uint32_t us=0,int length=64,bool corrupt=false){
        std::array<uint8_t,8> p{op,reg,data,uint8_t(us>>24),uint8_t(us>>16),uint8_t(us>>8),uint8_t(us),0},out{};
        p[7]=crc8(p.data(),7);if(corrupt)p[7]^=1;
        top.spi_cs_n=0;top.spi_sck=0;top.eval();wait_us(1);
        for(int k=0;k<length;k++){
            unsigned b=k%64;top.spi_mosi=(p[b/8]>>(7-b%8))&1;top.eval();advance(time+768000);
            top.spi_sck=1;top.eval();
            if(k<64)out[k/8]=uint8_t((out[k/8]<<1)|top.spi_miso);
            advance(time+768000);top.spi_sck=0;top.eval();
        }
        wait_us(1);top.spi_cs_n=1;top.eval();wait_us(2);
        require(out[0]==0x4a&&out[1]==1,"SPI status signature");
        if(length>=64)require(crc8(out.data(),7)==out[7],"SPI reply CRC");
        return out;
    }
    void fresh(){command(0x10);wait_us(500);require(!top.fault_out,"BEGIN did not clear fault");require(!top.line_allow,"BEGIN unmuted");}
    void enq(uint32_t t,uint8_t r,uint8_t v){command(1,r,v,t);require(!top.fault_out,"enqueue fault "+std::to_string(top.debug_error));}
    void seal(uint32_t t){command(5,0,0,t);require(!top.fault_out,"seal fault");}
    void start(){command(2);require(top.debug_running,"START rejected code="+std::to_string(top.debug_error));}
    void load_ssg(uint32_t off=20000){enq(0,0,142);enq(0,1,0);enq(0,7,0x3e);enq(0,8,15);enq(off,8,0);}
};
static unsigned passed=0;
static void test(const char*name,void(*fn)()){fn();passed++;std::cout<<"PASS "<<name<<'\n';}
void normal(){
    Sim s;s.fresh();s.load_ssg();s.seal(25000);s.start();s.wait_us(27000);
    require(!s.top.debug_running&&!s.top.fault_out&&!s.top.line_allow,"normal end not quiet");
    require(s.writes.size()==5,"event count");
    uint16_t pairs[]={0x008e,0x0100,0x073e,0x080f,0x0800};
    for(unsigned i=0;i<5;i++){require(s.writes[i].second==pairs[i],"write order/value");require(s.writes[i].first>=(i==4?20000u:0u),"early write");}
    require(std::any_of(s.left.begin(),s.left.end(),[](int16_t x){return x!=0;}),"SSG silent");
    unsigned crossings=0;bool positive=false;
    for(auto x:s.left){if(x>0&&!positive)crossings++;positive=x>0;}
    require(crossings>=6&&crossings<=12,"SSG pitch inconsistent with 440Hz");
    require(s.ws_periods.size()>100,"missing I2S clocks");
    for(auto p:s.ws_periods)require(p==32000000,"LRCK is not exact 48kHz");
    for(auto p:s.continuous_periods)require(p==32000000,"I2S clock broke across normal-end flush");
}
void stop_replay(){
    Sim s;s.fresh();s.load_ssg(40000);s.seal(45000);s.start();s.wait_us(3000);s.command(4);auto n=s.writes.size();s.wait_us(45000);
    require(!s.top.line_allow&&!s.top.debug_running&&s.writes.size()==n,"STOP resumed events");
    s.fresh();s.load_ssg();s.seal(25000);s.start();s.wait_us(27000);require(!s.top.fault_out,"explicit replay failed");
    for(auto p:s.continuous_periods)require(p==32000000,"I2S clocks restarted on STOP/BEGIN");
}
void lease(){Sim s;s.fresh();s.load_ssg(100000);s.seal(105000);s.start();for(int k=0;k<60;k++){s.command(0);s.wait_us(1000);}require(!s.top.line_allow&&s.top.debug_error==5,"reads renewed lease or no lease fault");auto n=s.writes.size();s.wait_us(5000);require(s.writes.size()==n,"lease resumed events");}
void keep(){Sim s;s.fresh();s.load_ssg(80000);s.seal(85000);s.start();for(int k=0;k<20;k++){s.wait_us(4000);s.command(3);}s.wait_us(6000);require(!s.top.fault_out&&!s.top.line_allow,"KEEP/normal end");}
void bad_crc(){Sim s;s.fresh();s.load_ssg(40000);s.seal(45000);s.start();s.command(1,8,0,1000,64,true);require(s.top.debug_error==1&&!s.top.line_allow,"bad CRC not fail-closed");}
void partial(){Sim s;s.fresh();s.command(1,0,0,0,31);require(s.top.debug_error==1&&!s.top.line_allow,"partial frame accepted");}
void overlong(){Sim s;s.fresh();s.command(1,0,0,0,72);require(s.top.debug_error==1,"overlong frame accepted");}
void order(){Sim s;s.fresh();s.enq(1000,8,0);s.command(1,8,0,999);require(s.top.debug_error==4,"decreasing time accepted");}
void full(){Sim s;s.fresh();for(int k=0;k<257;k++)s.enq(100000,8,0);s.command(1,8,0,100000);require(s.top.debug_error==3&&!s.top.line_allow,"FIFO overflow not detected");}
void starvation(){Sim s;s.fresh();s.enq(0,8,0);s.start();s.wait_us(3000);require(s.top.debug_error==9&&!s.top.line_allow,"event starvation did not mute");}
void audio_clock_stop(){Sim s;s.fresh();s.load_ssg(40000);s.seal(45000);s.start();s.wait_us(1000);s.aud_on=false;s.wait_us(3000);require(s.top.fault_out&&!s.top.line_allow,"audio clock stop did not mute");}
void synth_clock_stop(){Sim s;s.fresh();s.load_ssg(40000);s.seal(45000);s.start();s.wait_us(1000);s.sys_on=false;s.wait_us(3000);require(s.top.fault_out&&!s.top.line_allow,"synth clock stop did not mute in audio domain");}
void permit(){Sim s;s.fresh();s.load_ssg(40000);s.seal(45000);s.start();s.wait_us(1000);s.top.permit=0;s.top.eval();require(!s.top.line_allow,"permit not asynchronous");s.wait_us(100);s.top.permit=1;s.top.eval();s.wait_us(2000);require(!s.top.line_allow&&!s.top.debug_running,"permit release auto-restarted");}
void busy_stuck(){Sim s;s.fresh();s.load_ssg(4000);s.seal(10000);s.start();s.wait_us(3000);s.top.debug_force_busy=1;s.top.eval();s.wait_us(2500);require(s.top.debug_error==12&&!s.top.line_allow,"stuck BUSY did not mute");}
void phases(){for(uint64_t p:{1ull,15624ull,47231ull}){Sim s(p);s.fresh();s.load_ssg(2000);s.seal(4000);s.start();s.wait_us(6000);require(!s.top.fault_out&&!s.top.line_allow,"phase-sensitive failure");}}

void streaming_wrap(){
    Sim s;s.fresh();
    for(unsigned i=0;i<150;i++)s.enq(i*300,8,uint8_t(1+i%15));
    s.start();
    for(unsigned i=150;i<600;i++){
        while(s.top.debug_level>=220){s.wait_us(1000);s.command(3);}
        s.enq(i*300,8,uint8_t(1+i%15));
    }
    s.seal(182000);
    while(s.top.debug_running){s.wait_us(4000);if(s.top.debug_running)s.command(3);}
    require(!s.top.fault_out&&s.writes.size()==600,"streaming wrap lost events");
    for(unsigned i=0;i<600;i++){
        require(s.writes[i].second==uint16_t(0x0800|(1+i%15)),"wrap reordered event");
        require(s.writes[i].first>=i*300,"streamed early event");
        require(s.writes[i].first<=i*300+100,"streamed event missed 100us bound");
    }
}
void fm(){
    Sim s;s.fresh();
    for(unsigned slot:{0u,4u,8u,12u})
        for(auto rv:std::vector<std::pair<unsigned,unsigned>>{{0x30,1},{0x40,slot==0?32u:127u},{0x50,31},{0x60,0},{0x70,0},{0x80,15},{0x90,0}})
            s.enq(0,uint8_t(rv.first+slot),uint8_t(rv.second));
    s.enq(0,0xb0,7);s.enq(0,0xa4,0x24);s.enq(0,0xa0,0x0e);s.enq(5000,0x28,0xf0);s.enq(25000,0x28,0);s.seal(30000);s.start();s.wait_us(32000);
    require(!s.top.fault_out,"FM pipeline fault");
    unsigned crossings=0;bool positive=false;unsigned n=0;
    for(auto x:s.left){if(n++<400)continue;if(x>0&&!positive)crossings++;positive=x>0;}
    require(crossings>=5&&crossings<=12,"FM pitch/crossings inconsistent with 440Hz");
}

int main(int argc,char**argv){Verilated::commandArgs(argc,argv);try{
#ifdef DEFAULT_LEASE_TEST
 Sim s;s.fresh();s.load_ssg(1100000);s.seal(1150000);s.start();
 for(int i=0;i<51;i++){s.command(0);s.wait_us(20000);}
 require(s.top.debug_error==5&&!s.top.line_allow,"default one-second lease did not mute");
 std::cout<<"PASS default 16000000-cycle / 1-second lease with read-only SPI traffic\n";
 return 0;
#endif
 test("normal/order/I2S",normal);test("STOP/replay",stop_replay);test("lease/read-only",lease);test("KEEP",keep);
 test("CRC",bad_crc);test("partial",partial);test("overlong",overlong);test("time order",order);test("overflow",full);
 test("event starvation",starvation);test("audio clock stopped",audio_clock_stop);test("synth clock stopped",synth_clock_stop);test("permit",permit);test("clock phases",phases);test("streaming FIFO wrap",streaming_wrap);test("FM pitch",fm);test("stuck BUSY",busy_stuck);
 std::cout<<"ALL "<<passed<<" tests passed\n";
}catch(const std::exception&e){std::cerr<<"FAIL after "<<passed<<": "<<e.what()<<'\n';return 1;}}
