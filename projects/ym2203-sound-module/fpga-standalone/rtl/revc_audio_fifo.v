// SPDX-License-Identifier: MIT
// Single-clock sample RAM with registered head and no read-through shortcut.
module revc_audio_fifo #(
    parameter integer BITS=6
) (
    input wire clk, reset,
    input wire push,
    input wire [15:0] data,
    output wire ready,
    input wire pop,
    output reg valid,
    output reg [15:0] head,
    output reg [BITS:0] level
);
    reg [15:0] ram[0:(1<<BITS)-1];
    reg [BITS-1:0] rd,wr;
    reg pending;
    wire take=pop&&valid;
    wire put=push&&ready;
    assign ready=level<(1<<BITS)||take;
    always @(posedge clk) begin
        if(put) ram[wr]<=data;
        if(reset) begin rd<=0;wr<=0;level<=0;valid<=0;pending<=0;head<=0;end
        else begin
            case({put,take})
                2'b10:level<=level+1'b1;
                2'b01:level<=level-1'b1;
                default:begin end
            endcase
            if(put) wr<=wr+1'b1;
            if(take) begin rd<=rd+1'b1;valid<=0;pending<=0;end
            else if(pending) begin valid<=1;pending<=0;end
            else if(level!=0&&!valid) begin head<=ram[rd];pending<=1;end
        end
    end
endmodule
