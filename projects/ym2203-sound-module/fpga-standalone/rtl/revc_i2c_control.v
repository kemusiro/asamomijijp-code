// SPDX-License-Identifier: MIT
// Clock/timebase wrapper. Board clock manager, YM bus, audio and final inhibit are separate.
module revc_i2c_control #(
    parameter integer CLOCK_HZ = 48000000
) (
    input wire clk, reset,
    input wire scl_in, sda_in,
    output wire scl_low, sda_low,
    input wire audio_ok, other_owned, global_stop,
    output wire prepare_request,
    input wire prepare_done,
    input wire [3:0] prepare_result,
    output wire silence_request,
    input wire silence_done,
    output wire gate_request,source_reserved, event_valid,
    output wire [7:0] event_register, event_value,
    input wire event_ready, event_error,
    output wire [2:0] session_state,
    output wire [3:0] result, error,
    output wire [10:0] queued,
    output wire [31:0] next_sequence, ack_sequence, received, executed,
    output wire sealed
);
    generate if (CLOCK_HZ < 16000000 || CLOCK_HZ % 1000000 != 0) begin : invalid_clock
        initial $error("CLOCK_HZ must be an integer MHz, at least 16 MHz");
    end endgenerate
    localparam integer TICKS_PER_US = CLOCK_HZ / 1000000;
    localparam integer COUNTER_BITS = $clog2(TICKS_PER_US);
    reg [COUNTER_BITS-1:0] sub_us;
    reg [63:0] now_us;
    always @(posedge clk) begin
        if (reset) begin sub_us <= 0; now_us <= 0; end
        else if (sub_us == COUNTER_BITS'(TICKS_PER_US-1)) begin sub_us <= 0; now_us <= now_us + 1'b1; end
        else sub_us <= sub_us + 1'b1;
    end
    revc_i2c_stream stream (
        .clk(clk), .reset(reset), .now_us(now_us),.configured_clock_hz(24'd4000000), .scl_in(scl_in), .sda_in(sda_in),
        .scl_low(scl_low), .sda_low(sda_low), .audio_ok(audio_ok), .other_owned(other_owned),
        .global_stop(global_stop), .prepare_request(prepare_request), .prepare_done(prepare_done),
        .prepare_result(prepare_result), .silence_request(silence_request), .silence_done(silence_done),
        .gate_request(gate_request),.source_reserved(source_reserved), .event_valid(event_valid), .event_register(event_register),
        .event_value(event_value), .event_ready(event_ready), .event_error(event_error),
        .session_state(session_state), .result(result), .error(error), .queued(queued),
        .next_sequence(next_sequence), .ack_sequence(ack_sequence), .received(received), .executed(executed), .sealed(sealed)
    );
endmodule
