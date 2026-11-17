// SPDX-License-Identifier: MIT
#include "Vrevc_usb_composite.h"
#include "verilated.h"
#include "usb_host.h"
#include <iostream>
#include <stdexcept>
static void need(bool b,const char*m){if(!b)throw std::runtime_error(m);}
struct Model {
    Vrevc_usb_composite d;UsbHost h;std::vector<uint32_t>midi;std::vector<uint8_t>cdc;
    Model(){h.tick=[this]{tick();};d.permit=1;d.usb_vbus=1;d.midi_ready=1;d.cdc_rx_ready=1;d.reset=1;h.cycles(32);d.reset=0;h.cycles(100);}
    void tick(){
        d.dp_in=d.tx_enable?d.dp_out:h.dp;d.dn_in=d.tx_enable?d.dn_out:h.dn;
        if(h.host_enable&&d.tx_enable)throw std::runtime_error("USB bus collision");
        d.clk=0;d.eval();if(d.midi_valid&&d.midi_ready)midi.push_back(d.midi_packet);
        if(d.cdc_rx_valid&&d.cdc_rx_ready)cdc.push_back(d.cdc_rx_data);
        d.clk=1;d.eval();h.observe(d.tx_enable,d.dp_out,d.dn_out);d.clk=0;d.eval();
    }
};
int main(){try{
    Model m;need(m.d.pullup_enable,"USB pullup disabled in simulation");
    auto d=m.h.control_in(0x80,6,0x100,0,18);
    need(d.size()==18&&d[8]==0xfe&&d[9]==0xca&&d[4]==0xef,"device descriptor");
    // SET_ADDRESS takes effect only after a complete host status ACK.
    m.h.begin_control(0,5,7,0,0);auto status=m.h.in(0,false);
    need(status==std::vector<uint8_t>({0x4b,0,0}),"address status");
    m.h.cycles(8);m.h.packet({0xd2,0});m.h.cycles(256);
    need(m.h.in(0,false)==status,"unACKed IN not retransmitted");
    m.h.cycles(8);m.h.packet({0xd2});m.h.cycles(64);m.h.address=7;
    auto c=m.h.control_in(0x80,6,0x200,0,255);need(c.size()==175&&c[4]==4,"configuration descriptor");
    m.h.no_data(0,9,1);need(m.d.configured,"not configured");m.h.sof(1);
    m.h.no_data(0x21,0x22,3);need(m.d.dtr,"DTR not set");
    auto line=m.h.control_in(0xa1,0x21,0,0,7);need(line==std::vector<uint8_t>({0,0xc2,1,0,0,0,8}),"line coding");
    auto r=m.h.out(3,{9,0x90,60,100});need(r==std::vector<uint8_t>{0xd2},"MIDI packet not ACKed");m.h.cycles(100);
    need(m.midi==std::vector<uint32_t>{0x643c9009},"MIDI bytes not delivered once");
    r=m.h.out(3,{9,0x90,60,100},false,0xe1,true);need(r.empty(),"bad CRC duplicate ACKed");m.h.cycles(64);need(m.midi.size()==1,"bad duplicate replayed");
    r=m.h.out(3,{9,0x90,60,100});need(r==std::vector<uint8_t>{0xd2},"duplicate not ACKed");m.h.cycles(100);need(m.midi.size()==1,"duplicate MIDI replayed");
    r=m.h.out(2,{'s','t','a','t','u','s','\n'});need(r==std::vector<uint8_t>{0xd2},"CDC OUT not ACKed");m.h.cycles(100);need(m.cdc.size()==7,"CDC bytes not delivered");
    // CDC ACM line coding data stage, notification split at MPS8 and bulk IN ZLP.
    m.h.begin_control(0x21,0x20,0,0,7);
    need(m.h.out(0,{0x80,0x25,0,0,0,0,8},true)==std::vector<uint8_t>{0xd2},"SET_LINE data");m.h.cycles(32);
    need(m.h.in(0)==std::vector<uint8_t>({0x4b,0,0}),"SET_LINE status");
    need(m.h.control_in(0xa1,0x21,0,0,7)==std::vector<uint8_t>({0x80,0x25,0,0,0,0,8}),"SET_LINE readback");
    auto notification=m.h.in(1);need(notification.size()==11&&notification[1]==0xa1&&notification[2]==0x20,"notification header");
    need(m.h.in(1).size()==5,"notification tail");
    m.d.cdc_tx_valid=1;
    for(unsigned n=0;n<64;++n){need(m.d.cdc_tx_ready,"CDC IN premature full");m.d.cdc_tx_data=n;m.h.cycles(1);}
    m.d.cdc_tx_valid=0;m.h.cycles(2);auto bulk=m.h.in(2);
    need(bulk.size()==67,"CDC full bulk packet");for(unsigned n=0;n<64;++n)need(bulk[n+1]==n,"CDC IN bytes");
    m.h.cycles(8);need(m.h.in(2).size()==3,"CDC missing terminating ZLP");
    auto nsetup=m.midi.size();need(m.h.out(3,{9,0x90,60,100},false,0x2d)==std::vector<uint8_t>{0x1e},"SETUP to bulk endpoint not STALLed");m.h.cycles(64);need(m.midi.size()==nsetup,"SETUP delivered as MIDI");
    // Invalid EOP must not commit. Valid retry uses the same DATA toggle.
    auto count=m.midi.size();m.h.out(3,{9,0x90,61,100},true,0xe1,false,false,1);m.h.cycles(100);
    need(m.midi.size()==count,"short EOP committed MIDI");
    // Bad CRC and stuff errors must not deliver application bytes or advance toggle.
    auto before=m.midi.size();
    r=m.h.out(3,{9,0x90,61,100},true,0xe1,true);need(r.empty(),"bad CRC ACKed");
    r=m.h.out(3,{9,0x90,0x7f,0x7f},true,0xe1,false,true);need(r.empty(),"bad stuff ACKed");
    m.h.cycles(64);need(m.midi.size()==before,"corrupt MIDI committed");
    r=m.h.out(3,{9,0x90,62,100},true);need(r==std::vector<uint8_t>{0xd2},"good retry not ACKed");m.h.cycles(64);need(m.midi.size()==before+1,"good retry lost");
    r=m.h.out(3,{9,0x90,63},false);need(r==std::vector<uint8_t>{0xd2},"misaligned MIDI transport ACK");m.h.cycles(64);need(m.midi.size()==before+1,"partial MIDI delivered");
    m.h.out(3,std::vector<uint8_t>(65,0x7f),true);m.h.cycles(100);need(m.midi.size()==before+1,"oversized MIDI delivered");
    // Halt and clear reset the OUT toggle. Unsupported requests STALL, next SETUP recovers.
    m.h.no_data(2,3,0,3);need(m.h.out(3,{9,0x90,64,100},true)==std::vector<uint8_t>{0x1e},"halt did not STALL");
    m.h.no_data(2,1,0,3);need(m.h.out(3,{9,0x90,64,100})==std::vector<uint8_t>{0xd2},"clear halt did not reset toggle");
    m.h.begin_control(0x80,6,0x600,0,10);need(m.h.in(0)==std::vector<uint8_t>{0x1e},"unsupported qualifier not STALLed");
    need(m.h.control_in(0x80,8,0,0,1)==std::vector<uint8_t>{1},"recovery from STALL");
    m.h.sof(2047);m.h.sof(0);m.h.cycles(100);need(m.d.online,"SOF wrap not accepted");
    m.h.cycles(145000);need(m.d.suspended&&!m.d.online,"missing SOF did not suspend");
    m.h.sof(1);m.h.cycles(100);need(m.d.online,"SOF resume");
    // A staged word must remain stable under backpressure, and flush must
    // discard both it and the remaining words without replay on ready.
    m.h.no_data(2,1,0,3);m.d.midi_ready=0;auto held_count=m.midi.size();
    need(m.h.out(3,{9,0x90,60,100,9,0x91,64,100})==std::vector<uint8_t>{0xd2},"buffered MIDI not ACKed");
    m.h.cycles(100);need(m.d.midi_valid&&m.d.midi_packet==0x643c9009,"staged first word");
    m.h.cycles(100);need(m.d.midi_valid&&m.d.midi_packet==0x643c9009&&m.midi.size()==held_count,"backpressured word changed");
    m.d.flush_midi=1;m.h.cycles(1);m.d.flush_midi=0;m.d.midi_ready=1;m.h.cycles(100);
    need(!m.d.midi_valid&&m.midi.size()==held_count,"flushed staged MIDI replayed");
    need(m.h.out(3,{9,0x92,67,100},true)==std::vector<uint8_t>{0xd2},"fresh post-flush MIDI not ACKed");m.h.cycles(100);
    need(m.midi.size()==held_count+1&&m.midi.back()==0x64439209,"fresh post-flush MIDI");
    m.d.usb_vbus=0;m.h.cycles(64);need(!m.d.pullup_enable&&!m.d.tx_enable&&!m.d.configured,"VBUS detach");
    std::cout<<"PASS USB PHY validation: unACKed IN retry, delayed address, CRC/stuff/EOP/oversize rejection, aligned/staged MIDI backpressure/flush, CDC line coding/notification/bulk/ZLP, HALT/CLEAR, STALL recovery, SOF wrap/suspend/resume, VBUS; smoke: descriptors, address, configuration, CDC class, CDC bytes, MIDI packet and duplicate\n";
    return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
