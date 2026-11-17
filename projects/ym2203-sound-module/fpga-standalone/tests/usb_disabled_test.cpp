// SPDX-License-Identifier: MIT
#include "Vrevc_usb_composite.h"
#include "verilated.h"
#include <iostream>
int main(){Vrevc_usb_composite d;d.permit=d.usb_vbus=1;d.dp_in=1;d.reset=1;
 for(unsigned n=0;n<1000;++n){d.clk=0;d.eval();d.clk=1;d.eval();if(n==10)d.reset=0;
 if(d.pullup_enable||d.tx_enable||d.configured){std::cerr<<"FAIL USB attached without allocated IDs\n";return 1;}}
 std::cout<<"PASS USB default-zero ID guard: detached, no drive, no configuration\n";}
