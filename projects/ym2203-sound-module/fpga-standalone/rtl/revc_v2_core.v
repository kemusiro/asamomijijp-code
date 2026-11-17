// SPDX-License-Identifier: MIT
// Synchronous transaction-level top; rx_start follows the I2C address phase.
module revc_v2_core #(parameter integer CHECK_CLOCK=0) (
    input wire clk, reset,
    input wire [63:0] now_us,
    input wire [23:0] configured_clock_hz,
    input wire audio_ok, other_owned, global_stop, transport_error,
    output wire rx_ready,
    input wire rx_start, rx_valid,
    input wire [7:0] rx_data,
    input wire rx_end, rx_abort,
    output wire prepare_request,
    input wire prepare_done,
    input wire [3:0] prepare_result,
    output wire silence_request,
    input wire silence_done,
    output wire gate_request,source_reserved,
    output wire event_valid,
    output wire [7:0] event_register, event_value,
    input wire event_ready, event_error,
    input wire status_request,
    output wire status_busy, status_valid,
    input wire [7:0] status_address,
    output wire [7:0] status_data,
    output wire [2:0] session_state,
    output wire [3:0] result, error,
    output wire [10:0] queued,
    output wire [31:0] next_sequence, ack_sequence, received, executed,
    output wire sealed
);
    wire frame_valid, frame_take;
    wire [3:0] frame_result;
    wire [8:0] frame_length;
    wire [7:0] frame_opcode, frame_address, frame_data;
    wire [31:0] frame_sequence;
    wire [15:0] payload_length;
    revc_v2_frame frame (
        .clk(clk), .reset(reset || global_stop || transport_error), .rx_ready(rx_ready),
        .rx_start(rx_start), .rx_valid(rx_valid), .rx_data(rx_data), .rx_end(rx_end), .rx_abort(rx_abort),
        .frame_valid(frame_valid), .frame_take(frame_take), .frame_result(frame_result),
        .frame_length(frame_length), .opcode(frame_opcode), .frame_sequence(frame_sequence),
        .payload_length(payload_length), .read_address(frame_address), .read_data(frame_data)
    );
    revc_v2_session #(.CHECK_CLOCK(CHECK_CLOCK)) session (
        .clk(clk), .reset(reset), .now_us(now_us),.configured_clock_hz(configured_clock_hz), .audio_ok(audio_ok), .other_owned(other_owned),
        .global_stop(global_stop), .transport_error(transport_error), .frame_valid(frame_valid),
        .frame_take(frame_take), .frame_result(frame_result), .frame_length(frame_length),
        .frame_opcode(frame_opcode), .frame_sequence(frame_sequence), .frame_payload_length(payload_length),
        .frame_address(frame_address), .frame_data(frame_data),
        .prepare_request(prepare_request), .prepare_done(prepare_done), .prepare_result(prepare_result),
        .silence_request(silence_request), .silence_done(silence_done), .gate_request(gate_request),.source_reserved(source_reserved),
        .event_valid(event_valid), .event_register(event_register), .event_value(event_value),
        .event_ready(event_ready), .event_error(event_error),
        .status_request(status_request), .status_busy(status_busy), .status_valid(status_valid),
        .status_address(status_address), .status_data(status_data), .session_state(session_state),
        .result(result), .error(error), .queued(queued), .next_sequence(next_sequence),
        .ack_sequence(ack_sequence), .received(received), .executed(executed), .sealed(sealed)
    );
endmodule
