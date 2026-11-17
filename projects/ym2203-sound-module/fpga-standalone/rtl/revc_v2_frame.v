// SPDX-License-Identifier: MIT
// Rev C v2 framing/CRC only. Sequence, ownership and command semantics are downstream.
// All inputs are synchronous to clk; physical I2C/USB reception is a separate layer.
module revc_v2_frame (
    input wire clk,
    input wire reset,
    output wire rx_ready,
    input wire rx_start,
    input wire rx_valid,
    input wire [7:0] rx_data,
    input wire rx_end,
    input wire rx_abort,
    output wire frame_valid,
    input wire frame_take,
    output reg [3:0] frame_result,
    output wire [8:0] frame_length,
    output reg [7:0] opcode,
    output reg [31:0] frame_sequence,
    output reg [15:0] payload_length,
    input wire [7:0] read_address,
    output wire [7:0] read_data
);
    localparam IDLE = 2'd0, RECEIVE = 2'd1, CHECK = 2'd2, HOLD = 2'd3;
    reg [1:0] state;
    reg [7:0] packet [0:207];
    reg [8:0] count;
    reg malformed;
    reg aborted;
    reg [31:0] crc;
    // Retain the last four bytes, processing older bytes into CRC. This avoids
    // trusting a corrupt declared length when locating the CRC trailer.
    reg [31:0] trailer;

    function [31:0] crc_byte;
        input [31:0] prior;
        input [7:0] value;
        reg [31:0] c;
        integer i;
        begin
            c = prior ^ {24'd0, value};
            for (i = 0; i < 8; i = i + 1)
                c = (c >> 1) ^ (c[0] ? 32'hedb88320 : 32'd0);
            crc_byte = c;
        end
    endfunction

    assign rx_ready = state == IDLE;
    assign frame_valid = state == HOLD;
    assign frame_length = count;
    assign read_data = read_address < 208 ? packet[read_address] : 8'hff;

    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE;
            count <= 0;
            malformed <= 0;
            aborted <= 0;
            crc <= 32'hffffffff;
            trailer <= 0;
            frame_result <= 0;
            opcode <= 0;
            frame_sequence <= 0;
            payload_length <= 0;
        end else begin
            case (state)
                IDLE: if (rx_start) begin
                    state <= RECEIVE;
                    count <= 0;
                    malformed <= 0;
                    aborted <= 0;
                    crc <= 32'hffffffff;
                    trailer <= 0;
                    opcode <= 0;
                    frame_sequence <= 0;
                    payload_length <= 0;
                    frame_result <= 0;
                end
                RECEIVE: begin
                    if (rx_valid) begin
                        if (count < 208) packet[count[7:0]] <= rx_data;
                        // Saturation makes arbitrarily oversized frames invalid.
                        if (count < 209) count <= count + 1'b1;
                        if (count >= 208) malformed <= 1;
                        trailer <= {rx_data, trailer[31:8]};
                        if (count >= 4) crc <= crc_byte(crc, trailer[7:0]);
                        case (count)
                            0: if (rx_data != 8'h59) malformed <= 1;
                            1: if (rx_data != 8'h32) malformed <= 1;
                            2: if (rx_data != 2) malformed <= 1;
                            3: opcode <= rx_data;
                            4: frame_sequence[7:0] <= rx_data;
                            5: frame_sequence[15:8] <= rx_data;
                            6: frame_sequence[23:16] <= rx_data;
                            7: frame_sequence[31:24] <= rx_data;
                            8: payload_length[7:0] <= rx_data;
                            9: payload_length[15:8] <= rx_data;
                            10, 11: if (rx_data != 0) malformed <= 1;
                            default: begin end
                        endcase
                    end
                    if (rx_end || rx_abort) begin
                        aborted <= rx_abort;
                        state <= CHECK;
                    end
                end
                CHECK: begin
                    // Match stream.c's envelope validation order: shape before CRC.
                    if (aborted) frame_result <= 7;
                    else if (malformed || count < 16 || payload_length > 192 ||
                             {7'd0, count} != 16'd16 + payload_length)
                        frame_result <= 2;
                    else if (~crc != trailer) frame_result <= 1;
                    else frame_result <= 0;
                    state <= HOLD;
                end
                HOLD: if (frame_take) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
