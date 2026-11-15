// SPDX-License-Identifier: MIT
#ifndef REVC_DIAGNOSTIC_H
#define REVC_DIAGNOSTIC_H
#include <stdbool.h>
#include <stdint.h>
#define REVC_DIAG_HEADER 96u
#define REVC_DIAG_TRACE_CAPACITY 16384u
#define REVC_DIAG_BLOCKS 178u
#define REVC_DIAG_FRAMES (625u*REVC_DIAG_BLOCKS)
#define REVC_DIAG_RAW_OFFSET (REVC_DIAG_HEADER+REVC_DIAG_TRACE_CAPACITY*6u)
#define REVC_DIAG_BYTES (REVC_DIAG_RAW_OFFSET+REVC_DIAG_FRAMES*3u)
// Reset only while audio core is paused;arm only in state0 (no writers).
// Other calls have one writer per
// buffer:core0 trace,core1 raw. Acquire/release publishes completed buffers.
void revc_diag_reset(void);
bool revc_diag_arm(uint64_t origin,unsigned start_second,unsigned gain,bool fast,uint32_t song_crc,uint32_t events);
unsigned revc_diag_state(void); //0=empty/aborted,1=recording,2=raw done,3=sealed
void revc_diag_abort(void);
void revc_diag_trace(uint64_t returned_at,uint8_t reg,uint8_t value);
void revc_diag_rx(const uint32_t *raw,uint64_t dma_done);
//125-frame live fragments are grouped into the unchanged625-frame RCD1 unit.
void revc_diag_rx_frames(const uint32_t *raw,unsigned frames,uint64_t dma_done);
bool revc_diag_seal(void);
const uint8_t *revc_diag_data(void); //NULL until sealed;fixed REVC_DIAG_BYTES
bool revc_parse_capture(const char *command,unsigned *second);
#endif
