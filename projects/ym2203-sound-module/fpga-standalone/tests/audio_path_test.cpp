// SPDX-License-Identifier: MIT
#include "Vrevc_audio_path.h"
#include "verilated.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
static void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
static uint32_t raw(unsigned n){return (((1+n%7)<<10)|((n*73+17)&1023))<<11|((n*439)&2047);}
static int decode(uint32_t v){return (int((v>>11)&1023)-512)*(1<<((v>>21)-1));}
static int floor_div(int n,int d){return n>=0?n/d:-((-n+d-1)/d);}
struct Audio{
    Vrevc_audio_path d;uint64_t cycle=0,base=49152;unsigned skew=0,glitch=0,invalid=~0u;
    unsigned rx=0,out=0;bool frozen=false;unsigned minimum=64,maximum=0;
    void tick(bool verify=true){
        const uint64_t t=cycle*250;
        bool clk=false,sh=true,sd=false;
        if(t>=base){
            const uint64_t rel=t-base;
            clk=rel%9216>=4608;sh=rel%221184>=221184-9216;
            const int64_t pos=int64_t(rel)-4608-int64_t(skew)*250;
            if(pos>=0){uint64_t bit=uint64_t(pos)/9216;uint32_t r=bit/24==invalid?0:raw(unsigned(bit/24));sd=(r>>(bit%24))&1;}
            if(glitch&&((rel%9216>=1200&&rel%9216<1200+glitch*250)||(rel%9216>=6000&&rel%9216<6000+glitch*250)))clk=!clk;
        }
        if(frozen){clk=false;sh=false;sd=false;}
        d.sd_in=sd;d.bitclk_in=clk;d.sh_in=sh;d.clk=0;d.eval();
        if(d.pcm_probe_valid){
            if(verify){unsigned pos=out*125,index=pos/108,fraction=pos%108;
                int value=floor_div(decode(raw(index))*int(108-fraction)+decode(raw(index+1))*int(fraction),108);
                if(int16_t(d.pcm_probe)!=value){std::cerr<<"PCM sample="<<out<<" got="<<int16_t(d.pcm_probe)<<" expected="<<value<<'\n';throw std::runtime_error("RX-to-PCM differs");}
            }
            ++out;
        }
        d.clk=1;d.eval();d.clk=0;d.eval();++cycle;
        if(verify&&d.rx_frames!=rx){need(d.raw_word==raw(rx),"24-bit serial ordering/framing");++rx;}
        if(d.healthy){if(d.pcm_level<minimum)minimum=d.pcm_level;if(d.pcm_level>maximum)maximum=d.pcm_level;}
    }
    Audio(){d.clock_reset=1;d.stream_reset=1;for(unsigned i=0;i<8;++i)tick(false);d.clock_reset=0;d.stream_reset=0;d.audible=1;}
    void run(unsigned n,bool verify=true){for(unsigned i=0;i<n;++i)tick(verify);}
};
int main(){try{
    unsigned cases=0;
    for(unsigned phase=0;phase<3;++phase)for(unsigned skew=0;skew<=5;++skew)for(unsigned glitch=0;glitch<=2;++glitch){
        Audio a;a.base+=phase*83;a.skew=skew;a.glitch=glitch;a.run(100000);
        need(a.d.healthy&&!a.d.fault,"valid audio failed");need(a.out>80,"no PCM");if(glitch)need(a.d.rejections>0,"glitches not observed");++cases;
    }
    Audio longrun;longrun.run(4915200);need(longrun.d.healthy&&!longrun.d.fault,"100ms audio drift/overflow");
    need(longrun.minimum>=1&&longrun.maximum<64,"unbounded PCM occupancy");
    Audio bad;bad.invalid=3;bad.run(10000,false);need(bad.d.fault&&!bad.d.healthy,"zero exponent not fatal");
    Audio lost;lost.run(40000);need(lost.d.healthy,"no prime before clock failure");lost.frozen=true;lost.run(2500000,false);
    need(lost.d.fault&&!lost.d.healthy,"missing FM frame watchdog");
    std::cout<<"PASS AUDIO "<<cases<<" phase/skew/glitch cases; 100ms PCM/RX parity; level="<<longrun.minimum<<".."<<longrun.maximum<<"; exponent/clock faults\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
