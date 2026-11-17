// SPDX-License-Identifier: MIT
// SH falling starts one 24-bit LSB-first frame. Qualify CLK levels, then sample
// SD after an additional settling delay. Short excursions never insert a bit.
module revc_fm_rx #(
    parameter integer QUALIFY=3,
    parameter integer SETTLE=3
) (
    input wire clk, reset,
    input wire sd_in, bitclk_in, sh_in,
    output reg word_valid,
    output reg [23:0] word_data,
    output reg fault,
    output reg [31:0] frames, rejections
);
    (* async_reg="true", keep=1 *) reg [2:0] meta, sync;
    reg stable_clk, prior_sh, armed, need_low, high_seen;
    reg [7:0] qualifier, settling;
    reg [4:0] bits;
    reg [22:0] shift;
    wire sh_fall=prior_sh&&!sync[2];
    wire [23:0] next_word={sync[0],shift};
    always @(posedge clk) begin
        if(reset) begin meta<=0;sync<=0;end
        else begin meta<={sh_in,bitclk_in,sd_in};sync<=meta;end
    end
    always @(posedge clk) begin
        if(reset) begin
            stable_clk<=0;prior_sh<=0;armed<=0;need_low<=1;high_seen<=0;
            qualifier<=0;settling<=0;bits<=0;shift<=0;
            word_valid<=0;word_data<=0;fault<=0;frames<=0;rejections<=0;
        end else begin
            word_valid<=0;prior_sh<=sync[2];
            if(sync[1]==stable_clk) begin
                if(qualifier!=0) rejections<=rejections+1'b1;
                qualifier<=0;
            end else if(qualifier==8'(QUALIFY-1)) begin
                stable_clk<=sync[1];qualifier<=0;
                if(!sync[1]) need_low<=0;
                else if(armed&&!need_low&&!high_seen) begin high_seen<=1;settling<=8'(SETTLE);end
            end else qualifier<=qualifier+1'b1;
            if(high_seen) begin
                if(settling!=0) settling<=settling-1'b1;
                else begin
                    high_seen<=0;need_low<=1;shift<={sync[0],shift[22:1]};
                    if(bits==23) begin
                        word_data<=next_word;word_valid<=1;armed<=0;frames<=frames+1'b1;
                    end else bits<=bits+1'b1;
                end
            end
            if(sh_fall) begin
                if(armed) fault<=1;
                armed<=1;bits<=0;shift<=0;high_seen<=0;need_low<=sync[1];
            end
        end
    end
endmodule
