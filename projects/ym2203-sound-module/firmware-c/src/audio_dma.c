// SPDX-License-Identifier: MIT
#include "audio_dma.h"
#include "hardware/dma.h"
#include "hardware/structs/dma_debug.h"
#include "pico/stdlib.h"

void revc_audio_dma_stop(const int rx[2],const int tx[2]){
    const int channels[]={rx[0],rx[1],tx[0],tx[1]};
    uint32_t mask=0;for(unsigned i=0;i<4;i++)mask|=1u<<channels[i];
    // AL1_CTRL is the non-triggering alias. Never write CTRL_TRIG to pause.
    for(unsigned i=0;i<4;i++)hw_clear_bits(&dma_hw->ch[channels[i]].al1_ctrl,DMA_CH0_CTRL_TRIG_EN_BITS);
    for(unsigned i=0;i<4;i++)dma_channel_abort((unsigned)channels[i]);
    // CHAN_ABORT must retire before descriptor writes or a new trigger.
    while(dma_hw->abort&mask)tight_loop_contents();
}
void revc_audio_dma_enable(const int rx[2],const int tx[2]){
    const int channels[]={rx[0],rx[1],tx[0],tx[1]};
    // CHx_DBG_CTDREQ is write-clear: renew credits after PIO FIFO resets.
    for(unsigned i=0;i<4;i++)dma_debug_hw->ch[channels[i]].dbg_ctdreq=0;
    for(unsigned i=0;i<4;i++)hw_set_bits(&dma_hw->ch[channels[i]].al1_ctrl,DMA_CH0_CTRL_TRIG_EN_BITS);
}
