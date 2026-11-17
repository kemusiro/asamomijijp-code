// SPDX-License-Identifier: MIT
// F1 with independent control oscillator, dedicated Si5351 I2C bus and variable
// YM clock. Audio remains 49.152MHz; v2 accepts only its original 4MHz format.
module revc_clocked_ym_top #(
    parameter integer CONTROL_HZ=48000000,
    parameter integer GAIN_EIGHTHS=8,
    parameter integer ALT_SOURCE=0
) (
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
    input wire alt_owned,alt_prepare_request,alt_silence_request,alt_gate_request,alt_event_valid,
    input wire [7:0] alt_event_register,alt_event_value,
    output wire alt_prepare_done,alt_silence_done,alt_event_ready,alt_event_error,
    output wire [3:0] alt_prepare_result,
    output wire alt_blocked,alt_cancel,
    output wire [63:0] time_us,

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
    wire change_started;
    // Physical gates also include the audio-domain asynchronous fault inhibit.
    // Synchronize their state before the control-domain clock-change interlock.
    (* async_reg="true",keep=1 *) reg gates_meta,gates_sync;
    always @(posedge clk) begin
        if(management_reset) begin gates_meta<=0;gates_sync<=0;end
        else begin gates_meta<=line_allow||dac_allow;gates_sync<=gates_meta;end
    end
    wire safe_to_change=!(other_owned||(ALT_SOURCE!=0&&alt_owned))&&!gates_sync&&queued==0&&
        (session_state==0||session_state==3||session_state==4||session_state==5);
    wire management_reset;
    revc_domain_reset management_domain(.clk(clk),.async_reset(reset||!permit),.reset(management_reset));
    revc_si5351_manager #(.CLOCK_HZ(CONTROL_HZ)) clocks (
        .clk(clk),.reset(management_reset),.scl_in(si_scl_in),.sda_in(si_sda_in),
        .scl_low(si_scl_low),.sda_low(si_sda_low),.config_valid(config_valid),.config_profile(config_profile),
        .safe_to_change(safe_to_change),.config_done(config_done),.change_started(change_started),
        .config_error(config_error),.ready(clock_good),.clock_error(clock_error),.active_profile(active_profile),
        .ym_frequency(ym_frequency),.busy(config_busy),.state_monitor(clock_state));
    revc_real_ym_top #(.CONTROL_HZ(CONTROL_HZ),.GAIN_EIGHTHS(GAIN_EIGHTHS),.DYNAMIC_CLOCK(1),.ALT_SOURCE(ALT_SOURCE)) real_ym (
        .clk(clk),.audio_clk(audio_clk),.reset(reset),.permit(permit),
        .clock_good(clock_good),.ym_frequency(ym_frequency),.scl_in(scl_in),.sda_in(sda_in),
        .scl_low(scl_low),.sda_low(sda_low),.other_owned(other_owned),.global_stop(global_stop||change_started),
        .alt_owned(alt_owned),.alt_prepare_request(alt_prepare_request),.alt_silence_request(alt_silence_request),
        .alt_gate_request(alt_gate_request),.alt_event_valid(alt_event_valid),.alt_event_register(alt_event_register),.alt_event_value(alt_event_value),
        .alt_prepare_done(alt_prepare_done),.alt_silence_done(alt_silence_done),.alt_event_ready(alt_event_ready),.alt_event_error(alt_event_error),
        .alt_prepare_result(alt_prepare_result),.alt_blocked(alt_blocked),.alt_cancel(alt_cancel),.time_us(time_us),
        .ym_data_in(ym_data_in),.ym_data_out(ym_data_out),.ym_data_oe(ym_data_oe),.translator_dir(translator_dir),
        .translator_oe_n(translator_oe_n),.ym_a0(ym_a0),.ym_cs_n(ym_cs_n),.ym_wr_n(ym_wr_n),
        .ym_rd_n(ym_rd_n),.ym_reset_n(ym_reset_n),.arm_request(arm_request),.dac_allow(dac_allow),
        .line_allow(line_allow),.fm_sd(fm_sd),.fm_clk(fm_clk),.fm_sh(fm_sh),
        .i2s_bclk(i2s_bclk),.i2s_lrck(i2s_lrck),.i2s_data(i2s_data),.audio_ok(audio_ok),
        .audio_fault(audio_fault),.session_state(session_state),.result(result),.error(error),
        .queued(queued),.next_sequence(next_sequence),.ack_sequence(ack_sequence),.received(received),
        .executed(executed),.sealed(sealed),.rx_frames(rx_frames),.pcm_samples(pcm_samples),
        .clipped(clipped),.rejections(rejections),.bus_completed(bus_completed),.busy_polls(busy_polls),
        .tx_frames(tx_frames),.pcm_level(pcm_level),.native_level(native_level),.raw_word(raw_word),
        .backend_state(backend_state),.pcm_probe(pcm_probe),.pcm_probe_valid(pcm_probe_valid));
endmodule
