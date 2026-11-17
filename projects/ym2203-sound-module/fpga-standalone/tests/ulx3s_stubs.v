// SPDX-License-Identifier: MIT
// Adapter-only digital model: not a PLL or peripheral implementation.
module OBZ(input wire I,T,output wire O);
 assign O=T?1'bz:I;
endmodule
module revc_ulx3s_clocking(input wire ref12,reset,output wire clk,locked);
 assign clk=ref12;
 assign locked=!reset;
endmodule
module revc_usb_ym_top #(parameter [15:0] USB_VID=0,USB_PID=0,parameter [63:0] USB_SERIAL=0)(
 input wire clk,audio_clk,reset,permit,si_scl_in,si_sda_in,
 output wire si_scl_low,si_sda_low,
 input wire config_valid,input wire [3:0] config_profile,output wire clock_good,
 input wire scl_in,sda_in,output wire scl_low,sda_low,
 input wire other_owned,global_stop,usb_vbus,usb_dp_in,usb_dn_in,
 output wire usb_dp_out,usb_dn_out,usb_tx_enable,usb_pullup_enable,midi_owned,
 input wire [7:0] ym_data_in,output wire [7:0] ym_data_out,
 output wire ym_data_oe,translator_dir,translator_oe_n,
 output wire ym_a0,ym_cs_n,ym_wr_n,ym_rd_n,ym_reset_n,arm_request,dac_allow,line_allow,
 input wire fm_sd,fm_clk,fm_sh,output wire i2s_bclk,i2s_lrck,i2s_data,audio_ok,audio_fault);
 // Deliberately drive active requests even with permit/reset low: pad guard must win.
 assign {si_scl_low,si_sda_low,scl_low,sda_low}=4'b1111;
 assign {usb_dp_out,usb_dn_out,usb_tx_enable,usb_pullup_enable}=4'b1011;
 assign {ym_data_out,ym_data_oe}=9'h14b; // A5, enable=1
 assign {translator_dir,translator_oe_n,ym_a0}=3'b101;
 assign ym_cs_n=global_stop;
 assign {ym_wr_n,ym_rd_n,ym_reset_n,arm_request,dac_allow,line_allow}=6'b001111;
 assign {midi_owned,audio_ok,audio_fault,clock_good}=4'b0101;
 assign {i2s_bclk,i2s_lrck,i2s_data}=3'b000;
endmodule
