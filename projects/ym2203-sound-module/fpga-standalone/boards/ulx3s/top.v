// SPDX-License-Identifier: MIT
// Physical ULX3S 85F v3.0.8 carrier adapter; see BOARD.md and pins.json.
// No software CPU. External 5V translators, supervisor and mute gates required.
module revc_ulx3s_top #(
 parameter [15:0] USB_VID=0,USB_PID=0,
 parameter [63:0] USB_SERIAL=0
)(
 input wire ref12,audio49,reset_button,stop_button,permit,config_button,
 input wire [2:0] profile_switch,
 input wire vbus_sense,
 inout wire host_scl,host_sda,si_scl,si_sda,
 input wire usb_dp_rx,usb_dn_rx,
 output wire usb_dp_tx,usb_dn_tx,usb_dp_bias,usb_dn_bias,
 inout wire [7:0] ym_data,
 output wire translator_dir,translator_oe_n,
 output wire ym_a0,ym_cs_n,ym_wr_n,ym_rd_n,ym_reset_n,
 output wire arm_request,dac_allow,line_allow,
 input wire fm_sd,fm_clk,fm_sh,
 output wire i2s_bclk,i2s_lrck,i2s_data,
 output wire heartbeat,esp_en,
 output wire [2:0] led
);
 wire clk,locked;
 revc_ulx3s_clocking clocks(.ref12(ref12),.reset(reset_button),.clk(clk),.locked(locked));
 wire reset=reset_button||!locked;
 wire pad_reset;
 revc_domain_reset pad_domain(.clk(clk),.async_reset(reset||!permit),.reset(pad_reset));
 wire safe=permit&&!reset&&!pad_reset;
 // Assert asynchronously even if a clock stops; core reset release is two-flop.
 wire hscl_low,hsda_low,sscl_low,ssda_low;
 assign host_scl=(safe&&hscl_low)?1'b0:1'bz;
 assign host_sda=(safe&&hsda_low)?1'b0:1'bz;
 assign si_scl=(!reset&&sscl_low)?1'b0:1'bz;
 assign si_sda=(!reset&&ssda_low)?1'b0:1'bz;
 wire dp,dn,tx_en,pullup_req;
 assign usb_dp_tx=(safe&&vbus_sense&&tx_en)?dp:1'bz;
 assign usb_dn_tx=(safe&&vbus_sense&&tx_en)?dn:1'bz;
 // ULX3S diode/resistor network: LOW would select a 15k pulldown, not detach.
 assign usb_dp_bias=(safe&&vbus_sense&&pullup_req)?1'b1:1'bz;
 // A constant-Z assignment can be folded to 0 by synth_ecp5 setundef.
 // Preserve the physical output-disable explicitly through IO technology mapping.
 OBZ dn_bias_disabled(.I(1'b0),.T(1'b1),.O(usb_dn_bias));
 wire [7:0] data_out;
 wire data_oe,dir,oe_n,a0,cs_n,wr_n,rd_n,reset_n,arm,dac,line;
 assign ym_data=(safe&&data_oe)?data_out:8'bz;
 assign translator_dir=safe&&dir;
 assign translator_oe_n=!safe||oe_n;
 assign ym_a0=safe&&a0;
 assign ym_cs_n=!safe||cs_n;
 assign ym_wr_n=!safe||wr_n;
 assign ym_rd_n=!safe||rd_n;
 assign ym_reset_n=safe&&reset_n;
 assign arm_request=safe&&arm;
 assign dac_allow=safe&&dac;
 assign line_allow=safe&&line;
 // ESP32 is not part of the runtime; keep it disabled, reserve shared GPIOs.
 assign esp_en=1'b0;
 wire audio_ok,audio_fault,clock_good,midi_owned;
 assign led={audio_fault,audio_ok,locked};
 // External missing-pulse supervisor watches control clock, independent of permit.
 // It must also AND requests with power-good/configuration-safe physical defaults.
 reg [14:0] hb_count=0;
 reg hb=0;
 always @(posedge clk or posedge reset) begin
  if(reset) begin hb_count<=0;hb<=0;end
  else if(hb_count==23999) begin hb_count<=0;hb<=!hb;end
  else hb_count<=hb_count+1'b1;
 end
 assign heartbeat=locked&&!reset_button&&hb;
 (* async_reg="true",keep=1 *) reg stop_meta=0,stop_sync=0;
 (* async_reg="true",keep=1 *) reg config_meta=0,config_sync=0;
 (* async_reg="true",keep=1 *) reg [2:0] profile_meta=0,profile_sync=0;
 reg config_previous=0;
 always @(posedge clk) begin
  if(reset) begin
   stop_meta<=0;stop_sync<=0;config_meta<=0;config_sync<=0;config_previous<=0;
   profile_meta<=0;profile_sync<=0;
  end else begin
   stop_meta<=stop_button;stop_sync<=stop_meta;
   config_meta<=config_button;config_sync<=config_meta;config_previous<=config_sync;
   profile_meta<=profile_switch;profile_sync<=profile_meta;
  end
 end
 revc_usb_ym_top #(.USB_VID(USB_VID),.USB_PID(USB_PID),.USB_SERIAL(USB_SERIAL)) core (
  .clk(clk),.audio_clk(audio49),.reset(reset),.permit(permit&&!reset),
  .si_scl_in(si_scl),.si_sda_in(si_sda),.si_scl_low(sscl_low),.si_sda_low(ssda_low),
  .config_valid(config_sync&&!config_previous),.config_profile({1'b0,profile_sync}),.clock_good(clock_good),
  .scl_in(host_scl),.sda_in(host_sda),.scl_low(hscl_low),.sda_low(hsda_low),
  .other_owned(1'b0),.global_stop(stop_sync),
  .usb_vbus(vbus_sense),.usb_dp_in(usb_dp_rx),.usb_dn_in(usb_dn_rx),
  .usb_dp_out(dp),.usb_dn_out(dn),.usb_tx_enable(tx_en),.usb_pullup_enable(pullup_req),
  .midi_owned(midi_owned),
  .ym_data_in(ym_data),.ym_data_out(data_out),.ym_data_oe(data_oe),
  .translator_dir(dir),.translator_oe_n(oe_n),
  .ym_a0(a0),.ym_cs_n(cs_n),.ym_wr_n(wr_n),.ym_rd_n(rd_n),.ym_reset_n(reset_n),
  .arm_request(arm),.dac_allow(dac),.line_allow(line),
  .fm_sd(fm_sd),.fm_clk(fm_clk),.fm_sh(fm_sh),
  .i2s_bclk(i2s_bclk),.i2s_lrck(i2s_lrck),.i2s_data(i2s_data),
  .audio_ok(audio_ok),.audio_fault(audio_fault));
endmodule
