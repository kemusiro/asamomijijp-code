// SPDX-License-Identifier: MIT
#ifndef REVC_WYM1_H
#define REVC_WYM1_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define WYM1_MAX_EVENTS 131071u
#define REVC_INPUT_FRAMES 625u
#define REVC_OUTPUT_FRAMES 540u
// The legacy/RCD1 conversion unit stays625:540. Live DMA uses one fifth.
#define REVC_STREAM_INPUT_FRAMES 125u
#define REVC_STREAM_OUTPUT_FRAMES 108u
#define REVC_PRIME_BLOCKS 2u
#define REVC_CLOCK_BLOCKS 640u
#define REVC_NOMINAL_DELAY_US (REVC_STREAM_INPUT_FRAMES*18u*REVC_PRIME_BLOCKS)
#define REVC_PCM_MAX 32767
#define REVC_PCM_MIN (-32768)
#define REVC_LATE_US 100000u

typedef struct { const uint8_t *bytes; uint32_t count, period_ms; } wym1_file;
typedef enum { WYM_OK=0, WYM_SHAPE, WYM_CLOCK, WYM_TIME, WYM_REGISTER } wym1_error;
bool revc_valid_register(uint8_t reg, uint8_t value);
wym1_error wym1_open(wym1_file *out, const uint8_t *data, size_t size);
void wym1_event(const wym1_file *f, uint32_t index, uint32_t *ms, uint8_t *reg, uint8_t *value);
uint32_t revc_crc32(const uint8_t *data, size_t length);
// Internal rolling state:initial~0,final complement.
uint32_t revc_crc32_append(uint32_t state,const uint8_t *data,size_t length);
// Returns 0 on success;invalid exponent/overflow set bits1/2. Output is
// a MSB-first I2S word: left int16 in bits31..16,right digital channel zero.
uint32_t revc_convert(const uint32_t *input, uint32_t *output, uint32_t *peak);
// Gain0..16 represents0..2,with one-block linear ramp and no YM register changes.
// Above unity may saturate:flag2 is nonfatal and clipped counts output samples.
// Invalid gain returns flag4 with zero output;valid PCM includes -32768.
uint32_t revc_convert_gain(const uint32_t *input,uint32_t *output,uint32_t *peak,unsigned start,unsigned end);
uint32_t revc_convert_gain_ex(const uint32_t *input,uint32_t *output,uint32_t *peak,unsigned start,unsigned end,uint32_t *clipped);
// Stream converter:125 input to108 output;gain Q10,0..2048 (unity1024).
uint32_t revc_convert_stream(const uint32_t *input,uint32_t *output,uint32_t *peak,unsigned start_q10,unsigned end_q10,uint32_t *clipped);
typedef struct {uint32_t current,start,target,step;} revc_gain_ramp;
// Five short blocks keep the approximately11.25ms gain-control ramp.
bool revc_gain_step(revc_gain_ramp *r,unsigned target_eighths,unsigned *start_q10,unsigned *end_q10);
// Snapshot the first forbidden exponent0,including bounded neighboring words.
// Only called after conversion fails;never repairs or skips invalid audio.
typedef struct {uint32_t index,word,before,after;} revc_bad_frame;
bool revc_find_bad_frame(const uint32_t *raw,unsigned frames,revc_bad_frame *out);
typedef struct {uint32_t consumed;bool pending;} revc_tx_cursor;
// A completed DMA consumes once. -1=wait for production,-2=invalid queue,
// 0..7=published ring slot that may be armed for its NEXT turn.
int revc_tx_slot(revc_tx_cursor *cursor,uint32_t produced);
bool revc_parse_fm_gain(const char *command,unsigned *gain);
typedef enum { PLAYER_IDLE, PLAYER_RUNNING, PLAYER_DONE, PLAYER_STOPPED, PLAYER_FAULT } player_state;
typedef struct {
    const wym1_file *file; uint64_t origin_us; uint32_t index, max_late_us;
    uint32_t late_hist[5]; player_state state;
} revc_player;
// write():1=committed,0=BUSY retry,-1=hardware failure. Never skip/coalesce events.
typedef int (*revc_writer)(void *, uint8_t, uint8_t);
void revc_player_start(revc_player *p, const wym1_file *f, uint64_t origin_us);
void revc_player_stop(revc_player *p);
void revc_player_tick(revc_player *p, uint64_t now_us, revc_writer write, void *ctx);
uint32_t revc_i2s_div256(uint32_t system_hz,uint32_t elapsed_us);
typedef struct { uint64_t last_progress_us; uint16_t sof; bool valid; } revc_usb_guard;
bool revc_usb_alive(revc_usb_guard *g,uint64_t now_us,uint16_t sof,bool connected);
#endif
