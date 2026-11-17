// SPDX-License-Identifier: MIT
// Native simulation boundary. No hardware firmware includes these model clocks.
#include "Vrevc_v2_core.h"
#include "verilated.h"
#include <cstdint>
#include <memory>
#include <vector>

static std::unique_ptr<Vrevc_v2_core> d;
static uint64_t now_us, busy_until;
static unsigned service_us, prepares, silences;
static bool prior_prepare, prior_silence;
static std::vector<uint8_t> trace;

static void tick() {
    d->now_us = now_us;
    d->event_ready = now_us >= busy_until;
    d->clk = 0; d->eval();
    if (!d->reset && d->event_valid && d->event_ready) {
        trace.push_back(d->event_register); trace.push_back(d->event_value);
        busy_until = now_us + service_us;
    }
    if (d->prepare_request && !prior_prepare) ++prepares;
    if (d->silence_request && !prior_silence) ++silences;
    prior_prepare = d->prepare_request; prior_silence = d->silence_request;
    d->clk = 1; d->eval(); d->clk = 0; d->eval();
}

extern "C" {
void rtl_destroy() { d.reset(); }
void rtl_init(unsigned cost) {
    d = std::make_unique<Vrevc_v2_core>();
    now_us = busy_until = 0; service_us = cost;
    prepares = silences = 0; prior_prepare = prior_silence = false; trace.clear();
    d->audio_ok = 1; d->prepare_done = 1; d->silence_done = 1;
    d->reset = 1; tick(); d->reset = 0; tick();
}
uint64_t rtl_now() { return now_us; }
void rtl_clock(uint64_t value) { now_us = value; }
void rtl_cycles(unsigned n) { for (unsigned i = 0; i < n; ++i) tick(); }
void rtl_advance(uint64_t delta) {
    const uint64_t until = now_us + delta;
    while (now_us < until) {
        now_us += until - now_us > 20 ? 20 : until - now_us;
        for (unsigned i = 0; i < 4; ++i) tick();
    }
}
int rtl_send(const uint8_t *p, unsigned n) {
    if (!d->rx_ready) return -1;
    d->rx_start = 1; tick(); d->rx_start = 0;
    for (unsigned i = 0; i < n; ++i) {
        d->rx_valid = 1; d->rx_data = p[i]; tick();
    }
    d->rx_valid = 0; d->rx_end = 1; tick(); d->rx_end = 0;
    return 0;
}
int rtl_finish() {
    for (unsigned i = 0; i < 5000; ++i) {
        tick(); if (d->rx_ready) { tick(); return 0; }
    }
    return -1;
}
int rtl_command(const uint8_t *p, unsigned n) {
    if (rtl_send(p,n)) return -1;
    return rtl_finish();
}
int rtl_status(uint8_t *out) {
    d->status_request = 1;
    unsigned i;
    for (i = 0; i < 5000; ++i) { tick(); if (d->status_busy) break; }
    d->status_request = 0;
    if (i == 5000) return -1;
    for (i = 0; i < 5000; ++i) { tick(); if (d->status_valid && !d->status_busy) break; }
    if (i == 5000) return -1;
    for (i = 0; i < 64; ++i) { d->status_address = i; d->eval(); out[i] = d->status_data; }
    return 0;
}
unsigned rtl_status_byte(unsigned address) { d->status_address = address; d->eval(); return d->status_data; }
unsigned rtl_trace_count() { return unsigned(trace.size()/2); }
const uint8_t *rtl_trace() { return trace.data(); }
unsigned rtl_gate() { d->eval(); return d->gate_request; }
unsigned rtl_queued() { return d->queued; }
unsigned rtl_prepare_count() { return prepares; }
unsigned rtl_silence_count() { return silences; }
void rtl_controls(unsigned audio, unsigned other, unsigned writer_error,
                  unsigned prep_done, unsigned prep_result, unsigned silence_done) {
    d->audio_ok = audio; d->other_owned = other; d->event_error = writer_error;
    d->prepare_done = prep_done; d->prepare_result = prep_result; d->silence_done = silence_done;
    d->eval();
}
void rtl_transport_error() { d->transport_error = 1; tick(); d->transport_error = 0; tick(); }
void rtl_global_stop() { d->global_stop = 1; tick(); d->global_stop = 0; tick(); }
void rtl_abort() { d->rx_start = 1; tick(); d->rx_start = 0; d->rx_abort = 1; tick(); d->rx_abort = 0; }
}
