// SPDX-License-Identifier: MIT
// Behavioral I2C/register fixture, not an analog Si5351 or jitter model.
#pragma once
#include <array>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>
struct Si5351Fixture {
    static constexpr uint64_t hz=48000000;
    enum Phase {RX,ACK_SETUP,ACK_RISE,ACK_DONE,TX,TX_END,TX_ACK,TX_DONE,WAIT};
    std::array<uint8_t,256> regs{};
    std::vector<std::pair<unsigned,unsigned>> writes;
    bool scl=true,sda=true,old_scl=true,old_sda=true,slave=false,active=false,ack=false,read_next=false;
    bool nack_read_address=false;
    bool nack=false,hold_scl=false,hold_sda=false,forever_init=false,never_lock=false,loss=false,corrupt=false;
    unsigned byte=0,bits=0,number=0,pointer=0,tx=0,txbits=0,starts=0,stops=0,nacks=0,read_count=0;
    int nack_position=-1;
    Phase phase=RX;
    uint64_t last_edge=0;
    uint64_t reset_at=0,init_cycles=hz/50,lock_cycles=hz/500,stretch_until=0,stretch_cycles=0;
    bool stretched=false,last_master_scl=false;
    Si5351Fixture(){regs[15]=0xf3;regs[149]=0xd5;regs[177]=0x0c;regs[165]=regs[166]=0x80;}
    unsigned value(uint64_t cycle){
        if(pointer==0){
            if(forever_init||cycle<init_cycles)return 0x80;
            if(loss||never_lock||(reset_at&&cycle-reset_at<lock_cycles))return 0x60;
            return 0;
        }
        if(pointer==177&&reset_at&&cycle-reset_at>=lock_cycles)regs[177]&=~0xa0;
        return regs[pointer]^((corrupt&&pointer==183)?0x40:0);
    }
    void byte_received(uint64_t cycle){
        ack=!nack&&(nack_position<0||int(number)!=nack_position);read_next=false;
        if(number==0){ack=ack&&(byte>>1)==0x60&&!(nack_read_address&&(byte&1));if(ack&&(byte&1))read_next=true;}
        else if(ack&&number==1)pointer=byte;
        else if(ack){regs[pointer]=uint8_t(byte);writes.emplace_back(pointer,byte);if(pointer==177&&(byte&0xa0))reset_at=cycle;}
        ++number;phase=ACK_SETUP;
    }
    void update(uint64_t cycle,bool master_scl,bool master_sda){
        if(forever_init||cycle<init_cycles)regs[1]|=0x80;
        if(loss||never_lock||(reset_at&&cycle-reset_at<lock_cycles))regs[1]|=0x60;
        if(active&&last_master_scl&&!master_scl&&!stretched&&stretch_cycles){stretch_until=cycle+stretch_cycles;stretched=true;}
        last_master_scl=master_scl;
        scl=!(master_scl||hold_scl||cycle<stretch_until);sda=!(master_sda||slave||hold_sda);
        if(scl!=old_scl){
            if(active&&last_edge&&cycle-last_edge<192)throw std::runtime_error("SCL pulse shorter than 4us");
            last_edge=cycle;
        }
        bool start=old_sda&&!sda&&scl&&old_scl,stop=!old_sda&&sda&&scl&&old_scl;
        if(start){active=true;phase=RX;byte=bits=number=0;slave=false;stretched=false;++starts;}
        else if(stop){active=false;slave=false;++stops;}
        else if(active&&!old_scl&&scl){
            if(phase==RX){byte=(byte<<1)|unsigned(sda);if(++bits==8)byte_received(cycle);}
            else if(phase==ACK_RISE)phase=ACK_DONE;
            else if(phase==TX){if(++txbits==8)phase=TX_END;}
            else if(phase==TX_ACK){if(!sda)throw std::runtime_error("master ACKed single-byte read; expected NACK");++nacks;phase=TX_DONE;}
        } else if(active&&old_scl&&!scl){
            if(phase==ACK_SETUP){slave=ack;phase=ACK_RISE;}
            else if(phase==ACK_DONE){
                slave=false;
                if(!ack)phase=WAIT;
                else if(read_next){tx=value(cycle);++read_count;txbits=0;slave=!(tx&128);phase=TX;}
                else{bits=byte=0;phase=RX;}
            }else if(phase==TX){slave=!(tx&(128>>txbits));}
            else if(phase==TX_END){slave=false;phase=TX_ACK;}
            else if(phase==TX_DONE){slave=false;phase=WAIT;}
        }
        sda=!(master_sda||slave||hold_sda);old_scl=scl;old_sda=sda;
    }
    uint64_t ratio(unsigned address) const {
        const auto*d=regs.data()+address;
        uint64_t p1=((d[2]&3)<<16)|(d[3]<<8)|d[4];
        uint64_t p2=((d[5]&15)<<16)|(d[6]<<8)|d[7];
        uint64_t p3=((d[5]&240)<<12)|(d[0]<<8)|d[1];
        if(!p3)throw std::runtime_error("unprogrammed PLL denominator");
        return (p1+512)*p3+p2;
    }
    uint64_t denominator(unsigned address) const {
        const auto*d=regs.data()+address;return 128*(((d[5]&240)<<12)|(d[0]<<8)|d[1]);
    }
    void verify_frequency(unsigned f) const {
        uint64_t div0=ratio(42)/denominator(42),div1=ratio(50)/denominator(50);
        if(25000000*ratio(34)!=uint64_t(f)*denominator(34)*div0)throw std::runtime_error("YM frequency mismatch");
        if(25000000*ratio(26)!=49152000ull*denominator(26)*div1)throw std::runtime_error("audio frequency mismatch");
        if(regs[3]!=0xfc||regs[16]!=0x6c||regs[17]!=0x4c)throw std::runtime_error("output routing/enable mismatch");
        if((regs[15]&0xf3)!=0xf3||(regs[149]&0x7f)!=0x55||(regs[177]&0x0c)!=0x0c)throw std::runtime_error("reserved bits overwritten");
    }
};
