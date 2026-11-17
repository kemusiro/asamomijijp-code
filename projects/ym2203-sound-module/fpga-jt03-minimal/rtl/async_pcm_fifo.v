// SPDX-License-Identifier: GPL-3.0-or-later
// Single-writer / single-reader dual-clock FIFO, with Gray-pointer synchronizers.
// Both domains must be reset together; reset release is synchronized externally.
module async_pcm_fifo #(parameter AW=6, DW=16)(
    input wclk, wrst_n, input [DW-1:0] wdata, input wvalid,
    output wready,
    input rclk, rrst_n, output reg [DW-1:0] rdata,
    output reg rvalid, input rready, output reg [AW:0] rlevel
);
    reg [DW-1:0] mem [0:(1<<AW)-1];
    reg [AW:0] wbin, rbin;
    (* keep=1 *) reg [AW:0] wgray, rgray;
    reg [AW:0] rgray_plus;
    (* async_reg = "true", keep = 1 *) reg [AW:0] rq1_wgray, rq2_wgray;
    (* async_reg = "true", keep = 1 *) reg [AW:0] wq1_rgray, wq2_rgray;
    reg full, empty;
    wire push = wvalid && wready;
    wire fetch = (!rvalid || rready) && !empty;
    wire [AW:0] wnext = wbin + push;
    wire [AW:0] wg_next = (wnext >> 1) ^ wnext;
    wire [AW:0] rnext = rbin + 1'b1;
    wire [AW:0] rplus2 = rbin + 2;
    wire [AW:0] rg_plus2 = (rplus2 >> 1) ^ rplus2;
    wire full_next = wg_next == {~wq2_rgray[AW:AW-1], wq2_rgray[AW-2:0]};
    function [AW:0] ungray;
        input [AW:0] g;
        integer i;
        begin
            ungray[AW]=g[AW];
            for(i=AW-1;i>=0;i=i-1) ungray[i]=ungray[i+1]^g[i];
        end
    endfunction
    assign wready = wrst_n && !full;
    always @(posedge wclk) if(push) mem[wbin[AW-1:0]] <= wdata;
    always @(posedge rclk) if(fetch) rdata <= mem[rbin[AW-1:0]];
    always @(posedge wclk or negedge wrst_n)
        if(!wrst_n) begin
            wbin<=0; wgray<=0; full<=0; wq1_rgray<=0; wq2_rgray<=0;
        end else begin
            wq1_rgray<=rgray; wq2_rgray<=wq1_rgray;
            wbin<=wnext; wgray<=wg_next; full<=full_next;
        end
    always @(posedge rclk or negedge rrst_n)
        if(!rrst_n) begin
            rbin<=0; rgray<=0; rgray_plus<=1; rvalid<=0; rlevel<=0; empty<=1; rq1_wgray<=0; rq2_wgray<=0;
        end else begin
            rq1_wgray<=wgray; rq2_wgray<=rq1_wgray;
            if(fetch) begin rbin<=rnext; rgray<=rgray_plus; rgray_plus<=rg_plus2; end
            rlevel <= (ungray(rq2_wgray)-rbin) + rvalid;
            empty<=fetch ? (rgray_plus==rq2_wgray) : (rgray==rq2_wgray);
            if(fetch) rvalid<=1;
            else if(rready) rvalid<=0;
        end
endmodule
