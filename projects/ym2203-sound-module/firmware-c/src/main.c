// SPDX-License-Identifier: MIT
#include "revc.h"
#include "wym1.h"
#include "diagnostic.h"
#include "stream.h"
#include "transport.h"
#include "midi.h"
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/bootrom.h"
#include "hardware/watchdog.h"
#include "hardware/structs/usb.h"
#include "tusb.h"
#include "device/dcd.h"
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
extern const unsigned char revc_song[],revc_demo[];
extern const unsigned int revc_song_size,revc_song_crc,revc_demo_size,revc_demo_crc;
extern void revc_usb_identity_init(void);
static wym1_file song,demo;
static revc_player player;
static revc_stream stream;
static revc_midi midi;
static bool external_mode;
static uint8_t i2c_packet[REVC_PACKET_MAX],i2c_status[REVC_STATUS_SIZE];
static volatile bool usb_stop;
static volatile bool midi_usb_reset;
static uint64_t midi_discard_until;
static bool gates;
static unsigned dropped_logs;
static void log_line(const char *format,...) {
    if(!tud_cdc_connected()) return;
    char text[384];va_list ap;va_start(ap,format);int n=vsnprintf(text,sizeof(text)-2,format,ap);va_end(ap);
    if(n<0)return;
    if(n>(int)sizeof(text)-3)n=(int)sizeof(text)-3;
    text[n++]='\r';text[n++]='\n';
    if(tud_cdc_write_available()>=(uint32_t)n){tud_cdc_write(text,(uint32_t)n);tud_cdc_write_flush();}else dropped_logs++;
}
static void status(void) {
    unsigned state=midi.owned?1:external_mode?(stream.state==STREAM_RUNNING?1:stream.state==STREAM_DONE?2:stream.state>=STREAM_STOPPED?3:0):player.state;
    const uint32_t *hist=external_mode?stream.late_hist:player.late_hist;
    log_line("STATUS C=0.5.0-alpha.3 audio_ready=%u fault=%u state=%u events=%lu/%lu gates=%u fm_gain_eighths=%u",
      atomic_load(&revc_audio.ready),atomic_load(&revc_audio.fault),state,(unsigned long)(external_mode?stream.executed:player.index),
      (unsigned long)(external_mode?stream.total:player.file?player.file->count:0),gates,atomic_load(&revc_audio.fm_gain_eighths));
    log_line("AUDIO blocks=%u peak=%u max_convert_us=%u queue_min=%u queue_max=%u i2s_div256=%u log_drops=%u",
      atomic_load(&revc_audio.blocks),atomic_load(&revc_audio.peak),atomic_load(&revc_audio.convert_max_us),
      atomic_load(&revc_audio.queue_min),atomic_load(&revc_audio.queue_max),atomic_load(&revc_audio.i2s_div256),dropped_logs);
    log_line("PIPELINE input=%u output=%u prime=%u nominal_delay_us=%u;excludes serial,FIFO and DAC",
      REVC_STREAM_INPUT_FRAMES,REVC_STREAM_OUTPUT_FRAMES,REVC_PRIME_BLOCKS,REVC_NOMINAL_DELAY_US);
    log_line("RX qualify_ticks=2 pio_hz=32000000 reject_observations=%u;sticky observations,not pulse count",
      atomic_load(&revc_audio.rx_reject_observations));
    if(atomic_load_explicit(&revc_tx_start_fault.valid,memory_order_acquire)){
        log_line("TXSTART fifo=%lu fstat=%08lx fdebug=%08lx abort=%08lx ctrl_rx=%08lx,%08lx ctrl_tx=%08lx,%08lx",
          (unsigned long)revc_tx_start_fault.fifo,(unsigned long)revc_tx_start_fault.fstat,
          (unsigned long)revc_tx_start_fault.fdebug,(unsigned long)revc_tx_start_fault.abort_mask,
          (unsigned long)revc_tx_start_fault.ctrl[0],(unsigned long)revc_tx_start_fault.ctrl[1],
          (unsigned long)revc_tx_start_fault.ctrl[2],(unsigned long)revc_tx_start_fault.ctrl[3]);
        log_line("TXDMA remain_rx=%lu,%lu remain_tx=%lu,%lu dreq_rx=%lu,%lu dreq_tx=%lu,%lu",
          (unsigned long)revc_tx_start_fault.remaining[0],(unsigned long)revc_tx_start_fault.remaining[1],
          (unsigned long)revc_tx_start_fault.remaining[2],(unsigned long)revc_tx_start_fault.remaining[3],
          (unsigned long)revc_tx_start_fault.dreq[0],(unsigned long)revc_tx_start_fault.dreq[1],
          (unsigned long)revc_tx_start_fault.dreq[2],(unsigned long)revc_tx_start_fault.dreq[3]);
    }
    if(atomic_load_explicit(&revc_rx_fault.valid,memory_order_acquire)){
        log_line("RXFAULT reason=%u flags=%u block=%u index=%u word=%08lx before=%08lx after=%08lx gain_q10=%u..%u",
          revc_rx_fault.reason,revc_rx_fault.flags,revc_rx_fault.block,revc_rx_fault.index,
          (unsigned long)revc_rx_fault.word,(unsigned long)revc_rx_fault.before,(unsigned long)revc_rx_fault.after,
          revc_rx_fault.gain_start,revc_rx_fault.gain_end);
    }
    log_line("DIAG state=%u ready=%u bytes=%u",revc_diag_state(),revc_diag_state()==3,revc_diag_state()==3?REVC_DIAG_BYTES:0);
    log_line("LEVEL clipped_samples=%u;since last play/test;100percent=unity,200percent=2x",
      atomic_load(&revc_audio.clipped_samples));
    log_line("BUS mode=%s writes=%lu busy_retries=%lu max_call_us=%lu",
      revc_bus_fast?"fast":"slow",(unsigned long)revc_bus.writes,(unsigned long)revc_bus.busy_retries,(unsigned long)revc_bus.max_call_us);
    log_line("TIMING max_dispatch_late_us=%lu bins_lt1_5_10_20_100ms=%lu,%lu,%lu,%lu,%lu",
      (unsigned long)(external_mode?stream.max_late_us:player.max_late_us),(unsigned long)hist[0],(unsigned long)hist[1],
      (unsigned long)hist[2],(unsigned long)hist[3],(unsigned long)hist[4]);
    log_line("I2C protocol=2 address=0x42 state=%u result=%u error=%u received=%lu executed=%lu/%lu queued=%lu min_queue=%lu sealed=%u",
      stream.state,stream.result,stream.error,(unsigned long)stream.received,(unsigned long)stream.executed,(unsigned long)stream.total,
      (unsigned long)(stream.write-stream.read),(unsigned long)stream.min_queue,stream.sealed);
    log_line("MIDI protocol=1 owned=%u state=%u mask=%u gate=%u received=%lu applied=%lu rejected=%lu invalid=%lu ignored=%lu panics=%lu",
      midi.owned,midi.state,revc_midi_mask(&midi),midi.gate,(unsigned long)midi.received,(unsigned long)midi.applied,
      (unsigned long)midi.rejected,(unsigned long)midi.invalid,(unsigned long)midi.ignored,(unsigned long)midi.panics);
}
static void stop(const char *why) {
    revc_diag_abort();revc_stream_stop(&stream);
    revc_player_stop(&player);revc_all_off();gates=false;log_line("STOP %s;outputs muted;no automatic replay",why);
    revc_midi_cancel(&midi);midi_discard_until=time_us_64()+200000u;
}
void tud_umount_cb(void){usb_stop=true;midi_usb_reset=true;}
void tud_suspend_cb(bool remote_wakeup_en){(void)remote_wakeup_en;usb_stop=true;midi_usb_reset=true;}
void tud_cdc_line_state_cb(uint8_t itf,bool dtr,bool rts){(void)itf;(void)rts;if(!dtr)usb_stop=true;}
void tud_event_hook_cb(uint8_t rhport,uint32_t eventid,bool in_isr){
    (void)rhport;(void)in_isr;
    // A bus reset can keep SOFs moving: record it separately from the watchdog.
    if(eventid==DCD_EVENT_BUS_RESET||eventid==DCD_EVENT_UNPLUGGED||eventid==DCD_EVENT_SUSPEND)midi_usb_reset=true;
}
static bool reset_for_play(void) {
    atomic_store_explicit(&revc_audio.pause,1,memory_order_release);
    uint64_t deadline=time_us_64()+100000;
    while(!atomic_load_explicit(&revc_audio.paused,memory_order_acquire)) {
        tud_task();watchdog_update();
        if(atomic_load(&revc_audio.fault)||time_us_64()>=deadline) {
            revc_emergency(13);atomic_store(&revc_audio.pause,0);return false;
        }
    }
    revc_diag_reset();
    bool okay=revc_bus_reset();
    atomic_store_explicit(&revc_audio.pause,0,memory_order_release);
    deadline=time_us_64()+100000;
    while(okay&&!atomic_load_explicit(&revc_audio.ready,memory_order_acquire)) {
        tud_task();watchdog_update();
        if(atomic_load(&revc_audio.fault)||time_us_64()>=deadline)okay=false;
    }
    if(!okay)revc_emergency(13);
    return okay;
}
static unsigned prepare_i2c(void *unused){
    (void)unused;
    if(player.state==PLAYER_RUNNING||midi.owned)return S_STATE;
    if(atomic_load(&revc_audio.fault)||!atomic_load(&revc_audio.ready)){
        log_line("I2C BEGIN rejected: audio_ready=%u fault=%u",atomic_load(&revc_audio.ready),atomic_load(&revc_audio.fault));return S_AUDIO;
    }
    revc_diag_abort();revc_player_stop(&player);revc_all_off();gates=false;
    if(!reset_for_play()||atomic_load(&revc_audio.fault)||!atomic_load(&revc_audio.ready)){
        log_line("I2C BEGIN reset failed: audio_ready=%u fault=%u",atomic_load(&revc_audio.ready),atomic_load(&revc_audio.fault));return S_AUDIO;
    }
    external_mode=true;atomic_store(&revc_audio.peak,0);atomic_store(&revc_audio.clipped_samples,0);revc_bus_clear_stats();return S_OK;
}
static bool prepare_midi(void){
    revc_diag_abort();revc_player_stop(&player);revc_all_off();gates=false;
    if(!reset_for_play()||atomic_load(&revc_audio.fault)||!atomic_load(&revc_audio.ready)){
        revc_midi_cancel(&midi);return false;
    }
    external_mode=false;atomic_store(&revc_audio.peak,0);atomic_store(&revc_audio.clipped_samples,0);revc_bus_clear_stats();
    return true;
}
static void service_midi(uint64_t now,bool online){
    bool blocked=now<midi_discard_until||revc_stream_owned(&stream)||stream.state==STREAM_FAULT||player.state==PLAYER_RUNNING||!online||!atomic_load(&revc_audio.ready);
    uint8_t packet[4];unsigned budget=4;
    while(budget--&&tud_midi_packet_read(packet)){
        if(now<midi_discard_until||!online){midi.ignored++;continue;}
        unsigned action=revc_midi_message(&midi,packet,blocked);
        if(action==MIDI_PANIC){stop("MIDI panic");return;}
        if(action==MIDI_START&&!prepare_midi())return;
    }
    if(!midi.owned)return;
    revc_midi_tick(&midi,time_us_64(),revc_bus_write,NULL);
    if(midi.state==MIDI_FAULT){stop("MIDI bus failure");revc_emergency(17);return;}
    if(gates!=midi.gate){revc_gates(midi.gate);gates=midi.gate;}
    // Ordinary Note Off release is not a safety stop. Its135ms tail already
    // drained prior audio; a new Note On must not hit STOP's200ms discard.
    if(!midi.owned){revc_gates(false);gates=false;}
}
// Dump only a sealed snapshot while all outputs are muted. This transfer may
// block core0 briefly;it never blocks an audible performance. Any received byte,
// disconnect,or10s deadline aborts. Core1 keeps its normal silent stream service.
static bool dump_line(const char *text,uint64_t deadline){
    size_t n=strlen(text);unsigned sent=0;
    while(sent<n){
        tud_task();watchdog_update();
        bool cancelled=false;
        while(tud_cdc_available()){char ch;if(tud_cdc_read(&ch,1)==1&&ch!='\r'&&ch!='\n')cancelled=true;}
        if(!tud_cdc_connected()||cancelled||time_us_64()>=deadline){tud_cdc_read_flush();return false;}
        sent+=tud_cdc_write(text+sent,(uint32_t)(n-sent));tud_cdc_write_flush();
    }
    return true;
}
static void dump(void){
    const uint8_t *data=revc_diag_data();
    if(!data||player.state==PLAYER_RUNNING||revc_stream_owned(&stream)||midi.owned||gates){log_line("ERROR no sealed capture;run capture 31 and wait for DONE");return;}
    uint64_t deadline=time_us_64()+10000000u;uint32_t crc=revc_crc32(data,REVC_DIAG_BYTES);
    char line[280];snprintf(line,sizeof(line),"DIAGBEGIN %u %08lx\r\n",REVC_DIAG_BYTES,(unsigned long)crc);
    if(!dump_line(line,deadline))goto aborted;
    static const char hex[]="0123456789abcdef";
    for(unsigned p=0;p<REVC_DIAG_BYTES;){
        memcpy(line,"DIAGDATA ",9);unsigned used=9;
        for(unsigned i=0;i<128&&p<REVC_DIAG_BYTES;i++,p++){line[used++]=hex[data[p]>>4];line[used++]=hex[data[p]&15];}
        line[used++]='\r';line[used++]='\n';line[used]=0;
        if(!dump_line(line,deadline))goto aborted;
    }
    if(!dump_line("DIAGEND\r\n",deadline))goto aborted;
    return;
aborted:
    log_line("DIAGABORT transfer interrupted;outputs remain muted;dump can be retried");
}
static int score_write(void *unused,uint8_t reg,uint8_t value){
    int result=revc_bus_write(unused,reg,value);
    if(result==1)revc_diag_trace(time_us_64(),reg,value);
    return result;
}
static void command(const char *text) {
    if(!strcmp(text,"dump")){dump();return;}
    if(!strncmp(text,"bus",3)) {
        if(strcmp(text,"bus fast")&&strcmp(text,"bus slow")){log_line("ERROR use bus fast or bus slow;while stopped");return;}
        if(player.state==PLAYER_RUNNING||revc_stream_owned(&stream)||midi.owned){log_line("ERROR stop playback before changing bus timing");return;}
        revc_bus_fast=!strcmp(text,"bus fast");status();return;
    }
    if(!strncmp(text,"fm",2)) {
        if(revc_diag_state()==1||revc_diag_state()==2){log_line("ERROR FM gain is fixed during capture;stop first");return;}
        unsigned gain;
        if(!revc_parse_fm_gain(text,&gain)){log_line("ERROR use fm 0..16;fm 8=100percent,16=200percent,0=FM mute");return;}
        atomic_store_explicit(&revc_audio.fm_gain_eighths,gain,memory_order_release);
        log_line("FM gain target=%u/8;11.25ms ramp;SSG registers unchanged",gain);status();return;
    }
    if(!strcmp(text,"reboot")||!strcmp(text,"bootsel")) {
        stop("firmware reset");revc_emergency(14);
        if(!strcmp(text,"bootsel"))reset_usb_boot(0,0);
        watchdog_reboot(0,0,50);while(true)tight_loop_contents();
    }
    if(!strcmp(text,"stop")||!strcmp(text,"s")){stop("explicit");status();return;}
    if(!strcmp(text,"status")||!strcmp(text,"help")) {
        status();log_line("READY: test=13s original FM scale,SSG scale,six-voice chord;play=embedded WYM1;stop/status/help;fm 0..16 (default8=unity);bus fast/slow while stopped;capture 30..33,dump");
        log_line("SONG events=%lu period_ms=%lu CRC32=%08lx;I2C v2=0x42 100kHz;USB-MIDI1..6=FM3+SSG3;no REPL;reboot/bootsel available",
          (unsigned long)song.count,(unsigned long)song.period_ms,(unsigned long)revc_song_crc);return;
    }
    unsigned capture_second=0;
    if(!strncmp(text,"capture",7)&&!revc_parse_capture(text,&capture_second)){log_line("ERROR use capture 30,31,32 or33");return;}
    if(capture_second&&song.period_ms<(capture_second+3u)*1000u){log_line("ERROR song too short for this capture;outputs stay muted");status();return;}
    if(!strcmp(text,"play")||!strcmp(text,"test")||capture_second) {
        if(revc_stream_owned(&stream)){log_line("ERROR I2C owns playback;STOP before USB play/test/capture");return;}
        if(midi.owned){log_line("ERROR MIDI owns playback;STOP before USB play/test/capture");return;}
        external_mode=false;
        if(atomic_load_explicit(&revc_audio.fault,memory_order_acquire)||!atomic_load_explicit(&revc_audio.ready,memory_order_acquire)) {
            log_line("ERROR audio not ready/fault;outputs stay muted;reboot after saving log");return;
        }
        stop("prepare");if(atomic_load(&revc_audio.fault)||!reset_for_play())return;
        atomic_store(&revc_audio.peak,0);atomic_store(&revc_audio.clipped_samples,0);
        revc_bus_clear_stats();
        const wym1_file *f=!strcmp(text,"test")?&demo:&song;
        // No free-form user time input:one-shot bounded WYM1 period and no auto-start.
        uint64_t origin=time_us_64()+250000u;
        if(capture_second&&!revc_diag_arm(origin,capture_second,atomic_load(&revc_audio.fm_gain_eighths),revc_bus_fast,revc_song_crc,song.count)){
            log_line("ERROR cannot arm diagnostic;outputs stay muted");return;
        }
        revc_player_start(&player,f,origin);
        log_line("PLAY %s events=%lu period_ms=%lu starts in250ms;register order preserved",text,(unsigned long)f->count,(unsigned long)f->period_ms);return;
    }
    log_line("ERROR unknown command;use help/play/test/stop/status");
}
int main(void) {
    revc_safe_gpio();revc_stream_init(&stream);revc_midi_init(&midi);
    revc_usb_identity_init();tusb_init();
    bool valid=revc_crc32(revc_song,revc_song_size)==revc_song_crc &&
      revc_crc32(revc_demo,revc_demo_size)==revc_demo_crc &&
      wym1_open(&song,revc_song,revc_song_size)==WYM_OK && wym1_open(&demo,revc_demo,revc_demo_size)==WYM_OK;
    if(!valid||!revc_bus_start()||!revc_bus_check()) revc_emergency(11);
    if(!atomic_load(&revc_audio.fault))multicore_launch_core1(revc_audio_core);
    revc_i2c_init();revc_stream_status(&stream,i2c_status,time_us_64(),!atomic_load(&revc_audio.fault)&&atomic_load(&revc_audio.ready));revc_i2c_publish(i2c_status);
    watchdog_enable(1200,true);
    char line[48];unsigned used=0;bool overflow=false;bool announced=false,fault_reported=false;
    uint64_t next_publish=0;
    uint64_t next_progress=0;revc_usb_guard usb_guard={0},midi_guard={0};
    for(;;) {
        tud_task();
        if(usb_stop){usb_stop=false;used=0;overflow=false;tud_cdc_read_flush();if(!external_mode&&!midi.owned)stop("USB CDC close/suspend/disconnect");}
        if(midi_usb_reset){midi_usb_reset=false;if(midi.owned)stop("USB MIDI reset/suspend/disconnect");midi_discard_until=time_us_64()+200000u;}
        unsigned budget=64;
        while(budget--&&tud_cdc_connected()&&tud_cdc_available()) {
            char ch; if(tud_cdc_read(&ch,1)!=1)break;
            if(ch==3||ch==27){used=0;overflow=false;stop("control interrupt");}
            else if(ch=='\r'||ch=='\n') {
                if(overflow)log_line("ERROR command too long;discarded");
                else if(used){line[used]=0;command(line);}
                used=0;overflow=false;
            } else if(ch>=32&&ch<127){if(used<sizeof(line)-1)line[used++]=ch;else overflow=true;}
        }
        uint64_t now=time_us_64();
        bool usb_alive=revc_usb_alive(&usb_guard,now,(uint16_t)usb_hw->sof_rd,tud_mounted()&&tud_cdc_connected());
        bool midi_alive=revc_usb_alive(&midi_guard,now,(uint16_t)usb_hw->sof_rd,tud_mounted()&&!tud_suspended()&&tud_midi_mounted());
        if(midi.owned&&!midi_alive)stop("USB MIDI SOF timeout/offline");
        if(!external_mode&&player.state==PLAYER_RUNNING&&!usb_alive)stop("USB SOF timeout/offline");
        unsigned before_stream=stream.state;
        int packet_length=revc_i2c_pop(i2c_packet);
        if(packet_length<0){external_mode=true;revc_player_stop(&player);revc_stream_fail(&stream,S_IO);revc_all_off();gates=false;revc_midi_cancel(&midi);midi_discard_until=now+200000u;}
        else if(packet_length){
            revc_stream_command(&stream,i2c_packet,(unsigned)packet_length,now,prepare_i2c,NULL);
            now=time_us_64();
            if(stream.action==S_ACTION_STOP)stop("I2C explicit");
        }
        unsigned fault=atomic_load_explicit(&revc_audio.fault,memory_order_acquire);
        if(fault) {
            revc_midi_cancel(&midi);
            revc_diag_abort();if(revc_stream_owned(&stream))revc_stream_fail(&stream,S_AUDIO);
            if(!fault_reported&&tud_cdc_connected()){revc_gates(false);gates=false;revc_player_stop(&player);log_line("FAIL fault=%u;ARM=0 RESET=0 DAC=0 LINE=0;save log then reboot",fault);status();fault_reported=true;}
        } else {
            if(atomic_load_explicit(&revc_audio.ready,memory_order_acquire)&&!announced&&tud_cdc_connected()){command("help");announced=true;}
            if(revc_stream_owned(&stream)){
                // Expire the lease before opening output gates or applying data.
                revc_stream_tick(&stream,now,score_write,NULL);
                if(stream.state==STREAM_RUNNING&&now>=stream.origin_us&&!gates){revc_gates(true);gates=true;next_progress=now+30000000u;}
            }
            if(stream.state!=before_stream&&(stream.state==STREAM_DONE||stream.state==STREAM_FAULT)){
                revc_all_off();gates=false;
                if(stream.state==STREAM_DONE)log_line("DONE I2C all WYM1 events executed once;period complete;outputs muted");
                else log_line("FAIL I2C error=%u;outputs muted;explicit STOP/BEGIN required",stream.error);
                status();
            }else if(external_mode&&stream.state==STREAM_RUNNING&&gates&&now>=next_progress){status();next_progress=now+30000000u;}
            if(!external_mode&&player.state==PLAYER_RUNNING) {
                if(now>=player.origin_us&&!gates){revc_gates(true);gates=true;next_progress=now+30000000u;}
                revc_player_tick(&player,now,score_write,NULL);
                if(player.state==PLAYER_RUNNING&&!atomic_load(&revc_audio.fault)&&revc_diag_seal()){
                    stop("diagnostic capture complete");
                    log_line("DONE diagnostic snapshot ready;capture complete;outputs muted;use dump");status();
                }
                if(player.state==PLAYER_FAULT){stop("register deadline/BUSY failure");log_line("FAIL score deadline;save TIMING and AUDIO logs");status();}
                else if(player.state==PLAYER_DONE){revc_all_off();gates=false;log_line("DONE all WYM1 events executed once;period complete;outputs muted");status();}
                else if(now>=next_progress&&gates){status();next_progress=now+30000000u;}
            }
            service_midi(time_us_64(),midi_alive);
            uint32_t heartbeat=atomic_load_explicit(&revc_audio.heartbeat_us,memory_order_acquire);
            if(atomic_load(&revc_audio.ready)&&(uint32_t)(time_us_32()-heartbeat)>100000u)revc_emergency(12);
        }
        if(packet_length||now>=next_publish){
            revc_stream_status(&stream,i2c_status,now,!atomic_load(&revc_audio.fault)&&atomic_load(&revc_audio.ready));revc_i2c_publish(i2c_status);next_publish=now+1000u;
        }
        watchdog_update();tight_loop_contents();
    }
}
