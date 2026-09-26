// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
struct Transmission {
  uint8_t address;
  std::vector<uint8_t> bytes;
};
class TwoWire {
 public:
  std::vector<Transmission> sent;
  size_t failAt = static_cast<size_t>(-1);
  size_t shortAt = static_cast<size_t>(-1);
  size_t shortByte = 1;
  uint8_t status = 2;
  int begins = 0;
  void begin() { ++begins; }
  void beginTransmission(uint8_t address) { current_ = {address, {}}; }
  size_t write(uint8_t value) {
    if (sent.size() == shortAt && current_.bytes.size() == shortByte) return 0;
    current_.bytes.push_back(value);
    return 1;
  }
  uint8_t endTransmission() {
    sent.push_back(current_);
    return sent.size() - 1 == failAt ? status : 0;
  }
 private:
  Transmission current_{};
};
extern TwoWire Wire;
