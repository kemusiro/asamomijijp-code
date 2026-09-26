// SPDX-License-Identifier: BSD-2-Clause
#include <Aqm1602.h>

Aqm1602 lcd;
using Direction = Aqm1602::Direction;
const uint8_t diamond[8] = {0, 4, 14, 31, 14, 4, 0, 0};

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
  // Configure the LCD supply, not the CPU's nominal voltage.
  Aqm1602::Config config;
  require(lcd.begin(config));
  require(lcd.createChar(0, diamond));
  require(lcd.setCursor(0, 0));
  require(lcd.write(static_cast<uint8_t>(0)) == 1);  // Code 0 is not a C string.
  require(lcd.print(" Custom glyph") == 13);
  require(lcd.setCursor(0, 1));
  require(lcd.print("Cursor / blink") == 14);
  require(lcd.setCursorVisible(true));
  require(lcd.setBlink(true));
  delay(2000);
  require(lcd.moveCursor(Direction::Left));
  delay(500);
  require(lcd.moveCursor(Direction::Right));
  for (uint8_t i = 0; i < 4; ++i) {
    require(lcd.scrollDisplay(Direction::Left));
    delay(250);
  }
  for (uint8_t i = 0; i < 4; ++i) {
    require(lcd.scrollDisplay(Direction::Right));
    delay(250);
  }
  require(lcd.home());
  require(lcd.setDisplay(false));
  delay(500);
  require(lcd.setDisplay(true));
  require(lcd.setCursorVisible(false));
  require(lcd.setBlink(false));
  require(lcd.setContrast(30));
  delay(1000);
  require(lcd.setContrast(config.contrast));
  require(lcd.clear());
  require(lcd.setEntryMode(Direction::Left));
  require(lcd.setCursor(15, 0));
  require(lcd.print("ABC") == 3);  // Appears as CBA at columns 13..15.
  require(lcd.setEntryMode(Direction::Right, true));
  require(lcd.setCursor(15, 1));
  require(lcd.print("123") == 3);
  require(lcd.setEntryMode(Direction::Right));
  require(lcd.home());
  // Analog settings and one-line/double-height modes are advanced APIs.
  // See README before changing them; physical display results are unverified.
}

void loop() {}
