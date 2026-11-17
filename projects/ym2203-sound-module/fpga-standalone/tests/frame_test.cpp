// SPDX-License-Identifier: MIT
#include "Vrevc_v2_frame.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

static void require(bool ok, const char *message) {
    if (!ok) throw std::runtime_error(message);
}
static void tick(Vrevc_v2_frame &d) {
    d.clk = 0; d.eval(); d.clk = 1; d.eval(); d.clk = 0; d.eval();
}
static uint32_t read32(std::ifstream &f) {
    uint32_t value = 0;
    for (unsigned i = 0; i < 4; ++i) {
        int ch = f.get(); require(ch != EOF, "truncated test vector");
        value |= uint32_t(ch) << (8 * i);
    }
    return value;
}
int main(int argc, char **argv) {
    try {
        require(argc == 2, "expected vector path");
        std::ifstream f(argv[1], std::ios::binary);
        require(bool(f), "open test vectors");
        const unsigned cases = read32(f);
        Vrevc_v2_frame d;
        d.reset = 1; tick(d); d.reset = 0; tick(d);
        for (unsigned c = 0; c < cases; ++c) {
            const unsigned size = read32(f), expected = read32(f), mode = read32(f);
            std::vector<uint8_t> p(size);
            f.read(reinterpret_cast<char *>(p.data()), size);
            require(unsigned(f.gcount()) == size, "truncated packet");
            require(d.rx_ready, "must be ready before frame");
            d.rx_start = 1; tick(d); d.rx_start = 0;
            require(!d.frame_valid, "premature publication at start");
            for (unsigned i = 0; i < size; ++i) {
                if ((i + c) % 5 == 0) {
                    d.rx_valid = 0; tick(d); // variable wire pacing
                }
                d.rx_valid = 1; d.rx_data = p[i];
                d.rx_end = mode == 1 && i + 1 == size;
                tick(d);
                require(!d.frame_valid, "published before end/check");
            }
            d.rx_valid = 0;
            if (mode != 1 || !size) {
                d.rx_end = mode != 2;
                d.rx_abort = mode == 2;
                tick(d);
            }
            d.rx_end = 0; d.rx_abort = 0; tick(d);
            require(d.frame_valid && !d.rx_ready, "missing held result");
            if (unsigned(d.frame_result) != expected) {
                std::cerr << "case " << c << " length=" << size << " got="
                          << unsigned(d.frame_result) << " expected=" << expected << '\n';
                throw std::runtime_error("result mismatch");
            }
            require(d.frame_length == (size > 209 ? 209 : size), "length mismatch");
            if (!expected) {
                require(d.opcode == p[3], "opcode mismatch");
                uint32_t seq = 0;
                for (unsigned i = 0; i < 4; ++i) seq |= uint32_t(p[4 + i]) << (8 * i);
                require(d.frame_sequence == seq, "frame_sequence mismatch");
                require(d.payload_length == size - 16, "payload length mismatch");
            }
            for (unsigned i = 0; i < size && i < 208; ++i) {
                d.read_address = i; d.eval(); require(d.read_data == p[i], "packet RAM mismatch");
            }
            d.read_address = 250; d.eval(); require(d.read_data == 255, "RAM bounds");
            // No request may replace an unconsumed result.
            d.rx_start = 1; d.rx_valid = 1; d.rx_data = 0;
            for (unsigned i = 0; i < 3; ++i) {
                tick(d); require(d.frame_valid && d.frame_result == expected, "unstable held result");
            }
            d.rx_start = 0; d.rx_valid = 0;
            d.frame_take = 1; tick(d); d.frame_take = 0;
        }
        // Reset during a partial frame must discard it, with no publication.
        d.rx_start = 1; tick(d); d.rx_start = 0;
        d.rx_valid = 1; d.rx_data = 0x59; tick(d);
        d.reset = 1; tick(d); d.rx_valid = 0; d.reset = 0; tick(d);
        require(d.rx_ready && !d.frame_valid, "partial frame survived reset");
        std::cout << "PASS " << cases << " framing vectors; hold/readback/reset checks\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << "FAIL " << e.what() << '\n'; return 1;
    }
}
