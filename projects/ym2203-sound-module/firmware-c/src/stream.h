// SPDX-License-Identifier: MIT
#ifndef REVC_STREAM_H
#define REVC_STREAM_H
#include "wym1.h"
#define REVC_QUEUE_CAPACITY 1024u
#define REVC_PACKET_PAYLOAD 192u
#define REVC_PACKET_MAX (16u+REVC_PACKET_PAYLOAD)
#define REVC_STATUS_SIZE 64u
#define REVC_LEASE_US 1000000u
#define REVC_PREFILL 512u
enum { STREAM_IDLE,STREAM_PREFILL,STREAM_RUNNING,STREAM_DONE,STREAM_STOPPED,STREAM_FAULT };
enum { S_OK,S_CRC,S_SHAPE,S_SEQUENCE,S_STATE,S_FULL,S_DATA,S_IO,S_LEASE,S_UNDERRUN,S_LATE,S_INTEGRITY,S_AUDIO };
enum { S_PING,S_STOP,S_BEGIN,S_PUSH,S_PLAY,S_KEEP,S_SEAL };
enum { S_ACTION_NONE,S_ACTION_STOP };
typedef struct {uint32_t ms;uint8_t reg,value;} revc_event;
typedef struct {
    revc_event queue[REVC_QUEUE_CAPACITY];
    uint32_t read,write,received,executed,total,period,last_ms,crc,expected_crc;
    uint32_t next_seq,ack_seq,last_seq,last_length,max_late_us,late_hist[5],min_queue,generation;
    uint64_t origin_us,lease_us;
    uint8_t state,result,error,action;bool sealed,have_last;
    uint8_t last_packet[REVC_PACKET_MAX];
} revc_stream;
// Preparation returns S_OK,S_STATE (busy) or S_AUDIO (hardware not ready/fault).
typedef unsigned (*revc_prepare)(void *context);
void revc_stream_init(revc_stream *s);
bool revc_stream_owned(const revc_stream *s);
void revc_stream_stop(revc_stream *s);
void revc_stream_fail(revc_stream *s,unsigned error);
// Commands validated and executed on core0;never in the I2C ISR.
void revc_stream_command(revc_stream *s,const uint8_t *packet,unsigned length,uint64_t now,revc_prepare prepare,void *ctx);
void revc_stream_tick(revc_stream *s,uint64_t now,revc_writer writer,void *ctx);
void revc_stream_status(revc_stream *s,uint8_t out[REVC_STATUS_SIZE],uint64_t now,bool audio_ok);
#endif
