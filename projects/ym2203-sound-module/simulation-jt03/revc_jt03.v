// SPDX-License-Identifier: GPL-3.0-or-later
// YM2203 configuration of Jose Tejada Gomez's JT12/JT03 (GPL-3.0-or-later).
// Explicit SSG divider: 4 MHz / 4 / 8 / (2 * period) = 4 MHz / (64 * period).
// Upstream jt03.v leaves JT49_DIV at jt12_top's default of 2; use 3 here.
module revc_jt03 (
    input rst, clk, cen,
    input [7:0] din,
    input addr, cs_n, wr_n,
    output [7:0] dout,
    output signed [15:0] fm_snd,
    output [7:0] psg_A, psg_B, psg_C,
    output snd_sample
);
    jt12_top #(
        .use_lfo(0), .use_ssg(1), .num_ch(3), .use_pcm(0),
        .use_adpcm(0), .mask_div(0), .JT49_DIV(3), .YM2203_LUMPED(0)
    ) core (
        .rst(rst), .clk(clk), .cen(cen), .din(din), .addr({1'b0, addr}),
        .cs_n(cs_n), .wr_n(wr_n), .ch_enable(6'd0), .dout(dout),
        .IOA_in(8'hff), .IOB_in(8'hff), .en_hifi_pcm(1'b0),
        .adpcma_data(8'd0), .adpcmb_data(8'd0), .debug_bus(8'd0),
        .psg_A(psg_A), .psg_B(psg_B), .psg_C(psg_C),
        .fm_snd_left(fm_snd), .snd_sample(snd_sample)
    );
endmodule
