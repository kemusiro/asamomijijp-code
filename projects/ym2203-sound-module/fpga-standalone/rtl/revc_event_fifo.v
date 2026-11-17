// SPDX-License-Identifier: MIT
// 1024 x 48 event RAM. A staged batch is invisible until publish_count != 0.
// The session engine reserves free space and validates all staged events.
module revc_event_fifo (
    input wire clk, reset, clear,
    input wire stage_write,
    input wire [4:0] stage_offset,
    input wire [47:0] stage_data,
    input wire [5:0] publish_count,
    input wire pop,
    output reg [10:0] level,
    output reg head_valid,
    output reg [47:0] head_data
);
    reg [47:0] ram [0:1023];
    reg [9:0] rd, wr;
    reg read_pending;
    wire [9:0] stage_address = wr + {5'd0, stage_offset};
    wire consume = pop && head_valid;
    always @(posedge clk) begin
        if (stage_write) ram[stage_address] <= stage_data;
        if (reset || clear) begin
            level <= 0;
            rd <= 0;
            wr <= 0;
            head_valid <= 0;
            read_pending <= 0;
            head_data <= 0;
        end else begin
            level <= level + {5'd0, publish_count} - {10'd0, consume};
            if (publish_count != 0) wr <= wr + {4'd0, publish_count};
            if (consume) begin
                rd <= rd + 1'b1;
                head_valid <= 0;
                read_pending <= 0;
            end else if (read_pending) begin
                head_valid <= 1;
                read_pending <= 0;
            end else if (level != 0 && !head_valid) begin
                head_data <= ram[rd];
                read_pending <= 1;
            end
        end
    end
endmodule
