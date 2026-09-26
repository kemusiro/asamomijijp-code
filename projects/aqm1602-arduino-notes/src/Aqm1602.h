// SPDX-License-Identifier: BSD-2-Clause
#pragma once

#include <Arduino.h>
#include <Print.h>
#include <Wire.h>

// AQM1602XA-RN-GBW (ST7032i), write-only I2C, no dynamic allocation.
class Aqm1602 : public Print {
 public:
  enum class Supply : uint8_t { V5, V3_3 };
  enum class Mode : uint8_t { TwoLines, OneLine, DoubleHeight };
  enum class Bias : uint8_t { OneFifth, OneFourth };
  enum class Direction : uint8_t { Left, Right };
  enum class Error : uint8_t { None, NotInitialized, InvalidArgument, WireBuffer, WireTransmission };

  struct Config {
    Supply supply = Supply::V5;
    uint8_t contrast = 35;  // 5 V starting value; explicitly tune for 3.3 V.
    Mode mode = Mode::TwoLines;
    Bias bias = Bias::OneFifth;
    uint8_t oscillator = 4;  // F2..F0, not a frequency in Hz.
    uint8_t followerRatio = 4;  // Rab2..Rab0, not a multiplier.
  };

  explicit Aqm1602(TwoWire &wire = Wire);
  Aqm1602(const Aqm1602 &) = delete;
  Aqm1602 &operator=(const Aqm1602 &) = delete;

  bool begin(bool beginWire = true);  // Default: 5 V, two lines.
  bool begin(const Config &config, bool beginWire = true);
  bool ready() const { return ready_; }
  Error lastError() const { return error_; }
  uint8_t lastWireStatus() const { return wireStatus_; }

  using Print::write;
  size_t write(uint8_t value) override;
  size_t write(const uint8_t *data, size_t size) override;
  bool clear();  // Preserves the entry mode selected through this API.
  bool home();   // Does not erase DDRAM; cancels display shift.
  bool setCursor(uint8_t column, uint8_t row);
  bool setDdramAddress(uint8_t address);  // Includes off-screen positions.
  bool setCgramAddress(uint8_t address);  // Following write() targets CGRAM.
  bool createChar(uint8_t slot, const uint8_t bitmap[8]);

  bool setDisplay(bool enabled);
  bool setCursorVisible(bool enabled);
  bool setBlink(bool enabled);
  bool setEntryMode(Direction direction, bool shiftDisplay = false);
  bool moveCursor(Direction direction);
  bool scrollDisplay(Direction direction);
  bool setMode(Mode mode);  // Homes cursor/display; does not clear DDRAM.
  bool setContrast(uint8_t contrast);
  bool setBiasAndOscillator(Bias bias, uint8_t oscillator);
  bool setFollower(bool enabled, uint8_t ratio);
  bool setBooster(bool enabled);  // Enabling requires Config::supply == V3_3.

 private:
  static constexpr uint8_t kAddress = 0x3E;
  TwoWire &wire_;
  Config config_;
  uint8_t display_ = 4;
  uint8_t entry_ = 2;
  bool booster_ = false;
  bool ready_ = false;
  Error error_ = Error::NotInitialized;
  uint8_t wireStatus_ = 0;

  bool startOperation();
  bool invalidArgument();
  bool transfer(uint8_t control, uint8_t value, unsigned int waitUs = 100);
  bool command(uint8_t value, unsigned int waitUs = 100);
  uint8_t function(Mode mode, bool extended) const;
  uint8_t power(uint8_t contrast, bool booster) const;
  bool extendedCommand(uint8_t value, bool settle = false);
  bool changeDisplay(uint8_t bit, bool enabled);
  bool shift(Direction direction, bool display);
};
