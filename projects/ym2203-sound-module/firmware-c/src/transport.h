// SPDX-License-Identifier: MIT
#ifndef REVC_TRANSPORT_H
#define REVC_TRANSPORT_H
#include "stream.h"
#include <stdatomic.h>
typedef struct {
    uint8_t packets[4][REVC_PACKET_MAX],assembling[REVC_PACKET_MAX];
    unsigned lengths[4],length;bool oversized;
    atomic_uint head,tail,overflow;
    uint8_t status[2][REVC_STATUS_SIZE],read_status[REVC_STATUS_SIZE];
    atomic_uint current_status;unsigned read_pos;bool reading;
} revc_transport;
void revc_transport_init(revc_transport *t);
void revc_transport_byte(revc_transport *t,uint8_t value);
void revc_transport_finish(revc_transport *t);
int revc_transport_pop(revc_transport *t,uint8_t out[REVC_PACKET_MAX]);
void revc_transport_publish(revc_transport *t,const uint8_t status[REVC_STATUS_SIZE]);
uint8_t revc_transport_read(revc_transport *t);
void revc_i2c_init(void);
int revc_i2c_pop(uint8_t out[REVC_PACKET_MAX]);
void revc_i2c_publish(const uint8_t status[REVC_STATUS_SIZE]);
#endif
