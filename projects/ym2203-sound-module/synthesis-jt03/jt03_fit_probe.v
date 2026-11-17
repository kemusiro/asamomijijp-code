// SPDX-License-Identifier: GPL-3.0-or-later
// Analysis-only shell: observe every audio bit without exceeding SG48 I/O count.
// The asynchronous read mux is not an I2S interface or an approved board pinout.
module jt03_fit_probe (
    input clk, rst, cen,
    input [7:0] din,
    input addr, cs_n, wr_n,
    input [5:0] audio_select,
    output [7:0] dout,
    output snd_sample,
    output audio_probe
);
    wire signed [15:0] fm;
    wire [7:0] a, b, c;
    wire [39:0] audio_bits = {fm, c, b, a};
    assign audio_probe = audio_select < 40 ? audio_bits[audio_select] : 1'b0;
    revc_jt03 core (
        .clk(clk), .rst(rst), .cen(cen), .din(din), .addr(addr),
        .cs_n(cs_n), .wr_n(wr_n), .dout(dout), .snd_sample(snd_sample),
        .fm_snd(fm), .psg_A(a), .psg_B(b), .psg_C(c)
    );
endmodule
