// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
extern std::vector<unsigned long> delays;
inline void delay(unsigned long ms) { delays.push_back(ms * 1000); }
inline void delayMicroseconds(unsigned int us) { delays.push_back(us); }
