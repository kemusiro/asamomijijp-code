// SPDX-License-Identifier: MIT
// Four STOP-delimited 208-byte requests. Overflow fails the session, never truncates.
module revc_packet_queue (
    input wire clk, reset, clear,
    input wire write_start, write_valid, write_end,
    input wire [7:0] write_data,
    output reg overflow,
    input wire rx_ready,
    output reg rx_start, rx_valid, rx_end,
    output reg [7:0] rx_data
);
    reg [7:0] ram [0:1023];
    reg [8:0] lengths [0:3];
    reg [1:0] head, tail;
    reg [2:0] count;
    reg active, dropping, oversized;
    reg [8:0] length;
    reg [2:0] state;
    reg [7:0] cursor, read_byte;
    localparam IDLE=3'd0, START=3'd1, FETCH=3'd2, SEND=3'd3, END=3'd4;
    wire enqueue = write_end && active && !dropping && !oversized && length != 0;
    wire dequeue = state == END;
    always @(posedge clk) begin
        if (write_valid && active && !dropping && length < 208)
            ram[{head,length[7:0]}] <= write_data;
        if (state == FETCH) read_byte <= ram[{tail,cursor}];
        if (reset || clear) begin
            head <= 0; tail <= 0; count <= 0; active <= 0; dropping <= 0;
            oversized <= 0; length <= 0; state <= IDLE; cursor <= 0;
            overflow <= 0; rx_start <= 0; rx_valid <= 0; rx_end <= 0; rx_data <= 0;
        end else begin
            overflow <= 0; rx_start <= 0; rx_valid <= 0; rx_end <= 0;
            case ({enqueue,dequeue})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: begin end
            endcase
            if (write_start) begin
                active <= 1; dropping <= count == 4 && !dequeue;
                oversized <= 0; length <= 0;
            end
            if (write_valid && active) begin
                if (length < 209) length <= length + 1'b1;
                if (length >= 208) oversized <= 1;
            end
            if (write_end && active) begin
                active <= 0;
                if ((dropping || oversized) && length != 0) overflow <= 1;
                else if (enqueue) begin lengths[head] <= length; head <= head + 1'b1; end
            end
            case (state)
                IDLE: if (count != 0 && rx_ready) begin cursor <= 0; state <= START; end
                START: begin rx_start <= 1; state <= FETCH; end
                FETCH: state <= SEND;
                SEND: begin
                    rx_valid <= 1; rx_data <= read_byte;
                    if ({1'b0,cursor} + 9'd1 == lengths[tail]) state <= END;
                    else begin cursor <= cursor + 1'b1; state <= FETCH; end
                end
                END: begin rx_end <= 1; tail <= tail + 1'b1; state <= IDLE; end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
