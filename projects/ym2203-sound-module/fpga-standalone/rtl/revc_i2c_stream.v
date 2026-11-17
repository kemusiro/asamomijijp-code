// SPDX-License-Identifier: MIT
// Physical I2C + four-request queue + v2 core. now_us is a synchronous 64-bit clock.
module revc_i2c_stream #(parameter integer CHECK_CLOCK=0) (
    input wire clk, reset,
    input wire [63:0] now_us,
    input wire [23:0] configured_clock_hz,
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
    wire write_start, write_valid, write_end;
    wire [7:0] write_data;
    wire overflow, rx_ready, rx_start, rx_valid, rx_end;
    wire [7:0] rx_data, status_address, status_data;
    wire status_request, status_busy, status_valid;
    revc_i2c_target target (
        .clk(clk), .reset(reset), .scl_in(scl_in), .sda_in(sda_in),
        .scl_low(scl_low), .sda_low(sda_low), .write_start(write_start),
        .write_valid(write_valid), .write_end(write_end), .write_data(write_data),
        .status_request(status_request), .status_busy(status_busy), .status_valid(status_valid),
        .status_address(status_address), .status_data(status_data)
    );
    revc_packet_queue packets (
        .clk(clk), .reset(reset), .clear(global_stop || overflow),
        .write_start(write_start), .write_valid(write_valid), .write_end(write_end),
        .write_data(write_data), .overflow(overflow), .rx_ready(rx_ready),
        .rx_start(rx_start), .rx_valid(rx_valid), .rx_end(rx_end), .rx_data(rx_data)
    );
    revc_v2_core #(.CHECK_CLOCK(CHECK_CLOCK)) core (
        .clk(clk), .reset(reset), .now_us(now_us),.configured_clock_hz(configured_clock_hz), .audio_ok(audio_ok), .other_owned(other_owned),
        .global_stop(global_stop), .transport_error(overflow), .rx_ready(rx_ready),
        .rx_start(rx_start), .rx_valid(rx_valid), .rx_data(rx_data), .rx_end(rx_end), .rx_abort(1'b0),
        .prepare_request(prepare_request), .prepare_done(prepare_done), .prepare_result(prepare_result),
        .silence_request(silence_request), .silence_done(silence_done), .gate_request(gate_request),.source_reserved(source_reserved),
        .event_valid(event_valid), .event_register(event_register), .event_value(event_value),
        .event_ready(event_ready), .event_error(event_error),
        .status_request(status_request), .status_busy(status_busy), .status_valid(status_valid),
        .status_address(status_address), .status_data(status_data),
        .session_state(session_state), .result(result), .error(error), .queued(queued),
        .next_sequence(next_sequence), .ack_sequence(ack_sequence), .received(received), .executed(executed),
        .sealed(sealed)
    );
endmodule
