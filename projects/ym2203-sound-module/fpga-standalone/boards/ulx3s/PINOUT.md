# ULX3S 85F v3.0.8 F1端子表

正本は`pins.json`。J1/J2番号は縦型オスヘッダ。直角メスでは偶数・奇数を交換する。
全信号3.3V。YM側5Vはレベル変換後の信号。実機／キャリア回路図は未検証。

| 信号 | FPGA ball | 接続位置 | 方向 | bank | 初期pull | 用途 |
| --- | --- | --- | --- | ---: | --- | --- |
| `ref12` | P3 | OLED1.3 OLED_CLK (no display installed) | input | 6 | NONE | clock |
| `audio49` | A10 | J1.7 GP1 | input | 0 | NONE | clock |
| `permit` | C11 | J1.6 GN0 | input | 0 | DOWN | safety |
| `reset_button` | R1 | BTN0 | input | 8 | DOWN | safety |
| `stop_button` | T1 | BTN1 | input | 8 | DOWN | safety |
| `config_button` | R18 | BTN2 | input | 3 | DOWN | config |
| `profile_switch[0]` | E8 | SW1 | input | 0 | DOWN | config |
| `profile_switch[1]` | D8 | SW2 | input | 0 | DOWN | config |
| `profile_switch[2]` | D7 | SW3 | input | 0 | DOWN | config |
| `usb_dp_rx` | E16 | US2 D+ input tap | input | 2 | NONE | usb |
| `usb_dn_rx` | F16 | US2 D- input tap | input | 2 | NONE | usb |
| `usb_dp_tx` | D15 | US2 D+ via R53 | output | 1 | NONE | usb |
| `usb_dn_tx` | E15 | US2 D- via R52 | output | 1 | NONE | usb |
| `usb_dp_bias` | B12 | US2 D+ bias via D24/R40 | output | 1 | NONE | usb |
| `usb_dn_bias` | C12 | US2 D- bias (always high-Z) | output | 1 | NONE | usb |
| `ym_a0` | A6 | J1.23 GP7 | output | 0 | DOWN | ym |
| `ym_cs_n` | B6 | J1.24 GN7 | output | 0 | UP | ym |
| `ym_wr_n` | A4 | J1.25 GP8 | output | 7 | UP | ym |
| `ym_rd_n` | A5 | J1.26 GN8 | output | 7 | UP | ym |
| `ym_reset_n` | A2 | J1.27 GP9 | output | 7 | DOWN | safety |
| `translator_dir` | B1 | J1.28 GN9 | output | 7 | DOWN | ym |
| `translator_oe_n` | C4 | J1.29 GP10 | output | 7 | UP | safety |
| `arm_request` | B4 | J1.30 GN10 | output | 7 | DOWN | safety |
| `fm_sd` | U18 | J2.3 GP14 | input | 3 | DOWN | fm |
| `fm_clk` | U17 | J2.4 GN14 | input | 3 | DOWN | fm |
| `fm_sh` | N17 | J2.5 GP15 | input | 3 | DOWN | fm |
| `i2s_bclk` | P16 | J2.6 GN15 | output | 3 | NONE | i2s |
| `i2s_lrck` | N16 | J2.7 GP16 | output | 3 | NONE | i2s |
| `i2s_data` | M17 | J2.8 GN16 | output | 3 | NONE | i2s |
| `host_scl` | L16 | J2.9 GP17 | inout | 3 | NONE | i2c |
| `host_sda` | L17 | J2.10 GN17 | inout | 3 | NONE | i2c |
| `si_scl` | H18 | J2.11 GP18 | inout | 2 | NONE | si |
| `si_sda` | H17 | J2.12 GN18 | inout | 2 | NONE | si |
| `dac_allow` | F17 | J2.13 GP19 | output | 2 | DOWN | safety |
| `line_allow` | G18 | J2.14 GN19 | output | 2 | DOWN | safety |
| `vbus_sense` | D18 | J2.15 GP20 | input | 2 | DOWN | usb |
| `heartbeat` | E17 | J2.16 GN20 | output | 2 | DOWN | safety |
| `esp_en` | F1 | ESP32 EN (held low) | output | 6 | DOWN | reserved |
| `led[0]` | B2 | LED0 PLL lock | output | 7 | NONE | status |
| `led[1]` | C2 | LED1 audio OK | output | 7 | NONE | status |
| `led[2]` | C1 | LED2 audio fault | output | 7 | NONE | status |
| `ym_data[0]` | B9 | J1.11 GP3 | inout | 0 | NONE | ym |
| `ym_data[1]` | C10 | J1.12 GN3 | inout | 0 | NONE | ym |
| `ym_data[2]` | A7 | J1.13 GP4 | inout | 0 | NONE | ym |
| `ym_data[3]` | A8 | J1.14 GN4 | inout | 0 | NONE | ym |
| `ym_data[4]` | C8 | J1.15 GP5 | inout | 0 | NONE | ym |
| `ym_data[5]` | B8 | J1.16 GN5 | inout | 0 | NONE | ym |
| `ym_data[6]` | C6 | J1.17 GP6 | inout | 0 | NONE | ym |
| `ym_data[7]` | C7 | J1.18 GN6 | inout | 0 | NONE | ym |

内部pullは設定後の補助。設定前のARM／RESET／OE／DAC／LINEは外付け抵抗・監視回路で安全側にする。
USB US2のVBUS分離、OLED未装着、bank電圧、外付け発振器・許可回路は../../BOARD.mdを参照。
GP0, GN1, GP/GN2, GP/GN21..27等の未使用信号を5Vに接続しない。GP/GN11..13はESP32共用として予約。
