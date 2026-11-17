// SPDX-License-Identifier: MIT
// I2C v2 + real YM2203 bus and FM audio. External Si5351 must already supply
// 4MHz to YM and 49.152MHz audio; the independent control clock is 48MHz.
module revc_real_ym_top #(
    parameter integer CONTROL_HZ=48000000,
    parameter integer GAIN_EIGHTHS=8,
    parameter integer DYNAMIC_CLOCK=0,
    parameter integer ALT_SOURCE=0
) (
    input wire clk,audio_clk,reset,permit,clock_good,
    input wire [23:0] ym_frequency,
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
    initial begin
        if(CONTROL_HZ<16000000 || CONTROL_HZ%1000000!=0) $error("CONTROL_HZ must be an integer MHz >=16MHz");
        if(GAIN_EIGHTHS<0 || GAIN_EIGHTHS>16) $error("GAIN_EIGHTHS must be 0..16");
    end
    localparam integer US_TICKS=CONTROL_HZ/1000000;
    reg [$clog2(US_TICKS)-1:0] sub_us;
    reg [63:0] now_us;
    wire control_reset;
    revc_domain_reset domain(.clk(clk),.async_reset(reset||!permit),.reset(control_reset));
    always @(posedge clk) begin
        if(control_reset) begin sub_us<=0;now_us<=0;end
        else if(sub_us==$clog2(US_TICKS)'(US_TICKS-1)) begin sub_us<=0;now_us<=now_us+1'b1;end
        else sub_us<=sub_us+1'b1;
    end
    wire use_alt=ALT_SOURCE!=0&&alt_owned;
    wire source_reserved;
    wire prepare_request,prepare_done,silence_request,silence_done,gate_request,event_valid,event_ready,event_error;
    wire [3:0] prepare_result;
    wire [7:0] event_register,event_value;
    wire be_prepare_done,be_silence_done,be_event_ready,be_event_error;
    wire [3:0] be_prepare_result;
    assign time_us=now_us;
    assign prepare_done=be_prepare_done&&!use_alt;
    assign prepare_result=be_prepare_result;
    assign silence_done=be_silence_done;
    assign event_ready=be_event_ready&&!use_alt;
    assign event_error=be_event_error&&!use_alt;
    assign alt_prepare_done=be_prepare_done&&use_alt;
    assign alt_prepare_result=be_prepare_result;
    assign alt_silence_done=be_silence_done&&use_alt;
    assign alt_event_ready=be_event_ready&&use_alt;
    assign alt_event_error=be_event_error&&use_alt;
    assign alt_blocked=source_reserved||silence_request||session_state==5||other_owned||!audio_ok||
        !clock_good||global_stop||(DYNAMIC_CLOCK!=0&&ym_frequency!=4000000);
    assign alt_cancel=silence_request||global_stop||!clock_good||!permit||reset;
    revc_i2c_stream #(.CHECK_CLOCK(DYNAMIC_CLOCK)) control (
        .clk(clk),.reset(control_reset),.now_us(now_us),.configured_clock_hz(DYNAMIC_CLOCK!=0 ? ym_frequency : 24'd4000000),.scl_in(scl_in),.sda_in(sda_in),
        .scl_low(scl_low),.sda_low(sda_low),.audio_ok(audio_ok),.other_owned(other_owned||use_alt),.global_stop(global_stop),
        .prepare_request(prepare_request),.prepare_done(prepare_done),.prepare_result(prepare_result),
        .silence_request(silence_request),.silence_done(silence_done),.gate_request(gate_request),.source_reserved(source_reserved),
        .event_valid(event_valid),.event_register(event_register),.event_value(event_value),
        .event_ready(event_ready),.event_error(event_error),.session_state(session_state),.result(result),.error(error),
        .queued(queued),.next_sequence(next_sequence),.ack_sequence(ack_sequence),.received(received),.executed(executed),.sealed(sealed));
    revc_ym_backend #(.CONTROL_HZ(CONTROL_HZ),.GAIN_EIGHTHS(GAIN_EIGHTHS),.DYNAMIC_CLOCK(DYNAMIC_CLOCK)) backend (
        .clk(clk),.audio_clk(audio_clk),.reset(reset),.permit(permit),.clock_good(clock_good),.now_us(now_us),.ym_frequency(DYNAMIC_CLOCK!=0 ? ym_frequency : 24'd4000000),
        .prepare_request(prepare_request||(use_alt&&alt_prepare_request)),.prepare_done(be_prepare_done),.prepare_result(be_prepare_result),
        .silence_request(silence_request||(use_alt&&alt_silence_request)),.silence_done(be_silence_done),.gate_request(gate_request||(use_alt&&alt_gate_request)),.audio_ok(audio_ok),
        .event_valid(use_alt?alt_event_valid:event_valid),.event_register(use_alt?alt_event_register:event_register),.event_value(use_alt?alt_event_value:event_value),.event_ready(be_event_ready),.event_error(be_event_error),
        .ym_data_in(ym_data_in),.ym_data_out(ym_data_out),.ym_data_oe(ym_data_oe),.translator_dir(translator_dir),
        .translator_oe_n(translator_oe_n),.ym_a0(ym_a0),.ym_cs_n(ym_cs_n),.ym_wr_n(ym_wr_n),.ym_rd_n(ym_rd_n),
        .ym_reset_n(ym_reset_n),.arm_request(arm_request),.dac_allow(dac_allow),.line_allow(line_allow),
        .fm_sd(fm_sd),.fm_clk(fm_clk),.fm_sh(fm_sh),.i2s_bclk(i2s_bclk),.i2s_lrck(i2s_lrck),.i2s_data(i2s_data),
        .rx_frames(rx_frames),.pcm_samples(pcm_samples),.clipped(clipped),.rejections(rejections),
        .bus_completed(bus_completed),.busy_polls(busy_polls),.tx_frames(tx_frames),.pcm_level(pcm_level),
        .native_level(native_level),.raw_word(raw_word),.backend_state(backend_state),.audio_fault(audio_fault),
        .pcm_probe(pcm_probe),.pcm_probe_valid(pcm_probe_valid));
endmodule
