/* SPDX-License-Identifier: MIT
 * Static pin mux compilation only. No firmware initialization and no GPIO access.
 * Compile against the locked Pico SDK2.2.0 RP2350 io_bank0.h.
 */
#define _u(x) x##u
#include <stdint.h>
#include "hardware/regs/io_bank0.h"
#include "p2_pinmap.h"
#define SEL0(pin, fn) IO_BANK0_GPIO##pin##_CTRL_FUNCSEL_VALUE_##fn
#define SEL(pin, fn) SEL0(pin, fn)
#define CHECK(pin, fn, select) _Static_assert(SEL(pin, fn) == select, #fn)
CHECK(P2_GPIO_EXT_D0, UART0_RX, 2);
CHECK(P2_GPIO_EXT_D1, UART0_TX, 2);
CHECK(P2_GPIO_EXT_D10, SPI1_SS_N, 1);
CHECK(P2_GPIO_EXT_D11, SPI1_TX, 1);
CHECK(P2_GPIO_EXT_D12, SPI1_RX, 1);
CHECK(P2_GPIO_EXT_D13, SPI1_SCLK, 1);
CHECK(P2_GPIO_HOST_SDA, I2C0_SDA, 3);
CHECK(P2_GPIO_HOST_SCL, I2C0_SCL, 3);
CHECK(P2_GPIO_EXT_A4, I2C1_SDA, 3);
CHECK(P2_GPIO_EXT_A5, I2C1_SCL, 3);
CHECK(P2_GPIO_EXT_D3, PWM_A_7, 4);
CHECK(P2_GPIO_EXT_D5, PWM_B_7, 4);
CHECK(P2_GPIO_EXT_D6, PWM_A_3, 4);
CHECK(P2_GPIO_EXT_D9, PWM_B_3, 4);
CHECK(P2_GPIO_EXT_D10, PWM_B_4, 4);
CHECK(P2_GPIO_EXT_D11, PWM_B_5, 4);
_Static_assert(P2_GPIO_EXT_A0 == 40 && P2_GPIO_EXT_A1 == 41 &&
               P2_GPIO_EXT_A2 == 44 && P2_GPIO_EXT_A3 == 45,
               "QFN80 ADC channels0,1,4,5");
_Static_assert(P2_GPIO_M_I2S_LRCK == P2_GPIO_M_I2S_BCK + 1, "two contiguous side-set pins");
_Static_assert(P2_GPIO_M_I2S_LRCK < 32 && P2_GPIO_M_FM_SH < 32, "PIO BASE0");
_Static_assert(P2_GPIO_M_YM_WR_N >= 32 && (UINT64_C(1) << P2_GPIO_M_YM_WR_N) != 0,
               "high-bank GPIO need64bit masks");
