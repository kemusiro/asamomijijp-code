// SPDX-License-Identifier: MIT
#ifndef REVC_AUDIO_START_H
#define REVC_AUDIO_START_H
#include <stdbool.h>
#include "hardware/pio.h"
// PIO is disabled;DMA descriptors and their PCM buffers are already published.
// False leaves the SM disabled;caller shuts down both directions and mutes.
bool revc_i2s_start(PIO output,unsigned sm,unsigned dma_channel);
#endif
