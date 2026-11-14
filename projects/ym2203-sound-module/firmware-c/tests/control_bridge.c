// SPDX-License-Identifier: MIT
// Execute the actual main.c loop with scheduled USB/I2C events and fake hardware.
#include "control_stub.h"
#include <setjmp.h>
#define main firmware_main
#include "../src/main.c"
#undef main

revc_audio_state revc_audio;
revc_rx_fault_state revc_rx_fault;
revc_tx_start_fault_state revc_tx_start_fault;
revc_tx_run_fault_state revc_tx_run_fault;
revc_bus_stats revc_bus;
bool revc_bus_fast=true;
usb_model_regs model_usb_regs;
static jmp_buf done;
static uint64_t model_now,model_end;
static bool mounted=true,cdc=true,sof_running=true,suspended;
typedef struct {uint64_t when;unsigned kind,size;uint8_t data[208];} event;
static event events[160];static unsigned event_count,event_pos;
static uint8_t midi_rx[1024],i2c_rx[208];static unsigned midi_read,midi_write,i2c_size;
static char cdc_rx[128],logs[65536];static unsigned cdc_read_pos,cdc_write_pos,log_used;
static unsigned snapshots[32][15],snapshot_count,all_off_count;
static void snapshot(void){
    if(snapshot_count>=32)return;
    unsigned *p=snapshots[snapshot_count++];
    p[0]=midi.owned;p[1]=gates;p[2]=midi.state;p[3]=atomic_load(&revc_audio.fault);
    p[4]=stream.state;p[5]=stream.result;p[6]=stream.error;p[7]=stream.executed;
    p[8]=stream.received;p[9]=stream.total;p[10]=midi.rejected;p[11]=midi.invalid;
    p[12]=all_off_count;p[13]=midi.inflight;
    p[14]=revc_midi_mask(&midi);
}
void cm_clear(void){event_count=event_pos=0;}
void cm_add(uint64_t at_us,unsigned kind,const uint8_t *data,unsigned n){
    if(event_count>=160||n>208)return;
    event *e=&events[event_count++];e->when=at_us;e->kind=kind;e->size=n;if(n)memcpy(e->data,data,n);
}
void tud_task(void){
    model_now+=20;
    if(sof_running)model_usb_regs.sof_rd=(uint32_t)((model_now/1000)&2047);
    atomic_store(&revc_audio.heartbeat_us,(uint32_t)model_now);
    if(atomic_load(&revc_audio.pause)){atomic_store(&revc_audio.paused,1);atomic_store(&revc_audio.ready,0);}
    else{atomic_store(&revc_audio.paused,0);atomic_store(&revc_audio.ready,1);}
    while(event_pos<event_count&&events[event_pos].when<=model_now){
        event *e=&events[event_pos++];
        switch(e->kind){
        case 0:snapshot();break;
        case 1:for(unsigned i=0;i<e->size&&midi_write<sizeof(midi_rx);i++)midi_rx[midi_write++]=e->data[i];break;
        case 2:i2c_size=e->size;memcpy(i2c_rx,e->data,e->size);break;
        case 3:cdc=true;cdc_read_pos=0;cdc_write_pos=e->size;memcpy(cdc_rx,e->data,e->size);break;
        case 4:mounted=false;tud_umount_cb();break;
        case 5:tud_event_hook_cb(0,DCD_EVENT_BUS_RESET,true);break;
        case 6:cdc=false;tud_cdc_line_state_cb(0,false,false);break;
        case 7:sof_running=false;break;
        case 8:mounted=true;sof_running=true;break;
        case 9:suspended=true;tud_suspend_cb(false);break;
        }
    }
}
void cm_run(uint64_t until){
    model_now=0;model_end=until;mounted=cdc=sof_running=true;suspended=false;
    midi_read=midi_write=i2c_size=cdc_read_pos=cdc_write_pos=log_used=snapshot_count=all_off_count=0;
    memset(&revc_audio,0,sizeof(revc_audio));memset(&revc_rx_fault,0,sizeof(revc_rx_fault));
    memset(&revc_tx_start_fault,0,sizeof(revc_tx_start_fault));
    memset(&revc_tx_run_fault,0,sizeof(revc_tx_run_fault));
    memset(&player,0,sizeof(player));external_mode=gates=usb_stop=midi_usb_reset=false;
    midi_discard_until=0;dropped_logs=0;revc_diag_reset();
    atomic_store(&revc_audio.fm_gain_eighths,8);
    if(!setjmp(done))firmware_main();
    logs[log_used]=0;
}
unsigned cm_snap(unsigned index,unsigned field){return snapshots[index][field];}
unsigned cm_count(void){return snapshot_count;}
const char *cm_logs(void){return logs;}
uint64_t time_us_64(void){return model_now;}
uint32_t time_us_32(void){return (uint32_t)model_now;}
void tight_loop_contents(void){model_now+=30;if(model_now>=model_end)longjmp(done,1);}
void watchdog_update(void){}
void watchdog_enable(unsigned ms,bool pause){(void)ms;(void)pause;}
void watchdog_reboot(unsigned a,unsigned b,unsigned c){(void)a;(void)b;(void)c;longjmp(done,1);}
void reset_usb_boot(unsigned a,unsigned b){(void)a;(void)b;longjmp(done,1);}
void revc_usb_identity_init(void){}
void tusb_init(void){}
void revc_audio_core(void){}
void multicore_launch_core1(void (*fn)(void)){(void)fn;atomic_store(&revc_audio.ready,1);}
bool tud_cdc_connected(void){return mounted&&cdc;}
bool tud_mounted(void){return mounted;}
bool tud_suspended(void){return suspended;}
bool tud_midi_mounted(void){return mounted;}
void tud_cdc_read_flush(void){cdc_read_pos=cdc_write_pos;}
unsigned tud_cdc_available(void){return cdc_write_pos-cdc_read_pos;}
unsigned tud_cdc_read(void *p,unsigned n){if(n&&tud_cdc_available()){*(char *)p=cdc_rx[cdc_read_pos++];return 1;}return 0;}
unsigned tud_cdc_write_available(void){return (unsigned)sizeof(logs)-log_used-1;}
unsigned tud_cdc_write(const void *p,unsigned n){if(n<=tud_cdc_write_available()){memcpy(logs+log_used,p,n);log_used+=n;return n;}return 0;}
void tud_cdc_write_flush(void){}
bool tud_midi_packet_read(uint8_t p[4]){if(midi_write-midi_read<4)return false;memcpy(p,midi_rx+midi_read,4);midi_read+=4;return true;}
void revc_safe_gpio(void){}
void revc_emergency(unsigned code){atomic_store(&revc_audio.fault,code);gates=false;}
bool revc_bus_start(void){return true;}
bool revc_bus_check(void){return true;}
bool revc_bus_reset(void){return true;}
int revc_bus_write(void *p,uint8_t r,uint8_t v){(void)p;if(!revc_valid_register(r,v))return -1;revc_bus.writes++;return 1;}
void revc_all_off(void){gates=false;all_off_count++;}
void revc_gates(bool on){gates=on;}
void revc_bus_clear_stats(void){memset(&revc_bus,0,sizeof(revc_bus));}
void revc_i2c_init(void){}
int revc_i2c_pop(uint8_t *p){unsigned n=i2c_size;if(n){memcpy(p,i2c_rx,n);i2c_size=0;}return (int)n;}
void revc_i2c_publish(const uint8_t *p){(void)p;}
