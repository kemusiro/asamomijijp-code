# GPIOと編集パネルの静的照合

現在のG/H割当のGPIO番号を維持する候補。コネクタの物理位置と端子番号は新規。実装・新基板の通信受入ではない。

| 基板 | GPIO | 機能・net | Picossci端子 |
| --- | ---: | --- | --- |
| base | 0 | BUS_D0 / pio0_data_or_SPI0_if_bit0to3 | J1.4 |
| base | 1 | BUS_D1 / pio0_data_or_SPI0_if_bit0to3 | J1.5 |
| base | 2 | BUS_D2 / pio0_data_or_SPI0_if_bit0to3 | J1.6 |
| base | 3 | BUS_D3 / pio0_data_or_SPI0_if_bit0to3 | J1.7 |
| base | 4 | BUS_D4 / pio0_data_or_SPI0_if_bit0to3 | J1.8 |
| base | 5 | BUS_D5 / pio0_data_or_SPI0_if_bit0to3 | J1.9 |
| base | 6 | BUS_D6 / pio0_data_or_SPI0_if_bit0to3 | J1.10 |
| base | 7 | BUS_D7 / pio0_data_or_SPI0_if_bit0to3 | J1.11 |
| base | 8 | MOD_CTL0 / pio0_control_or_SIO | J1.12 |
| base | 9 | MOD_CTL1 / pio0_control_or_SIO | J1.13 |
| base | 10 | MOD_CTL2 / pio0_control_or_SIO | J1.14 |
| base | 11 | MOD_CTL3 / pio0_control_or_SIO | J1.15 |
| base | 12 | MOD_ENABLE / sio_output_default_low | J1.16 |
| base | 13 | MOD_ALERT_N / sio_input_open_drain | J1.17 |
| base | 14 | DAC_I2S_DATA / pio1_tx_data | J1.18 |
| base | 15 | AUDIO_BCK / pio1_clock | J1.19 |
| base | 16 | AUDIO_LRCK / pio1_clock | J1.20 |
| base | 17 | BASE_ADC_DOUT / pio1_rx_data | JP6.1 |
| base | 18 | MOD_I2S_DATA / pio1_rx_data | JP6.2 |
| base | 19 | EXT_D2 / sio | JP6.3 |
| base | 20 | HOST_SDA / i2c0_sda | JP6.4 |
| base | 21 | HOST_SCL / i2c0_scl | JP6.5 |
| base | 22 | EXT_D3 / sio | JP6.6 |
| base | 23 | EXT_D4 / sio | JP6.7 |
| base | 24 | EXT_D12 / spi1_rx | JP7.2 |
| base | 25 | EXT_D10 / spi1_ss_n | JP7.3 |
| base | 26 | EXT_D13 / spi1_sclk | JP7.4 |
| base | 27 | EXT_D11 / spi1_tx | JP7.5 |
| base | 28 | EXT_D1 / uart0_tx | JP7.6 |
| base | 29 | EXT_D0 / uart0_rx | JP7.7 |
| base | 30 | EXT_D5 / sio | JP7.8 |
| base | 31 | EXT_D6 / sio | J2.1 |
| base | 32 | EXT_D7 / sio | J2.2 |
| base | 33 | EXT_D8 / sio | J2.3 |
| base | 34 | EXT_D9 / sio | J2.4 |
| base | 38 | M_DAC_ALLOW / sio_output_default_low | J2.8 |
| base | 39 | M_LINE_ALLOW / sio_output_default_low | J2.9 |
| base | 40 | EXT_A0 / adc_or_sio | J2.11 |
| base | 41 | EXT_A1 / adc_or_sio | J2.12 |
| base | 42 | EXT_A4 / i2c1_sda | J2.13 |
| base | 43 | EXT_A5 / i2c1_scl | J2.14 |
| base | 44 | EXT_A2 / adc_or_sio | J2.15 |
| base | 45 | EXT_A3 / adc_or_sio | J2.16 |
| base | 46 | M_VBUS_SENSE / sio_input_with_voltage_divider | J2.17 |
| sound | 0 | YM_D0 / sio_data | J1.4 |
| sound | 1 | YM_D1 / sio_data | J1.5 |
| sound | 2 | YM_D2 / sio_data | J1.6 |
| sound | 3 | YM_D3 / sio_data | J1.7 |
| sound | 4 | YM_D4 / sio_data | J1.8 |
| sound | 5 | YM_D5 / sio_data | J1.9 |
| sound | 6 | YM_D6 / sio_data | J1.10 |
| sound | 7 | YM_D7 / sio_data | J1.11 |
| sound | 8 | MOD_SPI_MOSI / spi1_rx | J1.12 |
| sound | 9 | MOD_SPI_CS_N / spi1_ss_n | J1.13 |
| sound | 10 | MOD_SPI_SCK / spi1_sclk | J1.14 |
| sound | 11 | MOD_SPI_MISO / spi1_tx | J1.15 |
| sound | 12 | YM_A0 / sio_control | J1.16 |
| sound | 13 | YM_CS_N / sio_control | J1.17 |
| sound | 14 | YM_WR_N / sio_control | J1.18 |
| sound | 15 | YM_RD_N / sio_control | J1.19 |
| sound | 16 | YM_FM_SD / pio0_input | J1.20 |
| sound | 17 | YM_FM_CLK / pio0_input | JP6.1 |
| sound | 18 | YM_FM_SH / pio0_input | JP6.2 |
| sound | 19 | YM_DATA_DIR / sio_output | JP6.3 |
| sound | 20 | YM_DATA_OE_N / sio_output | JP6.4 |
| sound | 21 | YM_CTRL_OE_N / sio_output | JP6.5 |
| sound | 22 | YM_RESET_RELEASE / sio_output | JP6.6 |
| sound | 23 | MOD_ALERT_DRIVE / sio_output | JP6.7 |
| sound | 24 | MOD_I2S_DATA / pio1_output | JP7.2 |
| sound | 25 | MOD_I2S_BCK / pio1_input | JP7.3 |
| sound | 26 | MOD_I2S_LRCK / pio1_input | JP7.4 |
| sound | 27 | LINK_TX_DISABLE / sio_output | JP7.5 |

GP24/25は両モジュールのLED抵抗R5/R6を外して負荷を切り離す候補。baseではLCD DC/CS、soundではI2S DATA/BCK。GPIOを別番号へ移す案ではない。
外部RUNは端面にない。SW1 RESETの非GND端子から追加配線し、基板側コネクタを設ける。sourceは既存MOD_ENABLE→open-drain→RUNの経路を省略しない。baseも外部ハードリセットへ接続。実物導通と部品版の確認が必要。

## PANEL40（G40とは接続不可）

| pin | 信号 | base GPIO |
| ---: | --- | ---: |
| 1 | GND | — |
| 2 | AUX_3V3 | — |
| 3 | LCD_SCK | 26 |
| 4 | GND | — |
| 5 | LCD_MOSI | 27 |
| 6 | GND | — |
| 7 | LCD_CS_N | 25 |
| 8 | LCD_DC | 24 |
| 9 | LCD_RST_N | 28 |
| 10 | GND | — |
| 11 | SDA | 42 |
| 12 | SCL | 43 |
| 13 | KNOB1_ADC | 40 |
| 14 | GND | — |
| 15 | KNOB2_ADC | 41 |
| 16 | GND | — |
| 17 | KNOB3_ADC | 44 |
| 18 | GND | — |
| 19 | KNOB4_ADC | 45 |
| 20 | GND | — |
| 21 | STOP_N | 29 |
| 22 | ENC_A | 19 |
| 23 | ENC_B | 22 |
| 24 | ENC_SW_N | 23 |
| 25 | OP1_N | 30 |
| 26 | OP2_N | 31 |
| 27 | OP3_N | 32 |
| 28 | OP4_N | 33 |
| 29 | NOTE_N | 34 |
| 30 | GND | — |
| 31 | IOREF_3V3 | — |
| 32 | GND | — |
| 33 | GND | — |
| 34 | GND | — |
| 35 | GND | — |
| 36 | GND | — |
| 37 | GND | — |
| 38 | GND | — |
| 39 | GND | — |
| 40 | GND | — |

3.3V信号のみ、AUX_3V3とIOREF_3V3は別線・別レール。2MHz以下のLCD SPIを分割DMA、100kHzのservice I2CはEEPROM書込待ちをノンブロッキングにする。152mmリボンのSPI/ADCノイズは実機で確認する。
G40の論理40接点・KEY6・3.3Vバス・アナログL/R・任意I2Sは既存Hのまま。新コネクタ位置・支持高さなので、旧基板との物理嵌合は保証しない。通電中の着脱は対象外。
