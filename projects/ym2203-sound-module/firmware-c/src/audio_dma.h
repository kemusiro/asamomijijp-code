// SPDX-License-Identifier: MIT
#ifndef REVC_AUDIO_DMA_H
#define REVC_AUDIO_DMA_H
// Called only on core1, with both PIO state machines disabled. RP2350-E5:
// disable every member of both DMA chains before aborting any member.
void revc_audio_dma_stop(const int rx[2],const int tx[2]);
// After FIFO reset and descriptor rearming: renew the peripheral DREQ handshake
// before enabling channels. This does not trigger any transfer.
void revc_audio_dma_enable(const int rx[2],const int tx[2]);
#endif
