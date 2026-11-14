// SPDX-License-Identifier: MIT
// Actual core1 loop with DMA chains, FIFO credits and repeated pause/resume.
// Injects stale credits after abort; does not claim the user's electrical trace.
#include "audio_core_stub.h"
#include "revc.h"
#include <setjmp.h>
#include <string.h>
pio_hw_t am_input,am_output;
dma_model_hw am_dma;
dma_debug_model_hw am_debug;
#ifdef REVC_AUDIO_LEGACY_SNAPSHOT
revc_tx_start_fault_state revc_tx_start_fault;
revc_tx_run_fault_state revc_tx_run_fault;
#endif
static jmp_buf finished;
static uint64_t now,ready_since,pause_since,next_done[16];
static unsigned claimed,targets,pauses,phase,unsafe_aborts,starts,level,force_failure,early_enable;
static bool drift_mode;
static int drift_ppm;
static uint32_t tx_div256;
static uint64_t drift_limit,trigger_at_q8;
static unsigned max_poll_us;
static bool input_on,output_on;
static unsigned reload[16];static volatile void *write_addr[16];
static const volatile void *read_addr[16];
static bool is_rx(unsigned ch){return ch%2==0;}
static void trigger(unsigned ch){
    if(!(am_dma.ch[ch].ctrl_trig&1)||!reload[ch]||(am_dma.ch[ch].ctrl_trig&DMA_CH0_CTRL_TRIG_BUSY_BITS))return;
    am_dma.ch[ch].ctrl_trig|=DMA_CH0_CTRL_TRIG_BUSY_BITS;
    am_dma.ch[ch].transfer_count=reload[ch];
    uint64_t period_q8=2250u*256u;
    if(drift_mode)period_q8=is_rx(ch)?(uint64_t)(2250ll*256ll*(1000000+drift_ppm)/1000000):2250ull*256u*tx_div256/12500u;
    next_done[ch]=(trigger_at_q8?trigger_at_q8:now*256u)+period_q8;
}
static void run(unsigned cycles,unsigned phase_us,unsigned fail){
    memset(&am_input,0,sizeof(am_input));memset(&am_output,0,sizeof(am_output));
    memset(&am_dma,0,sizeof(am_dma));memset(&am_debug,0,sizeof(am_debug));
    memset(&revc_audio,0,sizeof(revc_audio));memset(&revc_rx_fault,0,sizeof(revc_rx_fault));
    memset(&revc_tx_start_fault,0,sizeof(revc_tx_start_fault));
    memset(&revc_tx_run_fault,0,sizeof(revc_tx_run_fault));
    memset(reload,0,sizeof(reload));memset(next_done,0,sizeof(next_done));
    now=ready_since=pause_since=0;claimed=pauses=unsafe_aborts=starts=level=early_enable=0;
    targets=cycles;phase=phase_us;force_failure=fail;input_on=output_on=false;
    trigger_at_q8=0;tx_div256=12500;max_poll_us=0;
    atomic_store(&revc_audio.fm_gain_eighths,8);
    if(!setjmp(finished))revc_audio_core();
}
void am_run(unsigned cycles,unsigned phase_us,unsigned fail){drift_mode=false;run(cycles,phase_us,fail);}
void am_drift(int ppm,unsigned seconds){drift_mode=true;drift_ppm=ppm;drift_limit=(uint64_t)seconds*1000000;run(0,0,0);}
static void update(void){
    am_dma.abort=0; // Abort handshake completes on the next model bus tick.
    for(unsigned ch=0;ch<claimed;ch++){
        bool on=is_rx(ch)?input_on:output_on;
        if(!on||!(am_dma.ch[ch].ctrl_trig&1)||!(am_dma.ch[ch].ctrl_trig&DMA_CH0_CTRL_TRIG_BUSY_BITS)||now*256u<next_done[ch])continue;
        if(is_rx(ch)){
            uint32_t *out=(uint32_t *)write_addr[ch];
            for(unsigned i=0;i<125;i++)out[i]=0x600u<<19;
        }
        am_dma.ch[ch].transfer_count=0;
        am_dma.ch[ch].ctrl_trig&=~DMA_CH0_CTRL_TRIG_BUSY_BITS;
        trigger_at_q8=next_done[ch];trigger((am_dma.ch[ch].ctrl_trig>>8)&15);trigger_at_q8=0;
    }
    if(drift_mode){if(now>=drift_limit)longjmp(finished,1);return;}
    if(atomic_load(&revc_audio.paused)){
        ready_since=0;
        if(!pause_since)pause_since=now;
        if(now-pause_since>=4000){atomic_store(&revc_audio.pause,0);pause_since=0;pauses++;}
    }else if(atomic_load(&revc_audio.ready)){
        if(!ready_since)ready_since=now;
        if(force_failure==2&&now-ready_since>=1000){
            for(unsigned ch=0;ch<claimed;ch++)if(!is_rx(ch))am_dma.ch[ch].ctrl_trig&=~DMA_CH0_CTRL_TRIG_BUSY_BITS;
            force_failure=0;
        }
        if(pauses<targets&&now-ready_since>=phase)atomic_store(&revc_audio.pause,1);
        if(pauses==targets&&now-ready_since>=phase+10000)longjmp(finished,1);
    }
    if(now>100000000)longjmp(finished,1);
}
void tight_loop_contents(void){
    uint64_t before=now;
    // Once startup/abort handshakes retire, jump only across intervals with no
    // pending DMA completion. Model chain epochs retain sub-us clock phase.
    if(drift_mode&&output_on&&!am_dma.abort){
        uint64_t next=now*256u+256u*50u;
        for(unsigned ch=0;ch<claimed;ch++)if(am_dma.ch[ch].ctrl_trig&DMA_CH0_CTRL_TRIG_BUSY_BITS)
            if(next_done[ch]<next)next=next_done[ch];
        now=(next+255u)/256u;if(now<=before)now=before+1u;
    }else now++;
    if(now-before>max_poll_us)max_poll_us=(unsigned)(now-before);
    update();
}
uint32_t time_us_32(void){return (uint32_t)now;}
uint64_t time_us_64(void){return now;}
unsigned clock_get_hz(unsigned id){(void)id;return 150000000;}
unsigned pio_add_program(PIO p,const pio_program *code){(void)p;(void)code;return 0;}
void pio_sm_claim(PIO p,unsigned s){(void)p;(void)s;}
void pio_gpio_init(PIO p,unsigned pin){(void)p;(void)pin;}
void pio_sm_set_consecutive_pindirs(PIO p,unsigned s,unsigned a,unsigned n,bool d){(void)p;(void)s;(void)a;(void)n;(void)d;}
void pio_sm_init(PIO p,unsigned s,unsigned o,const pio_sm_config *c){(void)p;(void)s;(void)o;(void)c;}
void pio_sm_set_pins_with_mask(PIO p,unsigned s,uint32_t v,uint32_t m){(void)p;(void)s;(void)v;(void)m;}
void pio_sm_exec(PIO p,unsigned s,unsigned cmd){(void)p;(void)s;(void)cmd;}
unsigned pio_encode_jmp(unsigned o){return o;}
void pio_sm_restart(PIO p,unsigned s){(void)p;(void)s;}
void pio_sm_clear_fifos(PIO p,unsigned s){(void)s;if(p==pio1)level=0;}
void pio_sm_set_enabled(PIO p,unsigned s,bool enabled){
    (void)s;am_input.fdebug=am_output.fdebug=0; // Model W1C acknowledgements.
    if(p==pio0)input_on=enabled;else{output_on=enabled;if(enabled)starts++;}
}
static void fill_tx(void){
    if(output_on)return;
    for(unsigned ch=0;ch<claimed;ch++)if(!is_rx(ch)&&(am_dma.ch[ch].ctrl_trig&DMA_CH0_CTRL_TRIG_BUSY_BITS)){
        // A stale credit state cannot fill the reset8-word FIFO while SM waits.
        level=force_failure==1?0:am_debug.ch[ch].dbg_ctdreq?4:8;
    }
}
bool pio_sm_is_tx_fifo_full(PIO p,unsigned s){(void)p;(void)s;fill_tx();return level==8;}
unsigned pio_sm_get_tx_fifo_level(PIO p,unsigned s){(void)p;(void)s;return level;}
unsigned pio_get_dreq(PIO p,unsigned s,bool tx){(void)p;(void)s;return tx?1:0;}
void pio_interrupt_clear(PIO p,unsigned irq){(void)p;(void)irq;}
bool pio_interrupt_get(PIO p,unsigned irq){(void)p;(void)irq;return false;}
void pio_sm_set_clkdiv_int_frac8(PIO p,unsigned s,unsigned i,uint8_t f){(void)s;if(p==pio1)tx_div256=(i<<8)|f;}
unsigned dma_claim_unused_channel(bool required){(void)required;return claimed++;}
dma_channel_config dma_channel_get_default_config(unsigned ch){return (dma_channel_config){1u|(ch<<8)};}
void channel_config_set_chain_to(dma_channel_config *c,unsigned ch){c->ctrl=(c->ctrl&~(15u<<8))|(ch<<8);}
void channel_config_set_dreq(dma_channel_config *c,unsigned d){(void)c;(void)d;}
void dma_channel_configure(unsigned ch,const dma_channel_config *c,volatile void *w,const volatile void *r,unsigned n,bool start){
    am_dma.ch[ch].ctrl_trig=am_dma.ch[ch].al1_ctrl=c->ctrl;
    write_addr[ch]=w;read_addr[ch]=r;reload[ch]=am_dma.ch[ch].transfer_count=n;if(start)trigger(ch);
}
void dma_channel_abort(unsigned ch){
    am_dma.abort|=1u<<ch;
    for(unsigned i=0;i<claimed;i++)if(am_dma.ch[i].ctrl_trig&1){unsafe_aborts++;break;}
    am_dma.ch[ch].ctrl_trig&=~DMA_CH0_CTRL_TRIG_BUSY_BITS;
    // In-flight request state is deliberately stale across a FIFO reset unless
    // production code explicitly renews its peripheral handshake.
    am_debug.ch[ch].dbg_ctdreq=4;
}
void dma_channel_set_write_addr(unsigned ch,volatile void *p,bool start){write_addr[ch]=p;if(start)trigger(ch);}
void dma_channel_set_read_addr(unsigned ch,const volatile void *p,bool start){read_addr[ch]=p;if(start)trigger(ch);}
void dma_channel_set_trans_count(unsigned ch,unsigned n,bool start){reload[ch]=am_dma.ch[ch].transfer_count=n;if(start)trigger(ch);}
bool dma_channel_is_busy(unsigned ch){return !!(am_dma.ch[ch].ctrl_trig&DMA_CH0_CTRL_TRIG_BUSY_BITS);}
void dma_start_channel_mask(uint32_t mask){for(unsigned i=0;i<claimed;i++)if(mask&(1u<<i))trigger(i);}
static void alias_bits(volatile uint32_t *p,uint32_t bits,bool on){
    for(unsigned i=0;i<claimed;i++)if(p==&am_dma.ch[i].al1_ctrl){
        if(on&&am_dma.abort)early_enable++;
        if(on)am_dma.ch[i].ctrl_trig|=bits;else am_dma.ch[i].ctrl_trig&=~bits;
        am_dma.ch[i].al1_ctrl=am_dma.ch[i].ctrl_trig;return;
    }
}
void hw_clear_bits(volatile uint32_t *p,uint32_t bits){alias_bits(p,bits,false);}
void hw_set_bits(volatile uint32_t *p,uint32_t bits){alias_bits(p,bits,true);}
void revc_emergency(unsigned code){unsigned expected=0;atomic_compare_exchange_strong(&revc_audio.fault,&expected,code);}
unsigned am_get(unsigned field){
    switch(field){case 0:return atomic_load(&revc_audio.fault);case 1:return atomic_load(&revc_audio.ready);
    case 2:return pauses;case 3:return starts;case 4:return unsafe_aborts;case 5:return atomic_load(&revc_audio.blocks);
    case 6:return atomic_load(&revc_tx_start_fault.valid);case 7:return revc_tx_start_fault.fifo;
    case 8:{unsigned mask=0;for(unsigned i=0;i<claimed;i++)if(am_dma.ch[i].ctrl_trig&1)mask|=1u<<i;return mask;}
    case 9:return early_enable;
    case 10:return (unsigned)(now/1000);case 11:return tx_div256;case 12:return max_poll_us;
    case 13:return atomic_load(&revc_tx_run_fault.valid);case 14:return revc_tx_run_fault.reason;
    default:return 0;}
}
