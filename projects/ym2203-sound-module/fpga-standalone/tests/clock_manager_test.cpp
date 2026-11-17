// SPDX-License-Identifier: MIT
#include "Vrevc_si5351_manager.h"
#include "verilated.h"
#include "si5351_fixture.h"
#include <iostream>
#include <stdexcept>
static void need(bool x,const char*m){if(!x)throw std::runtime_error(m);}
struct Model {
    Vrevc_si5351_manager d;Si5351Fixture si;uint64_t cycle=0;unsigned done=0;
    Model(){d.reset=1;d.safe_to_change=1;for(int i=0;i<8;++i)tick();d.reset=0;}
    void tick(){
        si.update(cycle,d.scl_low,d.sda_low);d.scl_in=si.scl;d.sda_in=si.sda;d.clk=0;d.eval();
        d.clk=1;d.eval();si.update(cycle,d.scl_low,d.sda_low);d.scl_in=si.scl;d.sda_in=si.sda;d.eval();d.clk=0;d.eval();
        if(d.config_done)++done;++cycle;
    }
    void run(unsigned n){for(unsigned i=0;i<n;++i)tick();}
    void wait(){for(unsigned i=0;i<30000000&&!d.ready&&!d.clock_error;++i)tick();}
    void boot(){wait();need(d.ready&&!d.clock_error,"boot failed");need(si.read_count>100&&si.nacks==si.read_count,"read/NACK coverage");}
    void idle(){while(d.state_monitor!=18&&d.state_monitor!=23)tick();}
    void select(unsigned p){idle();d.config_profile=p;d.config_valid=1;unsigned before=done;tick();
        for(unsigned i=0;i<30000000&&done==before;++i)tick();need(done==before+1,"missing config acknowledgement");d.config_valid=0;tick();}
};
int main(){try{
    unsigned cases=0;
    {Model m;m.boot();m.si.verify_frequency(4000000);++cases;
        const unsigned rates[]={4000000,3579545,3993600,3000000,2000000,1500000,2500000,3500000};
        for(unsigned i=1;i<8;++i){m.select(i);need(m.d.ready&&!m.d.config_error,"profile rejected");m.si.verify_frequency(rates[i]);++cases;}
        m.select(0);m.si.verify_frequency(4000000);++cases;
        auto writes=m.si.writes.size();m.d.safe_to_change=0;m.select(1);need(m.d.config_error==2&&m.d.ready,"running config not rejected");
        need(m.si.writes.size()==writes&&m.d.active_profile==0,"rejected config changed clock");++cases;
        m.d.safe_to_change=1;m.select(8);need(m.d.config_error==1&&m.d.ready,"invalid profile accepted");++cases;
        m.idle();m.d.config_profile=0;m.d.config_valid=1;unsigned before=m.done;
        while(m.done==before)m.tick();m.run(100000);need(m.done==before+1,"held request repeated");m.d.config_valid=0;m.tick();++cases;
        m.si.loss=true;m.run(500000);need(!m.d.ready&&m.d.clock_error==7,"lock loss did not latch off");
        m.run(500000);need(!m.d.ready,"automatic retry after lock loss");m.si.loss=false;m.select(0);need(m.d.ready,"explicit recovery failed");++cases;
        m.si.loss=true;m.run(480);m.si.loss=false;m.run(500000);
        need(!m.d.ready&&m.d.clock_error==7,"short sticky lock loss missed");m.select(0);need(m.d.ready,"sticky recovery failed");++cases;
        writes=m.si.writes.size();m.si.forever_init=true;m.run(500000);
        need(!m.d.ready&&m.d.clock_error==7,"unexpected SYS_INIT missed");
        need(m.si.writes.size()==writes,"RAM written while SYS_INIT returned");++cases;
    }
    for(int i=0;i<4;++i){Model m;if(i==3)m.si.nack_read_address=true;else m.si.nack_position=i;m.wait();need(!m.d.ready&&m.d.clock_error==3,"NACK not fatal");++cases;}
    for(int i=0;i<2;++i){Model m;m.si.hold_scl=i==0;m.si.hold_sda=i==1;m.wait();need(!m.d.ready&&m.d.clock_error==3,"stuck bus not bounded");++cases;}
    {Model m;m.si.forever_init=true;m.wait();need(!m.d.ready&&m.d.clock_error==4,"SYS_INIT not bounded");need(m.si.writes.empty(),"RAM write during SYS_INIT");++cases;}
    {Model m;m.si.never_lock=true;m.wait();need(!m.d.ready&&m.d.clock_error==5,"PLL lock not bounded");need(m.si.regs[3]==255,"unlocked outputs enabled");++cases;}
    {Model m;m.si.corrupt=true;m.wait();need(!m.d.ready&&m.d.clock_error==6,"bad readback not fatal");++cases;}
    {Model m;m.si.stretch_cycles=960;m.boot();m.si.verify_frequency(4000000);++cases;}
    std::cout<<"PASS CLOCK MANAGER "<<cases<<" cases; eight exact plans, RMW/readback, repeated START/read NACK, hold, interlock, fault/retry\n";
    return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
