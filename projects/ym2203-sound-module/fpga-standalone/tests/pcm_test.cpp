// SPDX-License-Identifier: MIT
#include "Vrevc_fm_pcm.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
extern "C" uint32_t revc_convert_stream(const uint32_t*,uint32_t*,uint32_t*,unsigned,unsigned,uint32_t*);
static void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
static void tick(Vrevc_fm_pcm&d){d.clk=0;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
int main(){try{
    std::mt19937 rng(220315);unsigned cases=0;
    for(unsigned g=0;g<=16;++g)for(unsigned trial=0;trial<8;++trial){
        std::vector<uint32_t> raw(625),expected;std::vector<uint16_t> source;
        for(unsigned i=0;i<raw.size();++i){
            unsigned e=1+rng()%7,m=rng()%1024;
            if(trial==0){e=7;m=i%2?1023:0;}
            raw[i]=((e<<10)|m)<<19;source.push_back(uint16_t((int(m)-512)*(1<<(e-1))));
        }
        unsigned clips=0;
        for(unsigned b=0;b<5;++b){uint32_t out[108],peak,clipped;
            need(!(revc_convert_stream(raw.data()+125*b,out,&peak,g*128,g*128,&clipped)&~2u),"C conversion error");
            clips+=clipped;expected.insert(expected.end(),out,out+108);
        }
        Vrevc_fm_pcm d;d.gain_eighths=g;d.reset=1;tick(d);d.reset=0;
        unsigned sent=0,received=0;
        for(unsigned cycle=0;received<expected.size()&&cycle<200000;++cycle){
            d.input_valid=sent<source.size();d.input_sample=sent<source.size()?source[sent]:0;
            d.output_ready=cycle%11!=0;d.eval();
            const bool in=d.input_take;const bool out=d.output_valid&&d.output_ready;
            if(out){
                if(uint16_t(expected[received]>>16)!=d.output_sample){
                    std::cerr<<"gain="<<g<<" trial="<<trial<<" sample="<<received<<" actual="<<int16_t(d.output_sample)<<" expected="<<int16_t(expected[received]>>16)<<'\n';
                    throw std::runtime_error("PCM differs from existing C");
                }
                ++received;
            }
            tick(d);if(in)++sent;need(!d.fault,"unexpected converter fault");
        }
        need(received==expected.size(),"converter stalled");need(d.clipped==clips,"clipping count");++cases;
    }
    Vrevc_fm_pcm d;d.reset=1;tick(d);d.reset=0;d.gain_eighths=17;tick(d);need(d.fault,"invalid gain not rejected");
    std::cout<<"PASS PCM "<<cases<<" C-equivalence cases / 73440 output samples / invalid gain\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
