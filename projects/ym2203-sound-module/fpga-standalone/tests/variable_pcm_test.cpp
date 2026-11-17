// SPDX-License-Identifier: MIT
#include "Vrevc_fm_pcm.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
static int64_t floor_div(int64_t n,int64_t d){return n>=0?n/d:-((-n+d-1)/d);}
static void tick(Vrevc_fm_pcm&d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
int main(){try{
    const unsigned rates[]={4000000,3579545,3993600,3000000,2000000,1500000,2500000,3500000};
    std::mt19937 random(53512203);Vrevc_fm_pcm d;unsigned cases=0,total=0;
    for(unsigned rate:rates)for(unsigned gain=0;gain<=16;++gain){
        std::vector<int16_t> input(512);for(auto&v:input)v=int16_t(random());
        input[0]=-32768;input[1]=32767;
        d.reset=1;d.step_hz=rate;d.gain_eighths=gain;tick(d);d.reset=0;
        unsigned sent=0,received=0,clips=0;
        for(unsigned cycle=0;cycle<200000&&received<256;++cycle){
            d.input_valid=sent<input.size()&&cycle%7!=0;d.input_sample=sent<input.size()?uint16_t(input[sent]):0;
            d.output_ready=cycle%11!=0;d.eval();const bool take=d.input_take;
            if(d.output_valid&&d.output_ready){
                uint64_t phase=uint64_t(received)*rate;unsigned i=unsigned(phase/3456000),f=unsigned(phase%3456000);
                int64_t n=int64_t(input[i])*(3456000-f)+int64_t(input[i+1])*f;
                int64_t sample=floor_div(floor_div(n,3456000)*gain,8);
                if(sample< -32768||sample>32767)++clips;
                sample=std::clamp<int64_t>(sample,-32768,32767);
                if(int16_t(d.output_sample)!=sample){std::cerr<<"rate="<<rate<<" gain="<<gain<<" sample="<<received<<'\n';throw std::runtime_error("variable PCM differs from rational reference");}
                ++received;++total;
            }
            tick(d);if(take)++sent;need(!d.fault,"valid rate faulted");
        }
        need(received==256&&d.clipped==clips,"variable PCM stalled or clipping count mismatch");++cases;
    }
    for(unsigned rate:{0u,1499999u,4000001u}){d.reset=1;tick(d);d.reset=0;d.step_hz=rate;tick(d);need(d.fault,"invalid rate accepted");}
    std::cout<<"PASS VARIABLE PCM "<<cases<<" cases / "<<total<<" samples; all gains, up/down sampling, reset, stalls, invalid rates\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
