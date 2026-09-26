// SPDX-License-Identifier: BSD-2-Clause
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
// Test double for the Arduino Print API; not a copy of Arduino implementation.
class Print {
 public:
  virtual ~Print() = default;
  virtual size_t write(uint8_t) = 0;
  virtual size_t write(const uint8_t *data, size_t size) = 0;
  size_t write(const char *s) { return write(reinterpret_cast<const uint8_t *>(s), std::strlen(s)); }
  size_t print(const char *s) { return write(s); }
  int getWriteError() const { return error_; }
  void clearWriteError() { error_ = 0; }
 protected:
  void setWriteError(int error = 1) { error_ = error; }
 private:
  int error_ = 0;
};
