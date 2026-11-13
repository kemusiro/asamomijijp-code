// SPDX-License-Identifier: MIT
#include "audio_start.h"
#include "hardware/dma.h"
#include "pico/stdlib.h"
bool revc_i2s_start(PIO output,unsigned sm,unsigned dma_channel){
    uint32_t started=time_us_32();
    dma_start_channel_mask(1u<<dma_channel);
    // DMA start is asynchronous. While the SM is disabled,DREQ can fill the
    // joined eight-word TX FIFO without consuming any PCM. Do not race the
    // first autopull against that initial DMA bus transaction.
    while(!pio_sm_is_tx_fifo_full(output,sm)){
        if((uint32_t)(time_us_32()-started)>=1000u)return false;
        tight_loop_contents();
    }
    // Clear the startup flag once,after priming. Runtime TXSTALL remains fatal.
    output->fdebug=1u<<(24+sm);
    pio_sm_set_enabled(output,sm,true);
    return true;
}
