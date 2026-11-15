// SPDX-License-Identifier: MIT
#include "revc.h"
#include "wym1.h"
#include "diagnostic.h"
#include "audio_start.h"
#include "audio_dma.h"
#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/structs/dma_debug.h"
#include "hardware/pio.h"
#include "fm_rx.pio.h"
#include "i2s_tx.pio.h"
#include <string.h>
revc_audio_state revc_audio={.fm_gain_eighths=ATOMIC_VAR_INIT(8)};
revc_rx_fault_state revc_rx_fault;
revc_tx_start_fault_state revc_tx_start_fault;
revc_tx_run_fault_state revc_tx_run_fault;
static uint32_t raw[2][1024] __attribute__((aligned(4096)));
static uint32_t pcm[8][REVC_STREAM_OUTPUT_FRAMES];
static int rx[2],tx[2];
static PIO const input=pio0,output=pio1;
static const unsigned sm=0;
static bool dma_error(int channel){return (dma_hw->ch[channel].ctrl_trig>>29)!=0;}
static void shutdown(unsigned code) {
    revc_emergency(code);atomic_store_explicit(&revc_audio.ready,0,memory_order_release);
    pio_sm_set_enabled(input,sm,false);pio_sm_set_enabled(output,sm,false);
    revc_audio_dma_stop(rx,tx);
}
static void snapshot_tx_run(unsigned reason,uint32_t produced,const revc_tx_cursor *cursor,unsigned channel,uint32_t last_rx){
    revc_tx_run_fault.reason=reason;revc_tx_run_fault.produced=produced;
    revc_tx_run_fault.consumed=cursor->consumed;revc_tx_run_fault.pending=cursor->pending;
    revc_tx_run_fault.channel=channel;revc_tx_run_fault.fifo=pio_sm_get_tx_fifo_level(output,sm);
    revc_tx_run_fault.rx_age_us=time_us_32()-last_rx;
    revc_tx_run_fault.divider=atomic_load(&revc_audio.i2s_div256);
    for(unsigned i=0;i<2;i++){
        revc_tx_run_fault.ctrl[i]=dma_hw->ch[tx[i]].ctrl_trig;
        revc_tx_run_fault.remaining[i]=dma_hw->ch[tx[i]].transfer_count;
    }
    atomic_store_explicit(&revc_tx_run_fault.valid,1,memory_order_release);
}
static void snapshot_tx_start(void){
    const int channels[]={rx[0],rx[1],tx[0],tx[1]};
    revc_tx_start_fault.fifo=pio_sm_get_tx_fifo_level(output,sm);
    revc_tx_start_fault.fstat=output->fstat;revc_tx_start_fault.fdebug=output->fdebug;
    revc_tx_start_fault.abort_mask=dma_hw->abort;
    for(unsigned i=0;i<4;i++){
        revc_tx_start_fault.ctrl[i]=dma_hw->ch[channels[i]].ctrl_trig;
        revc_tx_start_fault.remaining[i]=dma_hw->ch[channels[i]].transfer_count;
        revc_tx_start_fault.dreq[i]=dma_debug_hw->ch[channels[i]].dbg_ctdreq;
    }
    atomic_store_explicit(&revc_tx_start_fault.valid,1,memory_order_release);
}
static void snapshot_fault(unsigned reason,unsigned flags,uint32_t block,const uint32_t *words,unsigned start,unsigned end){
    revc_bad_frame bad={UINT32_MAX,0,0,0};
    if(reason==1)revc_find_bad_frame(words,REVC_STREAM_INPUT_FRAMES,&bad);
    revc_rx_fault.reason=reason;revc_rx_fault.flags=flags;revc_rx_fault.block=block;
    revc_rx_fault.index=bad.index;revc_rx_fault.word=bad.word;
    revc_rx_fault.before=bad.before;revc_rx_fault.after=bad.after;
    revc_rx_fault.gain_start=start;revc_rx_fault.gain_end=end;
    atomic_store_explicit(&revc_rx_fault.valid,1,memory_order_release);
}
void revc_audio_core(void) {
    unsigned in_offset=pio_add_program(input,&fm_rx_program);
    unsigned out_offset=pio_add_program(output,&i2s_tx_program);
    pio_sm_claim(input,sm);pio_sm_claim(output,sm);
    for(unsigned pin=16;pin<=18;pin++) pio_gpio_init(input,pin);
    pio_sm_set_consecutive_pindirs(input,sm,16,3,false);
    pio_sm_config in=fm_rx_program_get_default_config(in_offset);
    sm_config_set_in_pins(&in,PIN_FM_SD);sm_config_set_jmp_pin(&in,PIN_FM_CLK);
    sm_config_set_in_shift(&in,true,true,24);
    sm_config_set_fifo_join(&in,PIO_FIFO_JOIN_RX);
    sm_config_set_clkdiv(&in,(float)clock_get_hz(clk_sys)/32000000.0f);
    pio_sm_init(input,sm,in_offset,&in);
    for(unsigned pin=10;pin<=12;pin++) pio_gpio_init(output,pin);
    pio_sm_config out=i2s_tx_program_get_default_config(out_offset);
    sm_config_set_out_pins(&out,PIN_DATA,1);sm_config_set_sideset_pins(&out,PIN_BCLK);
    sm_config_set_out_shift(&out,false,true,32);sm_config_set_fifo_join(&out,PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv(&out,(float)clock_get_hz(clk_sys)/(48000.0f*64));
    pio_sm_init(output,sm,out_offset,&out);
    pio_sm_set_consecutive_pindirs(output,sm,10,3,true);
    pio_sm_set_pins_with_mask(output,sm,0,7u<<10);
    pio_sm_exec(output,sm,pio_encode_jmp(out_offset+i2s_tx_offset_entry));
    for(unsigned i=0;i<2;i++){rx[i]=dma_claim_unused_channel(true);tx[i]=dma_claim_unused_channel(true);}
    for(unsigned i=0;i<2;i++) {
        dma_channel_config c=dma_channel_get_default_config(rx[i]);
        channel_config_set_transfer_data_size(&c,DMA_SIZE_32);
        channel_config_set_read_increment(&c,false);channel_config_set_write_increment(&c,true);
        channel_config_set_dreq(&c,pio_get_dreq(input,sm,false));
        channel_config_set_chain_to(&c,rx[1-i]);channel_config_set_ring(&c,true,12);
        channel_config_set_high_priority(&c,true);
        dma_channel_configure(rx[i],&c,raw[i],&input->rxf[sm],REVC_STREAM_INPUT_FRAMES,false);
        c=dma_channel_get_default_config(tx[i]);
        channel_config_set_transfer_data_size(&c,DMA_SIZE_32);
        channel_config_set_read_increment(&c,true);channel_config_set_write_increment(&c,false);
        channel_config_set_dreq(&c,pio_get_dreq(output,sm,true));channel_config_set_chain_to(&c,tx[1-i]);
        channel_config_set_high_priority(&c,true);
        dma_channel_configure(tx[i],&c,&output->txf[sm],pcm[i],REVC_STREAM_OUTPUT_FRAMES,false);
    }
restart:
    revc_audio_dma_stop(rx,tx);
    pio_sm_restart(input,sm);pio_sm_restart(output,sm);
    pio_sm_clear_fifos(input,sm);pio_sm_clear_fifos(output,sm);
    pio_sm_exec(input,sm,pio_encode_jmp(in_offset));
    pio_sm_exec(output,sm,pio_encode_jmp(out_offset+i2s_tx_offset_entry));
    for(unsigned i=0;i<2;i++) {
        dma_channel_set_write_addr(rx[i],raw[i],false);
        dma_channel_set_trans_count(rx[i],REVC_STREAM_INPUT_FRAMES,false);
        dma_channel_set_read_addr(tx[i],pcm[i],false);
        dma_channel_set_trans_count(tx[i],REVC_STREAM_OUTPUT_FRAMES,false);
    }
    revc_audio_dma_enable(rx,tx);
    input->fdebug=1u<<sm;output->fdebug=1u<<(24+sm);
    pio_interrupt_clear(input,0);atomic_store(&revc_audio.rx_reject_observations,0);
    dma_start_channel_mask(1u<<rx[0]);pio_sm_set_enabled(input,sm,true);
    unsigned initial_gain=atomic_load(&revc_audio.fm_gain_eighths)*128u;
    revc_gain_ramp gain={initial_gain,initial_gain,initial_gain,5};
    uint32_t produced=0;revc_tx_cursor cursor={0};unsigned ri=0,ti=0;bool sending=false;
    uint32_t last_rx=time_us_32(),measure_start=last_rx;unsigned measure_blocks=0;
    atomic_store(&revc_audio.queue_min,8);
    uint32_t initial_divider=(uint32_t)((clock_get_hz(clk_sys)*256ull+1536000u)/3072000u);
    pio_sm_set_clkdiv_int_frac8(output,sm,initial_divider>>8,(uint8_t)initial_divider);
    atomic_store(&revc_audio.i2s_div256,initial_divider);
    uint64_t divider_remainder=0;
    for(;;) {
        if(atomic_load_explicit(&revc_audio.pause,memory_order_acquire)) {
            pio_sm_set_enabled(input,sm,false);pio_sm_set_enabled(output,sm,false);
            revc_audio_dma_stop(rx,tx);
            atomic_store(&revc_audio.ready,0);
            atomic_store_explicit(&revc_audio.paused,1,memory_order_release);
            while(atomic_load_explicit(&revc_audio.pause,memory_order_acquire))tight_loop_contents();
            atomic_store(&revc_audio.paused,0);
            if(atomic_load_explicit(&revc_audio.fault,memory_order_acquire))return;
            goto restart;
        }
        if(pio_interrupt_get(input,0)){pio_interrupt_clear(input,0);atomic_fetch_add(&revc_audio.rx_reject_observations,1);}
        for(unsigned i=0;i<2;i++) if(dma_error(rx[i])||dma_error(tx[i])) {shutdown(1);return;}
        if(input->fdebug&(1u<<sm)) {shutdown(2);return;}
        if(sending&&(output->fdebug&(1u<<(24+sm)))) {shutdown(3);return;}
        if((uint32_t)(time_us_32()-last_rx)>50000u) {shutdown(4);return;}
        if(sending&&cursor.pending&&dma_channel_is_busy(tx[ti])){snapshot_tx_run(1,produced,&cursor,ti,last_rx);shutdown(5);return;}
        // A completed channel may wait briefly for RX conversion before being
        // rearmed. Its partner is already transmitting a published block.
        // Do not count consumption again while waiting for the same channel.
        if(sending&&!dma_channel_is_busy(tx[ti])) {
            if(!dma_channel_is_busy(tx[1-ti])) {snapshot_tx_run(2,produced,&cursor,ti,last_rx);shutdown(5);return;}
            uint32_t before=cursor.consumed;
            int slot=revc_tx_slot(&cursor,produced);
            if(before!=cursor.consumed){
                uint32_t occupancy=produced-cursor.consumed;
                if(occupancy<atomic_load(&revc_audio.queue_min))atomic_store(&revc_audio.queue_min,occupancy);
            }
            if(slot==-2){shutdown(6);return;}
            if(slot>=0){
                dma_channel_set_read_addr(tx[ti],pcm[slot],false);
                dma_channel_set_trans_count(tx[ti],REVC_STREAM_OUTPUT_FRAMES,false);ti=1-ti;
            }
        }
        if(!dma_channel_is_busy(rx[ri])) {
            if(!dma_channel_is_busy(rx[1-ri])) {shutdown(7);return;}
            if(produced-cursor.consumed>=8u) {shutdown(8);return;}
            uint32_t started=time_us_32(),peak=0,clipped=0;
            revc_diag_rx_frames(raw[ri],REVC_STREAM_INPUT_FRAMES,time_us_64());
            unsigned start_gain=0,end_gain=0;
            if(!revc_gain_step(&gain,atomic_load_explicit(&revc_audio.fm_gain_eighths,memory_order_acquire),&start_gain,&end_gain)){snapshot_fault(2,4,produced+1u,raw[ri],0,0);shutdown(9);return;}
            uint32_t flags=revc_convert_stream(raw[ri],pcm[produced&7u],&peak,start_gain,end_gain,&clipped);
            uint32_t elapsed=time_us_32()-started;
            if(flags&~2u) {snapshot_fault(1,flags,produced+1u,raw[ri],start_gain,end_gain);shutdown(9);return;}
            // Saturation above unity is counted,not hidden as a stream fault.
            if(clipped)atomic_fetch_add(&revc_audio.clipped_samples,clipped);
            if(elapsed>atomic_load(&revc_audio.convert_max_us)) atomic_store(&revc_audio.convert_max_us,elapsed);
            if(peak>atomic_load(&revc_audio.peak)) atomic_store(&revc_audio.peak,peak);
            // Ownership/stall checks before publishing the just-converted block.
            if(dma_channel_is_busy(rx[ri])||!dma_channel_is_busy(rx[1-ri])||(input->fdebug&(1u<<sm))) {shutdown(7);return;}
            dma_channel_set_write_addr(rx[ri],raw[ri],false);
            dma_channel_set_trans_count(rx[ri],REVC_STREAM_INPUT_FRAMES,false);ri=1-ri;
            produced++;last_rx=time_us_32();
            atomic_store(&revc_audio.blocks,produced);atomic_store(&revc_audio.heartbeat_us,last_rx);
            if(++measure_blocks==REVC_CLOCK_BLOCKS) {
                measure_blocks=0;
                uint32_t divider=revc_i2s_div256_carry(clock_get_hz(clk_sys),last_rx-measure_start,&divider_remainder);
                if(!divider){shutdown(15);return;}
                // Track the external YM oscillator,not an indefinitely assumed
                // exact4MHz. Carry the below-LSB remainder instead of building
                // up a fixed rounding bias in the short2-block audio queue.
                pio_sm_set_clkdiv_int_frac8(output,sm,divider>>8,(uint8_t)divider);
                atomic_store(&revc_audio.i2s_div256,divider);measure_start=last_rx;
            }
            if(produced-cursor.consumed>atomic_load(&revc_audio.queue_max)) atomic_store(&revc_audio.queue_max,produced-cursor.consumed);
            if(!sending&&produced>=REVC_PRIME_BLOCKS) {
                if(!revc_i2s_start(output,sm,(unsigned)tx[0])){snapshot_tx_start();shutdown(16);return;}
                sending=true;
                atomic_store_explicit(&revc_audio.ready,1,memory_order_release);
            }
        }
        tight_loop_contents();
    }
}
