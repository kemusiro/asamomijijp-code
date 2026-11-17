// SPDX-License-Identifier: MIT
// Pad guard only; stub core is intentionally adversarial; full core tested separately.
#include "Vrevc_ulx3s_top.h"
#include <cassert>
#include <cstdio>
int main(){
 Vrevc_ulx3s_top m;
 m.ref12=0;m.audio49=0;m.reset_button=0;m.stop_button=0;m.config_button=0;m.profile_switch=0;m.permit=1;m.vbus_sense=1;
 auto tick=[&](){m.ref12=0;m.eval();m.ref12=1;m.eval();};
 for(int i=0;i<4;i++)tick();
 assert(m.arm_request&&m.dac_allow&&m.line_allow&&m.ym_reset_n&&!m.translator_oe_n);
 assert(m.ym_data==0xa5&&m.usb_dp_tx==1&&m.usb_dn_tx==0);
 // VBUS loss detaches USB, but must leave I2C owner's audio requests alone.
 m.vbus_sense=0;m.eval();assert(m.arm_request&&m.dac_allow&&m.line_allow);
 m.vbus_sense=1;m.stop_button=1;
 for(int i=0;i<4;i++)tick();assert(m.ym_cs_n);
 m.stop_button=0;for(int i=0;i<4;i++)tick();assert(!m.ym_cs_n);
 // Hardware permit is an immediate inhibit, without waiting for a clock edge.
 m.permit=0;m.eval();
 assert(!m.arm_request&&!m.dac_allow&&!m.line_allow&&!m.ym_reset_n&&m.translator_oe_n);
 assert(m.ym_cs_n&&m.ym_rd_n&&m.ym_wr_n&&!m.translator_dir);
 m.permit=1;m.reset_button=1;m.eval();
 assert(!m.arm_request&&!m.dac_allow&&!m.line_allow&&!m.ym_reset_n&&m.translator_oe_n);
 m.reset_button=0;for(int i=0;i<24000;i++)tick();assert(m.heartbeat);
 for(int i=0;i<24000;i++)tick();assert(!m.heartbeat);
 assert(!m.esp_en);
 puts("PASS adapter: asynchronous inhibit, VBUS/I2C scope, synchronized STOP and 1kHz heartbeat (ideal clock/core stubs)");
}
