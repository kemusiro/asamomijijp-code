// SPDX-License-Identifier: MIT
#ifndef REVC_BOARD_H
#define REVC_BOARD_H
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>
#define PIN_A0 8u
#define PIN_RESET 9u
#define PIN_DATA 10u
#define PIN_BCLK 11u
#define PIN_LRCK 12u
#define PIN_CS 13u
#define PIN_WR 14u
#define PIN_RD 15u
#define PIN_FM_SD 16u
#define PIN_FM_CLK 17u
#define PIN_FM_SH 18u
#define PIN_LINE 19u
#define PIN_ARM 22u
#define PIN_DAC 26u
// GP20/21 are I2C0 open-drain on the approved host pins.
// GP27 (reserved) and GP28 (IRQ input) stay inputs.
typedef struct {
    atomic_uint ready,fault,pause,paused,heartbeat_us,blocks,peak,convert_max_us,queue_min,queue_max,i2s_div256,fm_gain_eighths,clipped_samples,rx_reject_observations;
} revc_audio_state;
extern revc_audio_state revc_audio;
// Written by core1 once,then published with release/acquire;read after failure.
// No USB output or heap allocation in the audio loop.
typedef struct {
    uint32_t reason,flags,block,index,word,before,after,gain_start,gain_end;
    atomic_uint valid;
} revc_rx_fault_state;
extern revc_rx_fault_state revc_rx_fault;
// One immutable snapshot before fault16 shuts DMA down. Channel order:
// RX0,RX1,TX0,TX1. The main core reads it only after valid release/acquire.
typedef struct {
    uint32_t fifo,fstat,fdebug,abort_mask,ctrl[4],remaining[4],dreq[4];
    atomic_uint valid;
} revc_tx_start_fault_state;
extern revc_tx_start_fault_state revc_tx_start_fault;
void revc_safe_gpio(void);
void revc_emergency(unsigned code);
bool revc_bus_start(void);
bool revc_bus_reset(void);
int revc_bus_write(void *unused,uint8_t reg,uint8_t value);
bool revc_bus_write_wait(uint8_t reg,uint8_t value);
bool revc_bus_check(void);
void revc_all_off(void);
void revc_gates(bool enable);
typedef struct {uint32_t writes,busy_retries,max_call_us;} revc_bus_stats;
extern revc_bus_stats revc_bus;
extern bool revc_bus_fast;
void revc_bus_clear_stats(void);
void revc_audio_core(void);
#endif
