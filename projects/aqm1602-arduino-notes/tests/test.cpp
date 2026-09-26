// SPDX-License-Identifier: BSD-2-Clause
#include "Aqm1602.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>
#include <vector>

TwoWire Wire;
std::vector<unsigned long> delays;
using D = Aqm1602::Direction;
using M = Aqm1602::Mode;
using E = Aqm1602::Error;

// Independent minimal device model: decodes traffic into RAM and display state.
struct LcdModel {
  bool extended = false, cgramSelected = false;
  uint8_t ac = 0, entry = 2, display = 0, contrast = 0;
  uint8_t format = 8;
  std::array<uint8_t, 128> ddram{};
  std::array<uint8_t, 64> cgram{};
  void consume(const std::vector<Transmission> &sent) {
    for (const auto &t : sent) {
      assert(t.address == 0x3E && t.bytes.size() == 2);
      const uint8_t v = t.bytes[1];
      if (t.bytes[0] == 0x40) {
        if (cgramSelected) cgram[ac & 63] = v;
        else ddram[ac & 127] = v;
        ac = static_cast<uint8_t>(ac + ((entry & 2) ? 1 : -1));
      } else {
        assert(t.bytes[0] == 0);
        if ((v & 0xE0) == 0x20) { extended = v & 1; format = v & 0x0C; }
        else if (v & 0x80) { ac = v & 0x7F; cgramSelected = false; }
        else if (v == 1) { ddram.fill(0x20); ac = 0; cgramSelected = false; entry |= 2; }
        else if (v == 2) { ac = 0; cgramSelected = false; }
        else if ((v & 0xFC) == 4) entry = v & 3;
        else if ((v & 0xF8) == 8) display = v & 7;
        else if (!extended && (v & 0xC0) == 0x40) { ac = v & 63; cgramSelected = true; }
        else if (extended && (v & 0xF0) == 0x70) contrast = (contrast & 0x30) | (v & 15);
        else if (extended && (v & 0xF0) == 0x50) contrast = (contrast & 15) | ((v & 3) << 4);
      }
    }
  }
};

void expectCommands(const TwoWire &bus, const std::vector<uint8_t> &commands) {
  assert(bus.sent.size() == commands.size());
  for (size_t i = 0; i < commands.size(); ++i) {
    assert(bus.sent[i].address == 0x3E);
    assert((bus.sent[i].bytes == std::vector<uint8_t>{0, commands[i]}));
  }
}

void initialization() {
  for (auto supply : {Aqm1602::Supply::V5, Aqm1602::Supply::V3_3}) {
    TwoWire bus;
    Aqm1602 lcd(bus);
    assert(!lcd.home() && lcd.lastError() == E::NotInitialized && bus.sent.empty());
    Aqm1602::Config c;
    c.supply = supply;
    delays.clear();
    assert(lcd.begin(c, false) && lcd.ready());
    assert(bus.begins == 0 && lcd.getWriteError() == 0);
    expectCommands(bus, {0x38,0x39,0x14,0x73,static_cast<uint8_t>(supply == Aqm1602::Supply::V5 ? 0x52 : 0x56),0x6C,0x38,0x08,0x01,0x06,0x0C});
    assert(delays.front() == 100000);
    assert(std::count(delays.begin(), delays.end(), 201000) == 1);
    assert(std::count(delays.begin(), delays.end(), 3000) == 1);
    assert(std::all_of(delays.begin(), delays.end(), [](unsigned long d) { return d >= 100; }));
    LcdModel model;
    model.consume(bus.sent);
    assert(!model.extended && model.display == 4 && model.contrast == 35 && model.entry == 2);
  }
  TwoWire bus;
  Aqm1602 lcd(bus);
  assert(lcd.begin() && bus.begins == 1);
}

void ramAndEntry() {
  TwoWire bus;
  Aqm1602 lcd(bus);
  assert(lcd.begin());
  assert(lcd.setCursor(0, 1));
  assert(lcd.print("ABC") == 3);
  assert(lcd.setEntryMode(D::Left, true));
  const uint8_t glyph[8] = {0, 4, 14, 31, 14, 4, 0, 0};
  assert(lcd.createChar(7, glyph));
  assert(lcd.setCursor(3, 1));
  assert(lcd.write(static_cast<uint8_t>(7)) == 1);
  LcdModel model;
  model.consume(bus.sent);
  assert(std::equal(glyph, glyph + 8, model.cgram.begin() + 56));
  assert(model.ddram[0x40] == 'A' && model.ddram[0x42] == 'C');
  assert(model.ddram[0x43] == 7 && model.entry == 1 && !model.cgramSelected);
  bus.sent.clear();
  delays.clear();
  assert(lcd.clear());
  expectCommands(bus, {1,5});
  assert(delays[0] == 3000);
  assert(lcd.home() && delays[2] == 3000);
  bus.sent.clear();
  assert(lcd.setCgramAddress(63));
  assert(lcd.write(static_cast<uint8_t>(31)) == 1);
  assert(lcd.setDdramAddress(0x67));
  assert(lcd.write("Z") == 1);
  assert((bus.sent[1].bytes == std::vector<uint8_t>{0x40,31}));
  assert((bus.sent[3].bytes == std::vector<uint8_t>{0x40,'Z'}));
}

void controls() {
  TwoWire bus;
  Aqm1602 lcd(bus);
  assert(lcd.begin());
  bus.sent.clear();
  assert(lcd.setCursorVisible(true) && lcd.setBlink(true));
  assert(lcd.setDisplay(false) && lcd.setDisplay(true));
  assert(lcd.setCursorVisible(false) && lcd.setBlink(false));
  assert(lcd.moveCursor(D::Left) && lcd.moveCursor(D::Right));
  assert(lcd.scrollDisplay(D::Left) && lcd.scrollDisplay(D::Right));
  expectCommands(bus, {0x0E,0x0F,0x0B,0x0F,0x0D,0x0C,0x10,0x14,0x18,0x1C});
  bus.sent.clear();
  assert(lcd.setContrast(0) && lcd.setContrast(63));
  assert(lcd.setBiasAndOscillator(Aqm1602::Bias::OneFourth, 0));
  assert(lcd.setFollower(false,7) && lcd.setFollower(true,4));
  expectCommands(bus, {0x39,0x70,0x50,0x38,0x39,0x7F,0x53,0x38,0x39,0x18,0x38,0x39,0x67,0x38,0x39,0x6C,0x38});
  assert(!lcd.setBooster(true));
  Aqm1602::Config c;
  c.supply = Aqm1602::Supply::V3_3;
  c.contrast = 16;
  assert(lcd.begin(c));
  bus.sent.clear();
  assert(lcd.setBooster(false) && lcd.setContrast(63) && lcd.setBooster(true));
  expectCommands(bus, {0x39,0x51,0x38,0x39,0x7F,0x53,0x38,0x39,0x57,0x38});
}

void modesAndValidation() {
  TwoWire bus;
  Aqm1602 lcd(bus);
  assert(lcd.begin());
  bus.sent.clear();
  const uint8_t glyph[8] = {};
  const uint8_t badGlyph[8] = {0,0,0,32,0,0,0,0};
  assert(!lcd.setCursor(16,0) && !lcd.setCursor(0,2));
  assert(!lcd.setDdramAddress(0x28) && !lcd.setDdramAddress(0x68));
  assert(!lcd.setCgramAddress(64) && !lcd.setContrast(64));
  assert(!lcd.createChar(8,glyph) && !lcd.createChar(0,nullptr));
  assert(!lcd.createChar(0,badGlyph));
  assert(!lcd.setFollower(true,8) && !lcd.setBiasAndOscillator(Aqm1602::Bias::OneFifth,8));
  assert(!lcd.setMode(static_cast<M>(99)) && !lcd.moveCursor(static_cast<D>(99)));
  assert(!lcd.setEntryMode(static_cast<D>(99)) && !lcd.scrollDisplay(static_cast<D>(99)));
  assert(!lcd.setBiasAndOscillator(static_cast<Aqm1602::Bias>(99),0));
  assert(lcd.write(nullptr,1) == 0 && lcd.lastError() == E::InvalidArgument);
  assert(bus.sent.empty() && lcd.ready());
  assert(lcd.write(nullptr,0) == 0 && lcd.lastError() == E::None);
  assert(lcd.getWriteError() != 0);  // Print error is sticky until explicitly cleared.
  lcd.clearWriteError();
  assert(lcd.getWriteError() == 0);
  assert(lcd.setMode(M::OneLine));
  assert(lcd.setDdramAddress(0x4F) && !lcd.setDdramAddress(0x50));
  assert(!lcd.setCursor(0,1));
  assert(lcd.setMode(M::DoubleHeight));
  assert(lcd.setDdramAddress(0x27) && !lcd.setDdramAddress(0x28));
  assert(!lcd.createChar(0,glyph));
  bus.sent.clear();
  assert(lcd.setContrast(35));
  expectCommands(bus, {0x35,0x73,0x52,0x34});
  assert(lcd.setMode(M::TwoLines) && lcd.setCursor(15,1));
  Aqm1602::Config c;
  c.contrast = 64;
  bus.sent.clear();
  assert(!lcd.begin(c) && !lcd.ready() && bus.sent.empty());
  c.contrast = 35;
  c.supply = static_cast<Aqm1602::Supply>(99);
  assert(!lcd.begin(c) && bus.sent.empty());
  c.supply = Aqm1602::Supply::V5;
  c.oscillator = 8;
  assert(!lcd.begin(c) && bus.sent.empty());
  c.oscillator = 4;
  c.followerRatio = 8;
  assert(!lcd.begin(c) && bus.sent.empty());
  c.followerRatio = 4;
  c.mode = static_cast<M>(99);
  assert(!lcd.begin(c) && bus.sent.empty());
  c.mode = M::TwoLines;
  c.bias = static_cast<Aqm1602::Bias>(99);
  assert(!lcd.begin(c) && bus.sent.empty());
}

void rangesAndLongWrites() {
  for (auto mode : {M::TwoLines, M::OneLine, M::DoubleHeight}) {
    for (uint8_t oscillator = 0; oscillator < 8; ++oscillator) {
      TwoWire bus;
      Aqm1602 lcd(bus);
      Aqm1602::Config c;
      c.mode = mode;
      c.oscillator = oscillator;
      c.followerRatio = oscillator;
      c.bias = Aqm1602::Bias::OneFourth;
      assert(lcd.begin(c));
      LcdModel model;
      model.consume(bus.sent);
      assert(model.format == (mode == M::TwoLines ? 8 : (mode == M::OneLine ? 0 : 4)));
      assert(!model.extended);
    }
  }
  TwoWire bus;
  Aqm1602 lcd(bus);
  assert(lcd.begin());
  for (uint8_t contrast = 0; contrast < 64; ++contrast) {
    bus.sent.clear();
    assert(lcd.setContrast(contrast));
    LcdModel model;
    model.consume(bus.sent);
    assert(model.contrast == contrast && !model.extended);
  }
  std::array<uint8_t, 100> data{};
  for (size_t i = 0; i < data.size(); ++i) data[i] = static_cast<uint8_t>(i);
  bus.sent.clear();
  assert(lcd.write(data.data(), data.size()) == data.size());
  assert(bus.sent.size() == data.size());
  for (size_t i = 0; i < data.size(); ++i) {
    assert((bus.sent[i].bytes == std::vector<uint8_t>{0x40,data[i]}));
  }
  for (uint8_t status : {1,2,3,4,5,6,255}) {
    TwoWire failedBus;
    Aqm1602 failed(failedBus);
    failedBus.failAt = 0;
    failedBus.status = status;
    assert(!failed.begin() && failed.lastWireStatus() == status);
  }
}

void faults() {
  // Every initialization boundary may fail: no later commands may be issued.
  for (size_t i = 0; i < 11; ++i) {
    TwoWire bus;
    Aqm1602 lcd(bus);
    bus.failAt = i;
    assert(!lcd.begin() && !lcd.ready() && bus.sent.size() == i + 1);
    assert(lcd.lastError() == E::WireTransmission && lcd.lastWireStatus() == 2);
    assert(!lcd.setDisplay(true) && lcd.write("XYZ") == 0 && bus.sent.size() == i + 1);
    assert(lcd.lastError() == E::WireTransmission);
    bus.failAt = static_cast<size_t>(-1);
    assert(lcd.begin() && lcd.ready() && lcd.getWriteError() == 0);
  }
  // Exercise every transfer in multi-command operations including IS restore.
  for (int op = 0; op < 4; ++op) {
    const size_t length = op == 0 ? 4 : (op == 1 ? 12 : 3);
    for (size_t i = 0; i < length; ++i) {
      TwoWire bus;
      Aqm1602 lcd(bus);
      assert(lcd.begin());
      bus.sent.clear();
      bus.failAt = i;
      bus.status = 5;
      const uint8_t glyph[8] = {};
      const bool ok = op == 0 ? lcd.setContrast(20) : (op == 1 ? lcd.createChar(0,glyph) :
                      (op == 2 ? lcd.setFollower(true,4) : lcd.setBiasAndOscillator(Aqm1602::Bias::OneFifth,4)));
      assert(!ok && !lcd.ready() && bus.sent.size() == i + 1 && lcd.lastWireStatus() == 5);
      assert(lcd.write(static_cast<uint8_t>('X')) == 0 && bus.sent.size() == i + 1);
    }
  }
  for (size_t byte : {0U, 1U}) {
    TwoWire bus;
    Aqm1602 lcd(bus);
    assert(lcd.begin());
    bus.sent.clear();
    bus.shortAt = 0;
    bus.shortByte = byte;
    assert(lcd.write("X") == 0 && !lcd.ready());
    assert(lcd.lastError() == E::WireBuffer && bus.sent.size() == 1);
  }
  for (size_t i = 0; i < 3; ++i) {
    TwoWire bus;
    Aqm1602 lcd(bus);
    assert(lcd.begin());
    bus.sent.clear();
    bus.failAt = i;
    assert(lcd.write("ABC") == i && !lcd.ready() && bus.sent.size() == i + 1);
  }
}

int main() {
  initialization(); ramAndEntry(); controls(); modesAndValidation(); rangesAndLongWrites(); faults();
  std::cout << "PASS: initialization, RAM model, controls, validation, timing, fault injection\n";
}
