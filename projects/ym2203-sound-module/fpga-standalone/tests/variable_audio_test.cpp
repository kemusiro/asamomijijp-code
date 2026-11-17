// SPDX-License-Identifier: MIT
#include "Vrevc_audio_path.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
static uint32_t raw(unsigned n){return ((6u<<10)|unsigned(256+int(n*37%512)))<<11;}
static int decode(unsigned n){return (int((raw(n)>>11)&1023)-512)*32;}
static int floor_div(int64_t a,int b){return int(a>=0?a/b:-((-a+b-1)/b));}
int main(){try{
    const unsigned rates[]={4000000,3579545,3993600,3000000,2000000,1500000,2500000,3500000};
    unsigned cases=0,total=0;
    for(unsigned rate:rates){
        Vrevc_audio_path d;d.ym_frequency=rate;d.clock_reset=1;d.stream_reset=1;
        for(int i=0;i<8;++i){d.clk=0;d.eval();d.clk=1;d.eval();}
        d.clock_reset=0;d.stream_reset=0;d.audible=1;
        unsigned out=0,minimum=64,maximum=0;
        const uint64_t half=73728000,period=147456000,frame_period=3538944000ull;
        for(unsigned cycle=0;cycle<4915200;++cycle){
            d.sh_in=1;d.bitclk_in=0;d.sd_in=0;
            if(cycle>=200){
                uint64_t t=uint64_t(cycle-200)*rate;
                d.bitclk_in=(t/half)&1;d.sh_in=t%frame_period>=frame_period-period;
                if(t>=half){uint64_t bit=(t-half)/period;d.sd_in=(raw(unsigned(bit/24))>>(bit%24))&1;}
            }
            d.clk=0;d.eval();
            if(d.pcm_probe_valid){
                uint64_t p=uint64_t(out)*rate;unsigned i=unsigned(p/3456000),f=unsigned(p%3456000);
                int expected=floor_div(int64_t(decode(i))*(3456000-f)+int64_t(decode(i+1))*f,3456000);
                if(int16_t(d.pcm_probe)!=expected){std::cerr<<"rate="<<rate<<" out="<<out<<" actual="<<int16_t(d.pcm_probe)<<" expected="<<expected<<'\n';throw std::runtime_error("variable RX/PCM parity");}
                ++out;++total;
            }
            d.clk=1;d.eval();d.clk=0;d.eval();
            if(d.healthy){if(d.pcm_level<minimum)minimum=d.pcm_level;if(d.pcm_level>maximum)maximum=d.pcm_level;}
            need(!d.fault,"variable audio fault");
        }
        need(d.healthy&&out>4750&&minimum>=1&&maximum<64,"rate drift or lost samples");++cases;
        std::cout<<"RATE "<<rate<<" PCM="<<out<<" level="<<minimum<<".."<<maximum<<'\n';
    }
    std::cout<<"PASS VARIABLE AUDIO "<<cases<<" x100ms serial-to-PCM/I2S runs / "<<total<<" samples\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
