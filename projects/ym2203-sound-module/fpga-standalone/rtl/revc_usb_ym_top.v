// SPDX-License-Identifier: MIT
// F1 FPGA-only prototype: real YM + Si5351 + I2C v2 + CDC/MIDI USB FS.
// USB IDs must be supplied by the integrator; zero defaults keep USB detached.
module revc_usb_ym_top #(
    parameter integer CONTROL_HZ=48000000,
    parameter integer GAIN_EIGHTHS=8,
    parameter [15:0] USB_VID=0,USB_PID=0,
    parameter [63:0] USB_SERIAL=0
)(
    input wire clk,audio_clk,reset,permit,
    input wire si_scl_in,si_sda_in,
    output wire si_scl_low,si_sda_low,
    input wire config_valid,
    input wire [3:0] config_profile,
    output wire config_done,config_busy,
    output wire [3:0] config_error,clock_error,
    output wire [2:0] active_profile,
    output wire [23:0] ym_frequency,
    output wire clock_good,
    output wire [5:0] clock_state,
    input wire scl_in,sda_in,
    output wire scl_low,sda_low,
    input wire other_owned,global_stop,
    input wire usb_vbus,usb_dp_in,usb_dn_in,
    output wire usb_dp_out,usb_dn_out,usb_tx_enable,usb_pullup_enable,
    output wire usb_configured,usb_online,usb_suspended,cdc_dtr,
    output wire midi_owned,midi_gate,midi_fault,
    output wire [5:0] midi_mask,
    output wire [3:0] midi_state,
    output wire [31:0] midi_received,midi_applied,midi_rejected,midi_invalid,midi_ignored,midi_panics,usb_rejected,

    input wire [7:0] ym_data_in,
    output wire [7:0] ym_data_out,
    output wire ym_data_oe,translator_dir,translator_oe_n,
    output wire ym_a0,ym_cs_n,ym_wr_n,ym_rd_n,ym_reset_n,arm_request,dac_allow,line_allow,
    input wire fm_sd,fm_clk,fm_sh,
    output wire i2s_bclk,i2s_lrck,i2s_data,
    output wire audio_ok,audio_fault,
    output wire [2:0] session_state,
    output wire [3:0] result,error,
    output wire [10:0] queued,
    output wire [31:0] next_sequence,ack_sequence,received,executed,
    output wire sealed,
    output wire [31:0] rx_frames,pcm_samples,clipped,rejections,bus_completed,busy_polls,tx_frames,
    output wire [6:0] pcm_level,native_level,
    output wire [23:0] raw_word,
    output wire [4:0] backend_state,
    output wire [15:0] pcm_probe,
    output wire pcm_probe_valid
);
 initial begin if(CONTROL_HZ!=48000000) $error("USB requires independent 48MHz control clock");end
 wire [63:0] now_us;
 wire prepare_request,silence_request,event_valid,prepare_done,silence_done,event_ready,event_error;
 wire [3:0] prepare_result;
 wire [7:0] event_register,event_value;
 wire blocked,cancel,quarantined;
 wire [31:0] packet;
 wire packet_valid,packet_ready,packet_blocked,malformed,session_clear;
 wire [7:0] rx_data,tx_data;
 wire rx_valid,rx_ready,tx_valid,tx_ready,console_stop,console_panic;
 wire local_reset;
 revc_domain_reset domain(.clk(clk),.async_reset(reset||!permit),.reset(local_reset));
 revc_usb_composite #(.VID(USB_VID),.PID(USB_PID),.SERIAL(USB_SERIAL)) usb_device (
  .clk(clk),.reset(reset),.permit(permit),.usb_vbus(usb_vbus),.dp_in(usb_dp_in),.dn_in(usb_dn_in),
  .dp_out(usb_dp_out),.dn_out(usb_dn_out),.tx_enable(usb_tx_enable),.pullup_enable(usb_pullup_enable),
  .configured(usb_configured),.online(usb_online),.suspended(usb_suspended),.dtr(cdc_dtr),
  .midi_blocked((blocked&&!midi_owned)||quarantined),.flush_midi(cancel||quarantined||session_clear||console_panic),
  .midi_packet(packet),.midi_valid(packet_valid),.midi_ready(packet_ready),.midi_tag_blocked(packet_blocked),.malformed_midi(malformed),
  .cdc_rx_data(rx_data),.cdc_rx_valid(rx_valid),.cdc_rx_ready(rx_ready),
  .cdc_tx_data(tx_data),.cdc_tx_valid(tx_valid),.cdc_tx_ready(tx_ready),.session_clear(session_clear),.rejected_packets(usb_rejected));
 revc_midi_planner midi (
  .clk(clk),.reset(local_reset),.now_us(now_us),.online(usb_online),.blocked(blocked),
  .cancel(cancel||session_clear||console_panic),.malformed(malformed),.audio_ok(audio_ok),
  .packet_valid(packet_valid),.packet_blocked(packet_blocked),.packet(packet),.packet_ready(packet_ready),.quarantined(quarantined),
  .owned(midi_owned),.gate(midi_gate),.fault(midi_fault),.prepare_request(prepare_request),.silence_request(silence_request),
  .event_valid(event_valid),.prepare_done(prepare_done),.silence_done(silence_done),.event_ready(event_ready),.event_error(event_error),
  .prepare_result(prepare_result),.event_register(event_register),.event_value(event_value),.mask(midi_mask),.state_monitor(midi_state),
  .received(midi_received),.applied(midi_applied),.rejected(midi_rejected),.invalid(midi_invalid),.ignored(midi_ignored),.panics(midi_panics));
 wire board_dac,board_line;
 (* async_reg="true",keep=1 *) reg [1:0] gates_meta,gates_sync;
 (* async_reg="true",keep=1 *) reg fault_meta,fault_sync;
 always @(posedge clk) begin
  if(local_reset) begin gates_meta<=0;gates_sync<=0;fault_meta<=0;fault_sync<=0;end
  else begin gates_meta<={line_allow,dac_allow};gates_sync<=gates_meta;fault_meta<=audio_fault;fault_sync<=fault_meta;end
 end
 // Raw VBUS inhibits only MIDI. I2C playback remains independent of USB power/reset.
 assign dac_allow=board_dac&&(!midi_owned||usb_vbus);
 assign line_allow=board_line&&(!midi_owned||usb_vbus);
 revc_usb_console console (
  .clk(clk),.reset(local_reset),.connected(usb_online&&cdc_dtr),.rx_data(rx_data),.rx_valid(rx_valid),.rx_ready(rx_ready),
  .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready),.stop_request(console_stop),.panic_request(console_panic),
  .audio_ok(audio_ok),.audio_fault(fault_sync),.state(session_state),.executed(executed),.gates(gates_sync),
  .midi_owned(midi_owned),.midi_mask(midi_mask));
 revc_clocked_ym_top #(.CONTROL_HZ(CONTROL_HZ),.GAIN_EIGHTHS(GAIN_EIGHTHS),.ALT_SOURCE(1)) board (
  .clk(clk),
  .audio_clk(audio_clk),
  .reset(reset),
  .permit(permit),
  .si_scl_in(si_scl_in),
  .si_sda_in(si_sda_in),
  .si_scl_low(si_scl_low),
  .si_sda_low(si_sda_low),
  .config_valid(config_valid),
  .config_profile(config_profile),
  .config_done(config_done),
  .config_busy(config_busy),
  .config_error(config_error),
  .clock_error(clock_error),
  .active_profile(active_profile),
  .ym_frequency(ym_frequency),
  .clock_good(clock_good),
  .clock_state(clock_state),
  .scl_in(scl_in),
  .sda_in(sda_in),
  .scl_low(scl_low),
  .sda_low(sda_low),
  .other_owned(other_owned),
  .global_stop(global_stop||console_stop),
  .alt_owned(midi_owned),
  .alt_prepare_request(prepare_request),
  .alt_silence_request(silence_request),
  .alt_gate_request(midi_gate),
  .alt_event_valid(event_valid),
  .alt_event_register(event_register),
  .alt_event_value(event_value),
  .alt_prepare_done(prepare_done),
  .alt_silence_done(silence_done),
  .alt_event_ready(event_ready),
  .alt_event_error(event_error),
  .alt_prepare_result(prepare_result),
  .alt_blocked(blocked),
  .alt_cancel(cancel),
  .time_us(now_us),
  .ym_data_in(ym_data_in),
  .ym_data_out(ym_data_out),
  .ym_data_oe(ym_data_oe),
  .translator_dir(translator_dir),
  .translator_oe_n(translator_oe_n),
  .ym_a0(ym_a0),
  .ym_cs_n(ym_cs_n),
  .ym_wr_n(ym_wr_n),
  .ym_rd_n(ym_rd_n),
  .ym_reset_n(ym_reset_n),
  .arm_request(arm_request),
  .dac_allow(board_dac),
  .line_allow(board_line),
  .fm_sd(fm_sd),
  .fm_clk(fm_clk),
  .fm_sh(fm_sh),
  .i2s_bclk(i2s_bclk),
  .i2s_lrck(i2s_lrck),
  .i2s_data(i2s_data),
  .audio_ok(audio_ok),
  .audio_fault(audio_fault),
  .session_state(session_state),
  .result(result),
  .error(error),
  .queued(queued),
  .next_sequence(next_sequence),
  .ack_sequence(ack_sequence),
  .received(received),
  .executed(executed),
  .sealed(sealed),
  .rx_frames(rx_frames),
  .pcm_samples(pcm_samples),
  .clipped(clipped),
  .rejections(rejections),
  .bus_completed(bus_completed),
  .busy_polls(busy_polls),
  .tx_frames(tx_frames),
  .pcm_level(pcm_level),
  .native_level(native_level),
  .raw_word(raw_word),
  .backend_state(backend_state),
  .pcm_probe(pcm_probe),
  .pcm_probe_valid(pcm_probe_valid));
endmodule
