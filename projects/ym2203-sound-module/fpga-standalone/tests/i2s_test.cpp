// SPDX-License-Identifier: MIT
#include "Vrevc_i2s_tx.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
static void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
int main(){try{
    Vrevc_i2s_tx d;d.clock_reset=1;d.clk=0;d.eval();d.clk=1;d.eval();d.clock_reset=0;
    std::deque<uint16_t> expected;unsigned sent=0,matched=0,offset=0;uint16_t word=0;
    bool ws=true,oldb=d.bclk,olddata=d.data;unsigned lastfall=0;
    for(unsigned cycle=0;cycle<60000;++cycle){
        d.audible=cycle<20000||cycle>=30000;d.sample_valid=1;d.level=32;d.sample=uint16_t(0x8123+sent*73);
        d.clk=0;d.eval();if(d.take){expected.push_back(d.audible?d.sample:0);++sent;}
        d.clk=1;d.eval();d.clk=0;d.eval();
        if(oldb&&!d.bclk){if(lastfall)need(cycle-lastfall==16,"BCLK period");lastfall=cycle;}
        if(d.data!=olddata)need(oldb&&!d.bclk,"SD changed outside BCLK falling edge");
        if(!oldb&&d.bclk){
            if(d.lrck!=ws){ws=d.lrck;offset=0;word=0;}
            else{
                if(offset<16){word=uint16_t((word<<1)|d.data);if(offset==15){
                    if(!ws){need(!expected.empty(),"missing left sample");need(word==expected.front(),"I2S bit order/delay/PCM");expected.pop_front();++matched;}
                    else need(word==0,"right must stay zero for Rev C wiring");
                }}else need(!d.data,"nonzero I2S padding");
                ++offset;
            }
        }
        oldb=d.bclk;olddata=d.data;
    }
    need(matched>=55&&!d.fault,"I2S frames/prime");
    d.stream_reset=1;unsigned edges=0,lastedge=0;
    for(unsigned i=0;i<300;++i){const bool before=d.bclk;d.clk=1;d.eval();d.clk=0;d.eval();
        if(d.bclk!=before){if(edges)need(i-lastedge==8,"clock interval during stream reset");lastedge=i;++edges;}}
    need(edges>=37,"clock stopped on stream reset");
    d.stream_reset=0;d.sample_valid=1;d.level=32;
    for(unsigned i=0;i<2000;++i){d.clk=1;d.eval();d.clk=0;d.eval();}
    need(d.primed,"reprime failed");d.sample_valid=0;d.level=0;
    for(unsigned i=0;i<2000;++i){d.clk=1;d.eval();d.clk=0;d.eval();}
    need(d.fault&&!d.primed,"underrun did not fail closed");
    std::cout<<"PASS I2S "<<matched<<" left frames, zero right/padding, mute, continuous clocks, reset/reprime, underrun\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
