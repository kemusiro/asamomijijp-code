// SPDX-License-Identifier: MIT
#ifndef REVC_MIDI_H
#define REVC_MIDI_H
#include "wym1.h"
#define REVC_MIDI_OFF 255u
#define REVC_MIDI_SETUP_WRITES 88u
#define REVC_MIDI_PRIME_US 6750u
#define REVC_MIDI_RELEASE_US 135000u
enum { MIDI_IDLE,MIDI_SETUP,MIDI_PRIME,MIDI_READY,MIDI_FAULT };
enum { MIDI_NONE,MIDI_START,MIDI_PANIC };
typedef struct {
    uint8_t notes[6],applied_notes[6];
    uint32_t revision[6],done_revision[6];
    uint8_t state,setup,cursor,voice,note,step,reg,value;
    uint32_t job_revision,received,applied,rejected,invalid,ignored,panics;
    uint64_t ready_at,release_at,io_since;
    bool owned,gate,inflight,job,releasing;
} revc_midi;
void revc_midi_init(revc_midi *m);
// Cancel only with hardware outputs muted and any latched bus address cleared.
// Statistics survive cancellation; no messages are retained for replay.
void revc_midi_cancel(revc_midi *m);
// USB-MIDI 1.0 cable0 packets only. blocked prevents taking another source's
// ownership; malformed packets/panic never stop an unrelated I2C score.
unsigned revc_midi_message(revc_midi *m,const uint8_t packet[4],bool blocked);
// At most one nonblocking YM write per tick. An in-flight register is immutable
// across BUSY retries even if newer MIDI requests replace the desired note.
void revc_midi_tick(revc_midi *m,uint64_t now,revc_writer writer,void *ctx);
unsigned revc_midi_mask(const revc_midi *m);
bool revc_midi_pitch(unsigned voice,unsigned note,uint8_t *first,uint8_t *second);
#endif
