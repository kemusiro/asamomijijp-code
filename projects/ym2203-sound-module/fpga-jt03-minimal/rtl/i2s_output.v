// SPDX-License-Identifier: GPL-3.0-or-later
// 49.152 MHz -> 3.072 MHz BCLK, 48 kHz LRCK, 32-bit slots, 16-bit mono in L/R.
// WS changes one BCLK before MSB. Data changes only at BCLK falling edges.
module i2s_output(
    input clk, clock_reset_n, reset_n, running,
    input [15:0] pcm, input valid, input [6:0] level,
    output reg ready, output bclk, lrck, output reg data,
    output reg primed, output reg fault, output heartbeat
);
    reg [9:0] phase;
    reg signed [15:0] frame;
    reg [15:0] shift;
    wire frame_take = phase==1007;
    assign bclk = phase[3];
    assign lrck = phase[9];
    assign heartbeat = phase[9];
    always @(posedge clk or negedge clock_reset_n)
        if(!clock_reset_n) phase<=0;
        else phase<=phase+1'b1;
    always @(posedge clk or negedge reset_n)
        if(!reset_n) begin
            frame<=0; shift<=0; data<=0; primed<=0; fault<=0; ready<=0;
        end else begin
            ready<=(phase==1006) && primed && !fault;
            if(!primed && level>=8 && !fault) primed<=1;
            if(frame_take) begin
                if(ready && valid) frame<=running ? $signed(pcm) : 0;
                else frame<=0;
                if(ready && !valid) begin fault<=1; primed<=0; end
            end
            if(phase[3:0]==15) begin
                if(!running || !primed || fault) data<=0;
                else if(phase[8:4]==0) begin
                    data<=frame[15]; shift<={frame[14:0],1'b0};
                end else if(!phase[8]) begin
                    data<=shift[15]; shift<={shift[14:0],1'b0};
                end
                else data<=0;
            end
        end
endmodule
