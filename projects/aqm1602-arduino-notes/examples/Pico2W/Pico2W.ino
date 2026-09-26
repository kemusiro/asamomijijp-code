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

void loop() {}
