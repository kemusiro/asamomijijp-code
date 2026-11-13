// SPDX-License-Identifier: MIT
// Native-only model SDK surface for the real audio.c loop.
#ifndef REVC_AUDIO_CORE_STUB_H
#define REVC_AUDIO_CORE_STUB_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {uint32_t fdebug,fstat,txf[4],rxf[4];} pio_hw_t;
typedef pio_hw_t *PIO;
extern pio_hw_t am_input,am_output;
#define pio0 (&am_input)
#define pio1 (&am_output)
typedef struct {unsigned unused;} pio_sm_config;
typedef struct {unsigned unused;} pio_program;
typedef struct {uint32_t ctrl;} dma_channel_config;
typedef struct {uint32_t ctrl_trig,al1_ctrl,transfer_count;} dma_model_channel;
typedef struct {dma_model_channel ch[16];uint32_t abort;} dma_model_hw;
typedef struct {uint32_t dbg_ctdreq;} dma_debug_channel;
typedef struct {dma_debug_channel ch[16];} dma_debug_model_hw;
extern dma_model_hw am_dma;
extern dma_debug_model_hw am_debug;
#define dma_hw (&am_dma)
#define dma_debug_hw (&am_debug)
#define DMA_CH0_CTRL_TRIG_EN_BITS 1u
#define DMA_CH0_CTRL_TRIG_BUSY_BITS (1u<<24)
#define PIO_FIFO_JOIN_RX 1
#define PIO_FIFO_JOIN_TX 2
#define DMA_SIZE_32 2
#define clk_sys 0
uint32_t time_us_32(void);uint64_t time_us_64(void);void tight_loop_contents(void);
unsigned clock_get_hz(unsigned);
unsigned pio_add_program(PIO,const pio_program *);
void pio_sm_claim(PIO,unsigned);void pio_gpio_init(PIO,unsigned);
void pio_sm_set_consecutive_pindirs(PIO,unsigned,unsigned,unsigned,bool);
void pio_sm_init(PIO,unsigned,unsigned,const pio_sm_config *);
void pio_sm_set_pins_with_mask(PIO,unsigned,uint32_t,uint32_t);
void pio_sm_exec(PIO,unsigned,unsigned);unsigned pio_encode_jmp(unsigned);
void pio_sm_restart(PIO,unsigned);void pio_sm_clear_fifos(PIO,unsigned);
void pio_sm_set_enabled(PIO,unsigned,bool);bool pio_sm_is_tx_fifo_full(PIO,unsigned);
unsigned pio_sm_get_tx_fifo_level(PIO,unsigned);
unsigned pio_get_dreq(PIO,unsigned,bool);void pio_interrupt_clear(PIO,unsigned);
bool pio_interrupt_get(PIO,unsigned);void pio_sm_set_clkdiv_int_frac8(PIO,unsigned,unsigned,uint8_t);
#define sm_config_set_in_pins(...) ((void)0)
#define sm_config_set_jmp_pin(...) ((void)0)
#define sm_config_set_in_shift(...) ((void)0)
#define sm_config_set_fifo_join(...) ((void)0)
#define sm_config_set_clkdiv(...) ((void)0)
#define sm_config_set_out_pins(...) ((void)0)
#define sm_config_set_sideset_pins(...) ((void)0)
#define sm_config_set_out_shift(...) ((void)0)
unsigned dma_claim_unused_channel(bool);
dma_channel_config dma_channel_get_default_config(unsigned);
void channel_config_set_chain_to(dma_channel_config *,unsigned);
void channel_config_set_dreq(dma_channel_config *,unsigned);
#define channel_config_set_transfer_data_size(...) ((void)0)
#define channel_config_set_read_increment(...) ((void)0)
#define channel_config_set_write_increment(...) ((void)0)
#define channel_config_set_ring(...) ((void)0)
#define channel_config_set_high_priority(...) ((void)0)
void dma_channel_configure(unsigned,const dma_channel_config *,volatile void *,const volatile void *,unsigned,bool);
void dma_channel_abort(unsigned);void dma_channel_set_write_addr(unsigned,volatile void *,bool);
void dma_channel_set_read_addr(unsigned,const volatile void *,bool);void dma_channel_set_trans_count(unsigned,unsigned,bool);
bool dma_channel_is_busy(unsigned);void dma_start_channel_mask(uint32_t);
void hw_clear_bits(volatile uint32_t *,uint32_t);void hw_set_bits(volatile uint32_t *,uint32_t);
#endif
