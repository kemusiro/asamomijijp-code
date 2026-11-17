// SPDX-License-Identifier: MIT
#include "Vrevc_midi_planner.h"
#include "verilated.h"
#include <vector>
#include <stdexcept>
#include <iostream>
extern "C" {void mm_init();unsigned mm_packet(const uint8_t*,bool);void mm_advance(uint64_t);unsigned mm_get(unsigned);const uint8_t*mm_trace();bool revc_midi_pitch(unsigned,unsigned,uint8_t*,uint8_t*);}
static void need(bool b,const char*m){if(!b)throw std::runtime_error(m);}
struct Model {
 Vrevc_midi_planner d;std::vector<uint8_t>trace;unsigned age=0,r=0,v=0;bool hold=false;
 Model(){d.online=1;d.audio_ok=1;d.reset=1;tick();d.reset=0;d.now_us=200001;}
 void tick(){
  d.clk=0;d.prepare_done=d.prepare_request;d.silence_done=d.silence_request;d.eval();
  bool ready=false;
  if(d.event_valid){
   if(age){need(r==d.event_register&&v==d.event_value,"BUSY changed latched register");}
   else{r=d.event_register;v=d.event_value;}
   ++age;if(!hold&&age==31){ready=true;trace.push_back(uint8_t(r));trace.push_back(uint8_t(v));age=0;}
  }else age=0;
  d.event_ready=ready;d.eval();d.clk=1;d.eval();d.clk=0;d.eval();d.now_us++;
 }
 void advance(unsigned us){for(unsigned i=0;i<us;++i)tick();}
 void packet(unsigned cin,unsigned status,unsigned a,unsigned b,bool blocked=false){d.packet=(b<<24)|(a<<16)|(status<<8)|cin;d.packet_blocked=blocked;d.packet_valid=1;tick();d.packet_valid=0;d.packet_blocked=0;}
};
int main(){try{
 unsigned valid=0;
 for(unsigned voice=0;voice<6;++voice)for(unsigned note=0;note<128;++note){
  Model m;mm_init();uint8_t p[4]={9,uint8_t(0x90+voice),uint8_t(note),100};mm_packet(p,false);m.packet(p[0],p[1],p[2],p[3]);
  m.advance(16000);mm_advance(16000);std::vector<uint8_t>c(mm_trace(),mm_trace()+2*mm_get(4));
  need(m.trace==c,"setup/note trace differs from unchanged midi.c");
  uint8_t a=0,b=0;bool ok=revc_midi_pitch(voice,note,&a,&b);need(m.d.mask==(ok?(1u<<voice):0u),"mask/pitch validity mismatch");if(ok)++valid;
 }
 {Model m;m.d.blocked=1;m.packet(9,0x90,60,100);m.advance(100);need(!m.d.owned&&m.trace.empty(),"I2C block claimed MIDI");m.d.blocked=0;m.advance(100);need(!m.d.owned,"blocked note replayed");m.packet(9,0x90,60,100,true);need(!m.d.owned,"tagged stale note replayed");}
 {Model m;m.packet(9,0x90,60,100);m.advance(16000);need(m.d.gate,"note did not open gate");m.packet(8,0x80,61,0);m.advance(500);need(m.d.mask==1,"stale NoteOff cancelled current note");m.packet(9,0x90,60,0);m.advance(136000);need(!m.d.owned&&!m.d.gate,"release hold did not end ownership");}
 {Model m;m.packet(9,0x90,60,100);m.advance(16000);m.packet(0x19,0x90,61,100);need(m.d.mask==1,"other cable acted");m.packet(11,0xb6,120,0);need(m.d.owned,"unsupported CC channel panic");m.packet(11,0xb0,123,0);m.advance(500);need(m.d.mask==0,"CC123 channel off");m.packet(9,0x90,60,100);m.advance(500);m.packet(11,0xb0,120,0);m.advance(10);need(!m.d.owned&&!m.d.gate,"CC120 panic");m.packet(9,0x90,60,100);need(!m.d.owned,"quarantine replay");}
 {Model m;m.packet(9,0x90,60,100);m.advance(16000);m.hold=true;m.packet(9,0x90,62,100);m.advance(5);m.packet(8,0x80,62,0);m.advance(100100);need(m.d.fault&&!m.d.gate,"BUSY timeout not latched");}
 {Model m;m.packet(9,0x90,60,100);m.advance(16000);m.d.online=0;m.tick();need(!m.d.gate,"disconnect gate not closed");m.advance(10);need(!m.d.owned,"disconnect cleanup ownership");m.d.online=1;m.advance(201000);need(!m.d.owned,"reattach auto replay");}
 std::cout<<"PASS MIDI planner: 768 C pitch/setup/note comparisons ("<<valid<<" valid); immutable BUSY, stale off, CC120/123, cable/channel filters, ownership blocking/tagging, release hold, timeout, disconnect/quarantine\n";return 0;
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
