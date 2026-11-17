// SPDX-License-Identifier: MIT
#include "Vrevc_ym_bus.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
static void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
struct Model{
    Vrevc_ym_bus d;uint64_t time=0,busy_until=0,wr_at=0,cs_at=0,dir_at=0;
    bool old_wr=true,old_cs=true,old_dir=false,stuck=false;
    unsigned address=0,addresses=0,writes=0;std::array<uint8_t,256> regs{};
    void tick(){
        d.ym_data_in=(!d.ym_cs_n&&!d.ym_rd_n)?(d.ym_a0?regs[address]:(stuck||time<busy_until?128:0)):255;
        d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();++time;
        if(!d.reset){
            need(d.ym_wr_n||d.ym_rd_n,"simultaneous read/write");
            if(d.translator_dir!=old_dir){need(d.translator_oe_n,"DIR changed with OE active");dir_at=time;}
            if(!d.translator_oe_n)need(time-dir_at>=48,"DIR settling shorter than 1us");
            if(!d.ym_rd_n&&!d.ym_cs_n)need(!d.ym_data_oe&&!d.translator_dir&&!d.translator_oe_n,"read direction/drive collision");
            if(old_cs&&!d.ym_cs_n)cs_at=time;
            if(old_wr&&!d.ym_wr_n){
                need(d.ym_data_oe&&d.translator_dir&&!d.translator_oe_n,"write drive missing");
                need(time-cs_at>=48,"CS setup shorter than 1us");wr_at=time;
            }
            if(!old_wr&&d.ym_wr_n&&!d.ym_cs_n){
                need(time-wr_at>=48,"WR pulse shorter than 1us");need(!stuck&&time>=busy_until,"wrote while BUSY");
                if(!d.ym_a0){address=d.ym_data_out;++addresses;busy_until=time+15*48;}
                else{regs[address]=d.ym_data_out;++writes;busy_until=time+35*48;}
            }
        }
        old_wr=d.ym_wr_n;old_cs=d.ym_cs_n;old_dir=d.translator_dir;
    }
    Model(){d.reset=1;tick();d.reset=0;tick();}
    void start(unsigned r,unsigned v,bool read=false){
        need(d.request_ready,"bus not ready");d.request_register=r;d.request_value=v;d.request_read=read;
        d.request_valid=1;tick();d.request_valid=0;
    }
    void finish(){for(unsigned i=0;i<4800100&&!d.response_valid;++i)tick();need(d.response_valid,"no bounded bus response");}
    void consume(){d.response_ready=1;tick();d.response_ready=0;}
};
int main(){try{
    Model m;
    for(unsigned i=0;i<128;++i){m.start(i%6,(i*73)&255);m.finish();need(!m.d.response_error&&!m.d.response_aborted,"write failed");m.consume();}
    need(m.writes==128&&m.addresses==128&&m.d.completed==128,"address/data count");need(m.d.busy_polls>0,"BUSY was never polled");
    m.start(2,0,true);m.finish();need(m.d.response_data==m.regs[2],"register readback");
    const unsigned held=m.d.response_data;
    for(unsigned i=0;i<100;++i){m.tick();need(m.d.response_valid&&m.d.response_data==held,"reply changed under backpressure");}m.consume();
    for(unsigned phase=0;phase<4;++phase){
        m.start(4,77);for(unsigned i=0;i<phase*220+30;++i)m.tick();m.d.cancel=1;m.finish();
        need(m.d.response_aborted,"cancel not reported");m.consume();m.d.cancel=0;m.tick();
    }
    m.stuck=true;m.start(0,0);m.finish();need(m.d.response_error,"stuck BUSY did not time out");
    need(m.d.ym_cs_n&&m.d.ym_wr_n&&m.d.ym_rd_n&&m.d.translator_oe_n,"fault left bus driving");
    std::cout<<"PASS BUS 128 writes, readback, both BUSY checks, held reply, four cancels, 100ms timeout\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
