// SPDX-License-Identifier: GPL-3.0-or-later
// Project-owned JT03/Verilator harness; upstream RTL is used without patches.
#include "Vrevc_jt03.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

static uint32_t le32(const uint8_t *p) {
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
struct Event { uint32_t ms; uint8_t reg, value; };
struct Score { std::vector<Event> events; uint32_t period, clock; };
static Score read_score(const char *path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("Cannot read WYM1");
    f.seekg(0, std::ios::end); auto size = f.tellg(); f.seekg(0);
    if (size < 16 || size > 16 + 6 * 131071) throw std::runtime_error("Invalid WYM1 length");
    std::vector<uint8_t> b(static_cast<size_t>(size));
    if (!f.read(reinterpret_cast<char*>(b.data()), size)) throw std::runtime_error("Short WYM1 read");
    if (!std::equal(b.begin(), b.begin() + 4, "WYM1")) throw std::runtime_error("Invalid WYM1 signature");
    uint32_t n = le32(b.data() + 4);
    Score s{{}, le32(b.data() + 8), le32(b.data() + 12)};
    if (!n || n > 131071 || b.size() != 16 + 6 * size_t(n) || !s.period || s.clock != 4000000)
        throw std::runtime_error("Unsupported WYM1 shape/clock");
    for (uint32_t i = 0; i < n; ++i) {
        const auto *p = b.data() + 16 + 6 * i;
        Event e{le32(p), p[4], p[5]};
        if (e.ms > s.period || (!s.events.empty() && e.ms < s.events.back().ms))
            throw std::runtime_error("Invalid event order/range");
        if (e.reg >= 0x2d && e.reg <= 0x2f) throw std::runtime_error("Prescaler changes require a separate clock validation");
        s.events.push_back(e);
    }
    return s;
}
class Simulation {
public:
    Vrevc_jt03 chip;
    uint64_t cycles = 0, frames = 0, sample_edges = 0, busy_cycles = 0;
    uint64_t last_sample_cycle = 0, sample_period_min = UINT64_MAX, sample_period_max = 0;
    uint64_t max_late = 0, executed = 0;
    int fm_peak = 0, psg_peak = 0;
    bool audible = false;
    uint64_t capture_end = 0;
    std::ofstream trace;
    std::vector<float> pcm;
    int64_t fm_sum = 0, psg_sum = 0;
    unsigned sub_sample = 0;
    bool previous_sample = false;
    Simulation(const char *trace_path): trace(trace_path, std::ios::binary) {
        if (!trace) throw std::runtime_error("Cannot create trace");
        chip.clk = 0; chip.cen = 1; chip.rst = 1;
        chip.addr = 0; chip.din = 0; chip.cs_n = 1; chip.wr_n = 1;

        pcm.reserve(16384);
        for (int i = 0; i < 4096; ++i) tick();
        chip.rst = 0;
        for (int i = 0; i < 32; ++i) tick();
        cycles = 0; previous_sample = chip.snd_sample;
    }
    void flush() {
        if (!pcm.empty() && fwrite(pcm.data(), sizeof(float), pcm.size(), stdout) != pcm.size())
            throw std::runtime_error("PCM pipe write failed");
        pcm.clear();
    }
    void tick() {
        chip.clk = 0; chip.eval();
        chip.clk = 1; chip.eval();
        if (audible && cycles < capture_end) {
            bool edge = chip.snd_sample && !previous_sample;
            if (edge) {
                if (sample_edges) {
                    uint64_t delta = cycles - last_sample_cycle;
                    sample_period_min = std::min(sample_period_min, delta);
                    sample_period_max = std::max(sample_period_max, delta);
                }
                last_sample_cycle = cycles; ++sample_edges;
            }
            previous_sample = chip.snd_sample;
            int fm = int16_t(chip.fm_snd);
            int psg = unsigned(chip.psg_A) + unsigned(chip.psg_B) + unsigned(chip.psg_C);
            fm_peak = std::max(fm_peak, std::abs(fm)); psg_peak = std::max(psg_peak, psg);
            fm_sum += fm; psg_sum += psg;
            // Integrate four 4 MHz cycles per output frame. FM and SSG stay separate.
            // This is 1 MHz PCM; a documented anti-alias filter later converts to 48 kHz.
            if (++sub_sample == 4) {
                pcm.push_back(float(fm_sum) / (4.0f * 32768.0f));
                pcm.push_back(float(psg_sum) / (4.0f * 255.0f));
                fm_sum = psg_sum = 0; sub_sample = 0; ++frames;
                if (pcm.size() >= 16384) flush();
            }
        }
        ++cycles;
    }
    void idle(unsigned n) { for (unsigned i = 0; i < n; ++i) tick(); }
    void pulse(uint8_t addr, uint8_t data) {
        chip.addr = addr; chip.din = data; chip.cs_n = 0; chip.wr_n = 0;
        idle(8);
        chip.cs_n = 1; chip.wr_n = 1; idle(8);
    }
    void write(const Event &e) {
        chip.addr = 0; idle(2); // status output is registered in JT03
        unsigned wait = 0;
        while (chip.dout & 0x80) {
            tick(); ++busy_cycles;
            if (++wait > 4096) throw std::runtime_error("BUSY timeout");
        }
        uint64_t planned = uint64_t(e.ms) * 4000, start = cycles;
        max_late = std::max(max_late, start - planned);
        for (unsigned i = 0; i < 8; ++i) trace.put(char(start >> (8 * i)));
        trace.put(char(e.reg)); trace.put(char(e.value));
        pulse(0, e.reg); pulse(1, e.value); ++executed;
    }
};
int main(int argc, char **argv) {
    try {
        if (argc != 5) throw std::runtime_error("Usage: simulator input.wym1 trace.bin stats.json limit_ms(0=full)");
        Verilated::commandArgs(argc, argv);
        Score score = read_score(argv[1]);
        uint64_t requested = std::stoull(argv[4]);
        uint64_t duration = requested ? std::min<uint64_t>(requested, score.period) : score.period;
        Simulation sim(argv[2]);
        sim.audible = true; sim.capture_end = duration * 4000;
        size_t i = 0; uint64_t next_progress = 30 * 4000000ull;
        while (sim.cycles < sim.capture_end) {
            if (i < score.events.size() && uint64_t(score.events[i].ms) * 4000 <= sim.cycles) {
                sim.write(score.events[i++]);
            } else sim.tick();
            if (sim.cycles >= next_progress) {
                std::cerr << "SIM " << sim.cycles / 4000000 << "s events=" << i << '/' << score.events.size() << '\n';
                next_progress += 30 * 4000000ull;
            }
        }
        // Events exactly at period_ms still execute in order; no extra PCM is appended.
        while (!requested && i < score.events.size()) sim.write(score.events[i++]);
        sim.flush(); sim.chip.final(); sim.trace.close();
        std::ofstream out(argv[3]);
        if (!out) throw std::runtime_error("Cannot create stats");
        out << "{\n  \"clock_hz\": 4000000,\n  \"pcm_rate_hz\": 1000000,\n"
            << "  \"duration_ms\": " << duration << ",\n  \"executed_events\": " << sim.executed
            << ",\n  \"source_events\": " << score.events.size()
            << ",\n  \"frames\": " << sim.frames
            << ",\n  \"max_address_start_late_cycles\": " << sim.max_late
            << ",\n  \"busy_wait_cycles\": " << sim.busy_cycles
            << ",\n  \"fm_sample_edges\": " << sim.sample_edges
            << ",\n  \"fm_sample_period_min_cycles\": " << (sim.sample_edges > 1 ? sim.sample_period_min : 0)
            << ",\n  \"fm_sample_period_max_cycles\": " << sim.sample_period_max
            << ",\n  \"fm_peak_native\": " << sim.fm_peak
            << ",\n  \"psg_sum_peak_native\": " << sim.psg_peak << "\n}\n";
        if (!out || sim.frames != duration * 1000) throw std::runtime_error("Output frame/report mismatch");
        std::cerr << "SIM DONE events=" << sim.executed << " frames=" << sim.frames << '\n';
        return 0;
    } catch (const std::exception &e) { std::cerr << "FAIL: " << e.what() << '\n'; return 1; }
}
