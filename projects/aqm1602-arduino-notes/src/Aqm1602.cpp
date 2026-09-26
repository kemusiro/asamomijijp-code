// SPDX-License-Identifier: BSD-2-Clause
#include "Aqm1602.h"

namespace {
bool validMode(Aqm1602::Mode mode) {
  return mode == Aqm1602::Mode::TwoLines || mode == Aqm1602::Mode::OneLine ||
         mode == Aqm1602::Mode::DoubleHeight;
}
bool validBias(Aqm1602::Bias bias) {
  return bias == Aqm1602::Bias::OneFifth || bias == Aqm1602::Bias::OneFourth;
}
bool validDirection(Aqm1602::Direction direction) {
  return direction == Aqm1602::Direction::Left || direction == Aqm1602::Direction::Right;
}
}  // namespace

Aqm1602::Aqm1602(TwoWire &wire) : wire_(wire) {}

bool Aqm1602::invalidArgument() {
  error_ = Error::InvalidArgument;
  setWriteError();
  return false;
}

bool Aqm1602::startOperation() {
  if (!ready_) {
    // Keep the original transport failure for diagnosis until begin().
    setWriteError();
    return false;
  }
  error_ = Error::None;
  wireStatus_ = 0;
  return true;
}

bool Aqm1602::transfer(uint8_t control, uint8_t value, unsigned int waitUs) {
  wire_.beginTransmission(kAddress);
  const size_t controlCount = wire_.write(control);
  const size_t dataCount = controlCount == 1 ? wire_.write(value) : 0;
  // Close even an incomplete transaction; its effect is treated as unknown.
  wireStatus_ = wire_.endTransmission();
  delayMicroseconds(waitUs);
  if (controlCount != 1 || dataCount != 1 || wireStatus_ != 0) {
    error_ = (controlCount != 1 || dataCount != 1) ? Error::WireBuffer : Error::WireTransmission;
    ready_ = false;
    setWriteError();
    return false;
  }
  return true;
}

bool Aqm1602::command(uint8_t value, unsigned int waitUs) {
  return transfer(0x00, value, waitUs);
}

uint8_t Aqm1602::function(Mode mode, bool extended) const {
  const uint8_t format = mode == Mode::TwoLines ? 0x08 : (mode == Mode::DoubleHeight ? 0x04 : 0);
  return static_cast<uint8_t>(0x30 | format | (extended ? 1 : 0));
}

uint8_t Aqm1602::power(uint8_t contrast, bool booster) const {
  // ION is always zero: AQM1602XA has no icon segments.
  return static_cast<uint8_t>(0x50 | (booster ? 0x04 : 0) | (contrast >> 4));
}

bool Aqm1602::begin(bool beginWire) { return begin(Config{}, beginWire); }

bool Aqm1602::begin(const Config &config, bool beginWire) {
  ready_ = false;
  error_ = Error::None;
  wireStatus_ = 0;
  clearWriteError();
  if ((config.supply != Supply::V5 && config.supply != Supply::V3_3) ||
      config.contrast > 63 || !validMode(config.mode) || !validBias(config.bias) ||
      config.oscillator > 7 || config.followerRatio > 7) {
    return invalidArgument();
  }
  config_ = config;
  display_ = 4;
  entry_ = 2;
  booster_ = config.supply == Supply::V3_3;
  if (beginWire) wire_.begin();
  delay(100);
  if (!command(function(config.mode, false)) ||
      !command(function(config.mode, true)) ||
      !command(static_cast<uint8_t>(0x10 | (config.bias == Bias::OneFourth ? 8 : 0) | config.oscillator)) ||
      !command(static_cast<uint8_t>(0x70 | (config.contrast & 0x0F))) ||
      !command(power(config.contrast, booster_)) ||
      !command(static_cast<uint8_t>(0x68 | config.followerRatio))) return false;
  delay(201);  // Datasheet: more than 200 ms after follower setup.
  if (!command(function(config.mode, false)) || !command(0x08) ||
      !command(0x01, 3000) || !command(0x06) || !command(0x0C)) return false;
  ready_ = true;
  return true;
}

size_t Aqm1602::write(uint8_t value) {
  return startOperation() && transfer(0x40, value) ? 1 : 0;
}

size_t Aqm1602::write(const uint8_t *data, size_t size) {
  if (!startOperation()) return 0;
  if (size != 0 && data == nullptr) {
    invalidArgument();
    return 0;
  }
  size_t written = 0;
  while (written < size && transfer(0x40, data[written])) ++written;
  return written;
}

bool Aqm1602::clear() {
  if (!startOperation() || !command(0x01, 3000)) return false;
  // Clear sets I/D=1 in hardware; restore the user's entry mode explicitly.
  return command(static_cast<uint8_t>(0x04 | entry_));
}

bool Aqm1602::home() { return startOperation() && command(0x02, 3000); }

bool Aqm1602::setCursor(uint8_t column, uint8_t row) {
  if (!startOperation()) return false;
  const uint8_t rows = config_.mode == Mode::TwoLines ? 2 : 1;
  if (column >= 16 || row >= rows) return invalidArgument();
  return command(static_cast<uint8_t>(0x80 | (row == 0 ? 0 : 0x40) | column));
}

bool Aqm1602::setDdramAddress(uint8_t address) {
  if (!startOperation()) return false;
  bool valid = false;
  switch (config_.mode) {
    case Mode::TwoLines: valid = address <= 0x27 || (address >= 0x40 && address <= 0x67); break;
    case Mode::OneLine: valid = address <= 0x4F; break;
    case Mode::DoubleHeight: valid = address <= 0x27; break;
  }
  if (!valid) return invalidArgument();
  return command(static_cast<uint8_t>(0x80 | address));
}

bool Aqm1602::setCgramAddress(uint8_t address) {
  if (!startOperation()) return false;
  if (address > 63) return invalidArgument();
  return command(static_cast<uint8_t>(0x40 | address));
}

bool Aqm1602::createChar(uint8_t slot, const uint8_t bitmap[8]) {
  if (!startOperation()) return false;
  if (slot > 7 || bitmap == nullptr || config_.mode == Mode::DoubleHeight) return invalidArgument();
  for (uint8_t i = 0; i < 8; ++i) {
    if (bitmap[i] > 31) return invalidArgument();
  }
  // CGRAM writes also obey I/D: temporarily force increment without shifting.
  if (!command(0x06) || !command(static_cast<uint8_t>(0x40 | (slot << 3)))) return false;
  for (uint8_t i = 0; i < 8; ++i) {
    if (!transfer(0x40, bitmap[i])) return false;
  }
  // Return to DDRAM at 0, not an unobservable guessed previous address.
  return command(0x80) && command(static_cast<uint8_t>(0x04 | entry_));
}

bool Aqm1602::changeDisplay(uint8_t bit, bool enabled) {
  if (!startOperation()) return false;
  const uint8_t next = enabled ? (display_ | bit) : (display_ & static_cast<uint8_t>(~bit));
  if (!command(static_cast<uint8_t>(0x08 | next))) return false;
  display_ = next;
  return true;
}
bool Aqm1602::setDisplay(bool enabled) { return changeDisplay(4, enabled); }
bool Aqm1602::setCursorVisible(bool enabled) { return changeDisplay(2, enabled); }
bool Aqm1602::setBlink(bool enabled) { return changeDisplay(1, enabled); }

bool Aqm1602::setEntryMode(Direction direction, bool shiftDisplay) {
  if (!startOperation()) return false;
  if (!validDirection(direction)) return invalidArgument();
  const uint8_t next = (direction == Direction::Right ? 2 : 0) | (shiftDisplay ? 1 : 0);
  if (!command(static_cast<uint8_t>(0x04 | next))) return false;
  entry_ = next;
  return true;
}

bool Aqm1602::shift(Direction direction, bool display) {
  if (!startOperation()) return false;
  if (!validDirection(direction)) return invalidArgument();
  return command(static_cast<uint8_t>(0x10 | (display ? 8 : 0) | (direction == Direction::Right ? 4 : 0)));
}
bool Aqm1602::moveCursor(Direction direction) { return shift(direction, false); }
bool Aqm1602::scrollDisplay(Direction direction) { return shift(direction, true); }

bool Aqm1602::setMode(Mode mode) {
  if (!startOperation()) return false;
  if (!validMode(mode)) return invalidArgument();
  if (!command(function(mode, false)) || !command(0x02, 3000)) return false;
  config_.mode = mode;
  return true;
}

bool Aqm1602::extendedCommand(uint8_t value, bool settle) {
  if (!command(function(config_.mode, true)) || !command(value)) return false;
  if (settle) delay(201);
  return command(function(config_.mode, false));
}

bool Aqm1602::setContrast(uint8_t contrast) {
  if (!startOperation()) return false;
  if (contrast > 63) return invalidArgument();
  if (!command(function(config_.mode, true)) ||
      !command(static_cast<uint8_t>(0x70 | (contrast & 0x0F))) ||
      !command(power(contrast, booster_)) ||
      !command(function(config_.mode, false))) return false;
  config_.contrast = contrast;
  return true;
}

bool Aqm1602::setBiasAndOscillator(Bias bias, uint8_t oscillator) {
  if (!startOperation()) return false;
  if (!validBias(bias) || oscillator > 7) return invalidArgument();
  if (!extendedCommand(static_cast<uint8_t>(0x10 | (bias == Bias::OneFourth ? 8 : 0) | oscillator))) return false;
  config_.bias = bias;
  config_.oscillator = oscillator;
  return true;
}

bool Aqm1602::setFollower(bool enabled, uint8_t ratio) {
  if (!startOperation()) return false;
  if (ratio > 7) return invalidArgument();
  if (!extendedCommand(static_cast<uint8_t>(0x60 | (enabled ? 8 : 0) | ratio), enabled)) return false;
  config_.followerRatio = ratio;
  return true;
}

bool Aqm1602::setBooster(bool enabled) {
  if (!startOperation()) return false;
  if (enabled && config_.supply != Supply::V3_3) return invalidArgument();
  if (!extendedCommand(power(config_.contrast, enabled), enabled)) return false;
  booster_ = enabled;
  return true;
}
