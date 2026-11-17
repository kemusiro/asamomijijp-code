// SPDX-License-Identifier: MIT
// Ideal full-speed USB host: NRZI, bit stuffing, CRC5/16 and ACK/retry.
#pragma once
#include <algorithm>
#include <cstdint>
#include <deque>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <vector>
struct UsbHost {
    std::function<void()> tick;
    bool host_enable=false,dp=true,dn=false;
    bool capturing=false,last_enable=false;
    unsigned capture_cycle=0,address=0;
    std::vector<unsigned> symbols;
    std::deque<std::vector<uint8_t>> replies;
    static uint16_t crc16(const std::vector<uint8_t>&b){uint16_t c=65535;for(auto v:b){c^=v;for(int i=0;i<8;++i)c=(c&1)?uint16_t((c>>1)^0xa001):uint16_t(c>>1);}return uint16_t(~c);}
    static unsigned crc5(unsigned v){unsigned c=31;for(int i=0;i<11;++i){bool x=(c^v)&1;c>>=1;v>>=1;if(x)c^=0x14;}return c^31;}
    static std::vector<unsigned> encode(const std::vector<uint8_t>&bytes,bool bad_stuff=false,unsigned eop_bits=2){
        std::vector<unsigned> s;bool j=true;unsigned ones=0;bool corrupted=false;
        for(auto b:bytes)for(unsigned bit=0;bit<8;++bit){bool d=(b>>bit)&1;if(!d)j=!j;s.push_back(j?2:1);ones=d?ones+1:0;
            if(ones==6){if(!(bad_stuff&&!corrupted))j=!j;else corrupted=true;s.push_back(j?2:1);ones=0;}}
        for(unsigned i=0;i<eop_bits;++i)s.push_back(0);s.push_back(2);return s;
    }
    static std::vector<uint8_t> decode(const std::vector<unsigned>&s){
        std::vector<bool> bits;bool j=true;unsigned ones=0,se0=0;
        for(auto v:s){if(v==0){++se0;continue;}if(se0){if(se0<2||v!=2)throw std::runtime_error("device EOP invalid");break;}
            if(v==3)throw std::runtime_error("device emitted SE1");bool now=v==2,d=now==j;j=now;
            if(ones==6){if(d)throw std::runtime_error("device stuffing invalid");ones=0;continue;}
            bits.push_back(d);ones=d?ones+1:0;
        }
        if(bits.size()%8)throw std::runtime_error("device partial byte");
        std::vector<uint8_t>b(bits.size()/8);for(unsigned i=0;i<bits.size();++i)b[i/8]|=uint8_t(bits[i])<<(i%8);
        if(b.empty()||b[0]!=128)throw std::runtime_error("device SYNC invalid");b.erase(b.begin());
        if(b.empty()||uint8_t((b[0]>>4)^(b[0]&15))!=15)throw std::runtime_error("device PID invalid");
        if(b[0]==0xc3||b[0]==0x4b){if(b.size()<3)throw std::runtime_error("missing DATA CRC");std::vector<uint8_t>data(b.begin()+1,b.end()-2);auto c=crc16(data);if(b[b.size()-2]!=uint8_t(c)||b.back()!=uint8_t(c>>8))throw std::runtime_error("device CRC16 invalid");}
        return b;
    }
    void observe(bool en,bool p,bool n){
        if(en&&!last_enable){capturing=true;capture_cycle=0;symbols.clear();}
        if(en&&capturing){if(capture_cycle%4==2)symbols.push_back((unsigned(p)<<1)|n);++capture_cycle;}
        if(!en&&last_enable&&capturing){capturing=false;replies.push_back(decode(symbols));}
        last_enable=en;
    }
    void cycles(unsigned n){for(unsigned i=0;i<n;++i)tick();}
    void packet(std::vector<uint8_t>b,bool stuff=false,unsigned eop=2){
        b.insert(b.begin(),128);auto s=encode(b,stuff,eop);host_enable=true;
        for(auto v:s){dp=(v&2)!=0;dn=(v&1)!=0;cycles(4);}host_enable=false;dp=true;dn=false;
    }
    void token(unsigned pid,unsigned ep){unsigned v=address|(ep<<7);v|=crc5(v)<<11;packet({uint8_t(pid),uint8_t(v),uint8_t(v>>8)});}
    std::vector<uint8_t> wait(unsigned timeout=4000){for(unsigned i=0;i<timeout&&replies.empty();++i)cycles(1);if(replies.empty())return {};auto b=replies.front();replies.pop_front();return b;}
    std::vector<uint8_t> out(unsigned ep,const std::vector<uint8_t>&data,bool toggle=false,unsigned pid=0xe1,bool bad_crc=false,bool bad_stuff=false,unsigned eop=2){
        token(pid,ep);cycles(8);auto c=crc16(data);std::vector<uint8_t>b{uint8_t(toggle?0x4b:0xc3)};b.insert(b.end(),data.begin(),data.end());b.push_back(uint8_t(c)^(bad_crc?1:0));b.push_back(uint8_t(c>>8));packet(b,bad_stuff,eop);return wait();
    }
    std::vector<uint8_t> in(unsigned ep,bool ack=true){token(0x69,ep);auto b=wait();if(ack&&!b.empty()&&(b[0]==0xc3||b[0]==0x4b)){cycles(8);packet({0xd2});cycles(32);}return b;}
    static std::vector<uint8_t> setup(unsigned bm,unsigned request,unsigned value,unsigned index,unsigned length){return {uint8_t(bm),uint8_t(request),uint8_t(value),uint8_t(value>>8),uint8_t(index),uint8_t(index>>8),uint8_t(length),uint8_t(length>>8)};}
    void begin_control(unsigned bm,unsigned req,unsigned val,unsigned idx,unsigned len){auto r=out(0,setup(bm,req,val,idx,len),false,0x2d);if(r!=std::vector<uint8_t>{0xd2})throw std::runtime_error("SETUP not ACKed");cycles(32);}
    void no_data(unsigned bm,unsigned req,unsigned val,unsigned idx=0){begin_control(bm,req,val,idx,0);auto r=in(0);if(r!=std::vector<uint8_t>({0x4b,0,0}))throw std::runtime_error("control status IN invalid");cycles(32);}
    std::vector<uint8_t> control_in(unsigned bm,unsigned req,unsigned val,unsigned idx,unsigned len){
        begin_control(bm,req,val,idx,len);std::vector<uint8_t>result;bool toggle=true;
        while(result.size()<len){auto r=in(0);if(r.empty()||(r[0]!=(toggle?0x4b:0xc3))){std::cerr<<"control response bm="<<bm<<" req="<<req<<" val="<<val<<" length="<<len<<" have="<<result.size()<<" bytes=";for(auto v:r)std::cerr<<std::hex<<unsigned(v)<<' ';std::cerr<<std::dec<<'\n';throw std::runtime_error("control data PID/response invalid");}toggle=!toggle;unsigned n=unsigned(r.size()-3);result.insert(result.end(),r.begin()+1,r.end()-2);if(n<64)break;}
        auto r=out(0,{},true);if(r!=std::vector<uint8_t>{0xd2})throw std::runtime_error("control status OUT invalid");cycles(32);return result;
    }
    void sof(unsigned frame){unsigned v=frame&2047;v|=crc5(v)<<11;packet({0xa5,uint8_t(v),uint8_t(v>>8)});cycles(8);}
};
