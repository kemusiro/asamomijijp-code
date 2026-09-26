// SPDX-License-Identifier: BSD-2-Clause
// Arduino-Pico core: rp2040:rp2040:rpipico2w, LCD powered at 3.3 V.
#include <Aqm1602.h>

Aqm1602 lcd;

void require(bool ok) {
  if (ok) return;
  Serial.print("LCD error: ");
  Serial.print(static_cast<unsigned int>(lcd.lastError()));
  Serial.print(" Wire status: ");
  Serial.println(lcd.lastWireStatus());
  while (true) delay(1000);
}

void setup() {
  Serial.begin(115200);
  // Call pin selection before Wire.begin(). GP numbers, not physical pin numbers.
  require(Wire.setSDA(16));
  require(Wire.setSCL(17));
  Wire.begin();
  Wire.setClock(100000);
  Aqm1602::Config config;
  config.supply = Aqm1602::Supply::V3_3;
  config.contrast = 35;
  require(lcd.begin(config, false));
  require(lcd.print("AQM1602 / Pico2W") == 16);
  require(lcd.setCursor(0, 1));
  require(lcd.print("Arduino 3.3 V") == 13);
}

using Direction = Aqm1602::Direction;
const uint8_t diamond[8] = {0, 4, 14, 31, 14, 4, 0, 0};
void loop() {
  if (!Serial.available()) return;
  const int command = Serial.read();
  if (command == 's') {
    Serial.println(lcd.ready() ? "READY: Arduino Pico2W basic display" : "ERROR: not ready");
    return;
  }
  if (command != 'g') return;
  Serial.println("START: features in 5 seconds");
  delay(5000);
  require(lcd.clear());
  require(lcd.createChar(0, diamond));
  require(lcd.write(static_cast<uint8_t>(0)) == 1);
  require(lcd.print(" Custom glyph") == 13);
  require(lcd.setCursor(0, 1));
  require(lcd.print("Cursor / blink") == 14);
  require(lcd.setCursorVisible(true));
  require(lcd.setBlink(true));
  Serial.println("glyph / cursor / blink");
  delay(4000);
  require(lcd.moveCursor(Direction::Left)); delay(1000);
  require(lcd.moveCursor(Direction::Right)); delay(1000);
  Serial.println("scroll left / right");
  for (uint8_t i=0;i<4;++i) { require(lcd.scrollDisplay(Direction::Left)); delay(600); }
  for (uint8_t i=0;i<4;++i) { require(lcd.scrollDisplay(Direction::Right)); delay(600); }
  require(lcd.home());
  Serial.println("display OFF / ON");
  require(lcd.setDisplay(false)); delay(2000);
  require(lcd.setDisplay(true)); delay(2000);
  require(lcd.setCursorVisible(false));
  require(lcd.setBlink(false));
  require(lcd.clear());
  require(lcd.setEntryMode(Direction::Left));
  require(lcd.setCursor(15, 1));
  require(lcd.print("ABC") == 3);
  require(lcd.setEntryMode(Direction::Right));
  Serial.println("CBA at lower right"); delay(4000);
  require(lcd.setCursor(0, 0)); require(lcd.print("100") == 3); delay(3000);
  require(lcd.setCursor(0, 0)); require(lcd.print(" 99") == 3);
  Serial.println("100 -> space99"); delay(3000);
  require(lcd.clear());
  require(lcd.print("AQM1602 / Pico2W") == 16);
  require(lcd.setCursor(0, 1)); require(lcd.print("Arduino done") == 12);
  require(lcd.setCursor(15, 1)); require(lcd.write(static_cast<uint8_t>(0)) == 1);
  Serial.println("PASS: all feature writes; visual confirmation required");
}
