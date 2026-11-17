// SPDX-License-Identifier: GPL-3.0-or-later
#include "Vasync_pcm_fifo.h"
#include "verilated.h"
#include <deque>
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <cstdint>
static void check(bool p,const char*s){if(!p)throw std::runtime_error(s);}
static uint32_t random_state=0x71235ab;
static uint32_t rnd(){random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;return random_state;}
static void trial(unsigned wp,unsigned rp,unsigned phase){
    Vasync_pcm_fifo t;uint64_t now=0,wn=wp,rn=rp+phase;std::deque<uint16_t> q;
    t.wclk=0;t.rclk=0;t.wrst_n=0;t.rrst_n=0;t.wvalid=0;t.rready=0;t.eval();
    unsigned sent=0,received=0,full=0,empty=0;
    for(unsigned edges=0;edges<1000000&&received<5000;edges++){
        now=std::min(wn,rn);bool w=now==wn,r=now==rn;
        bool w_rise=w&&!t.wclk,r_rise=r&&!t.rclk;
        if(edges==40){t.wrst_n=1;t.rrst_n=1;t.eval();}
        bool push=w_rise&&t.wvalid&&t.wready,pop=r_rise&&t.rvalid&&t.rready;
        if(pop){check(!q.empty(),"FIFO invented a word");check(t.rdata==q.front(),"FIFO order/data mismatch");q.pop_front();received++;}
        if(push){q.push_back(t.wdata);sent++;}
        if(w){t.wclk=!t.wclk;wn+=wp;}
        if(r){t.rclk=!t.rclk;rn+=rp;}
        t.eval();
        if(w&&!t.wclk){t.wvalid=sent<5000&&(rnd()%4!=0);t.wdata=uint16_t(sent*31+7);}
        if(r&&!t.rclk)t.rready=(edges>2000)&&(rnd()%4!=0);
        if(t.wrst_n&&!t.wready)full++;
        if(t.rrst_n&&!t.rvalid)empty++;
        t.eval();
    }
    check(received==5000&&q.empty(),"FIFO drain/count mismatch");
    check(full>0&&empty>0,"FIFO full/empty cases not exercised");
    // Buffer old payload without consumption, reset, then verify a new sequence.
    unsigned old_sent=0;t.rready=0;t.wvalid=1;t.wdata=0xdead;t.eval();
    while(old_sent<24){
        now=std::min(wn,rn);bool w=now==wn,r=now==rn;
        if(w&&!t.wclk&&t.wvalid&&t.wready)old_sent++;
        if(w){t.wclk=!t.wclk;wn+=wp;}if(r){t.rclk=!t.rclk;rn+=rp;}t.eval();
    }
    t.wrst_n=0;t.rrst_n=0;t.wvalid=0;t.eval();check(!t.rvalid,"FIFO reset left valid asserted");
    for(int k=0;k<20;k++){
        now=std::min(wn,rn);if(now==wn){t.wclk=!t.wclk;wn+=wp;}
        if(now==rn){t.rclk=!t.rclk;rn+=rp;}t.eval();
    }
    t.wrst_n=1;t.rrst_n=1;t.rready=1;t.wvalid=1;t.wdata=0x8000;t.eval();
    unsigned new_sent=0,new_received=0;
    while(new_received<32){
        now=std::min(wn,rn);bool w=now==wn,r=now==rn;
        if(r&&!t.rclk&&t.rvalid&&t.rready){
            check(t.rdata==uint16_t(0x8000+new_received),"reset replayed old FIFO payload");new_received++;
        }
        if(w&&!t.wclk&&t.wvalid&&t.wready)new_sent++;
        if(w){t.wclk=!t.wclk;wn+=wp;}if(r){t.rclk=!t.rclk;rn+=rp;}t.eval();
        if(w&&!t.wclk){t.wvalid=new_sent<32;t.wdata=uint16_t(0x8000+new_sent);t.eval();}
    }
    std::cout<<"PASS FIFO wrap/random/full/empty/reset "<<wp<<':'<<rp<<" phase="<<phase<<'\n';
}
int main(int argc,char**argv){Verilated::commandArgs(argc,argv);try{trial(48,16,1);trial(16,48,7);trial(31,47,13);}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
