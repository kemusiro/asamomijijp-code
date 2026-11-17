// SPDX-License-Identifier: MIT
// All FM capture/conversion/PCM RAM/I2S processing runs in the audio clock domain.
module revc_audio_path #(
    parameter integer GAIN_EIGHTHS=8,
    parameter integer DYNAMIC_CLOCK=0
) (
    input wire clk, clock_reset, stream_reset, audible,
    input wire sd_in, bitclk_in, sh_in,
    input wire [23:0] ym_frequency,
    output wire bclk,lrck,data,
    output wire healthy,heartbeat,
    output reg fault,
    output wire [31:0] rx_frames,pcm_samples,clipped,rejections,
    output wire [6:0] pcm_level,native_level,
    output wire [23:0] raw_word,
    output wire [31:0] tx_frames,
    output wire [15:0] pcm_probe,
    output wire pcm_probe_valid
);
    wire word_valid,rx_fault;
    wire [23:0] word_data;
    wire [2:0] exponent=word_data[23:21];
    wire signed [10:0] mantissa=$signed({1'b0,word_data[20:11]})-11'sd512;
    wire signed [15:0] decoded=16'(mantissa)<<<(exponent-1'b1);
    wire native_valid,native_ready,native_take;
    wire [15:0] native_head;
    assign raw_word=word_data;
    wire converted_valid,converted_ready,converter_fault;
    wire [15:0] converted,pcm_head;
    wire pcm_valid,pcm_take,tx_primed,tx_fault;
    reg [21:0] since_frame;
    wire clear_stream=clock_reset||stream_reset;
    assign pcm_probe=converted;
    assign pcm_probe_valid=converted_valid&&converted_ready&&!fault&&!clear_stream;
    wire bad_word=word_valid&&exponent==0;
    wire native_overflow=word_valid&&!native_ready;
    wire pcm_overflow=converted_valid&&!converted_ready;
    assign healthy=tx_primed&&!fault&&!clear_stream;
    revc_fm_rx rx(.clk(clk),.reset(clear_stream),.sd_in(sd_in),.bitclk_in(bitclk_in),.sh_in(sh_in),
        .word_valid(word_valid),.word_data(word_data),.fault(rx_fault),.frames(rx_frames),.rejections(rejections));
    revc_audio_fifo native_samples(.clk(clk),.reset(clear_stream),.push(word_valid&&!bad_word&&!fault),
        .data(decoded),.ready(native_ready),.pop(native_take),.valid(native_valid),.head(native_head),.level(native_level));
    revc_fm_pcm #(.STEP_NUM(DYNAMIC_CLOCK!=0 ? 4000000 : 125),
        .STEP_DEN(DYNAMIC_CLOCK!=0 ? 3456000 : 108),.DYNAMIC_STEP(DYNAMIC_CLOCK)) converter(.clk(clk),.reset(clear_stream),.input_valid(native_valid&&!fault),
        .input_sample(native_head),.input_take(native_take),.gain_eighths(5'(GAIN_EIGHTHS)),.step_hz(ym_frequency),
        .output_valid(converted_valid),.output_sample(converted),.output_ready(converted_ready),
        .fault(converter_fault),.samples(pcm_samples),.clipped(clipped));
    revc_audio_fifo pcm(.clk(clk),.reset(clear_stream),.push(converted_valid&&!fault),.data(converted),
        .ready(converted_ready),.pop(pcm_take),.valid(pcm_valid),.head(pcm_head),.level(pcm_level));
    revc_i2s_tx tx(.clk(clk),.clock_reset(clock_reset),.stream_reset(stream_reset),.audible(audible&&!fault),
        .sample_valid(pcm_valid),.sample(pcm_head),.level(pcm_level),.take(pcm_take),
        .bclk(bclk),.lrck(lrck),.data(data),.primed(tx_primed),.fault(tx_fault),.heartbeat(heartbeat),.frames(tx_frames));
    always @(posedge clk) begin
        if(clear_stream) begin fault<=0;since_frame<=0;end
        else begin
            if(word_valid) since_frame<=0;
            else if(since_frame<2457600) since_frame<=since_frame+1'b1;
            if(rx_fault||bad_word||native_overflow||pcm_overflow||converter_fault||tx_fault||since_frame>=2457599) fault<=1;
        end
    end
endmodule
