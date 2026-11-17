// SPDX-License-Identifier: GPL-3.0-or-later
// Synchronous event RAM plus one registered lookahead word. Capacity = 256 + 1.
module event_fifo #(parameter AW=8)(
    input clk, reset_n,
    input [47:0] wdata, input wvalid, output wready,
    output reg [47:0] rdata, output reg rvalid, input rready,
    output [AW+1:0] level
);
    reg [47:0] mem [0:(1<<AW)-1];
    reg [AW-1:0] wptr, rptr;
    reg [AW:0] count;
    wire push = wvalid && wready;
    wire fetch = reset_n && (!rvalid || rready) && count!=0;
    assign wready = reset_n && count < (1<<AW);
    assign level = {1'b0,count} + rvalid;
    always @(posedge clk) begin
        if(push) mem[wptr] <= wdata;
        if(fetch) rdata <= mem[rptr];
    end
    always @(posedge clk or negedge reset_n)
        if(!reset_n) begin wptr<=0; rptr<=0; count<=0; rvalid<=0; end
        else begin
            if(push) wptr<=wptr+1'b1;
            if(fetch) rptr<=rptr+1'b1;
            case({push,fetch})
                2'b10: count<=count+1'b1;
                2'b01: count<=count-1'b1;
                default: ;
            endcase
            if(fetch) rvalid<=1;
            else if(rready) rvalid<=0;
        end
endmodule
