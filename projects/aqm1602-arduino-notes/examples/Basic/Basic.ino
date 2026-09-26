// SPDX-License-Identifier: BSD-2-Clause
#include <Aqm1602.h>

Aqm1602 lcd;

void stopOnError() {
  Serial.print("LCD error: ");
  Serial.print(static_cast<unsigned int>(lcd.lastError()));
  Serial.print(" Wire status: ");
  Serial.println(lcd.lastWireStatus());
  while (true) delay(1000);
}

void setup() {
  Serial.begin(115200);
  Aqm1602::Config config;  // 5 V LCD supply and compatible I2C signal levels.
  // For a 3.3 V LCD supply, set BOTH supply and a contrast value to tune:
  // config.supply = Aqm1602::Supply::V3_3;
  // config.contrast = 35;  // Starting point only; not hardware-verified.
  if (!lcd.begin(config)) stopOnError();
  if (lcd.print("AQM1602") != 7) stopOnError();
  if (!lcd.setCursor(0, 1)) stopOnError();
  lcd.print(23.5, 1);
  lcd.print(" C");
  if (lcd.getWriteError()) stopOnError();
}

void loop() {}
