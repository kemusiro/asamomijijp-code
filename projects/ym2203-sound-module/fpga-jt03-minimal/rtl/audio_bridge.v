// SPDX-License-Identifier: GPL-3.0-or-later
// Fixed 4 MHz JT03 -> 48 kHz PCM. FM: one-native-frame linear interpolation.
// SSG: two shift-IIR poles at 1 MHz. Mix/DC blocker use wide signed arithmetic.
module audio_bridge(
    input clk, reset_n, running,
    input signed [15:0] fm,
    input fm_sample,
    input [7:0] ssg_a, ssg_b, ssg_c,
    output reg [15:0] pcm,
    output reg valid
);
    reg sample_last;
    reg signed [15:0] fm_prev, fm_cur;
    reg [7:0] fraction;
    reg [3:0] ninth;
    reg [9:0] phase;
    reg [3:0] micro;
    reg signed [17:0] ssg_filter1, ssg_filter2;
    wire [9:0] ssg_sum = {2'b0,ssg_a}+{2'b0,ssg_b}+{2'b0,ssg_c};
    wire signed [17:0] ssg_target = $signed({2'b0,ssg_sum,6'b0});
    wire signed [15:0] difference = (fm_cur >>> 1) - (fm_prev >>> 1);
    reg signed [24:0] product;
    reg signed [15:0] previous;
    reg signed [17:0] psg;
    reg signed [17:0] mixed;
    reg signed [27:0] dc, ac;
    wire signed [27:0] target = $signed({{10{mixed[17]}},mixed}) <<< 10;
    wire signed [27:0] error = target-dc;
    wire signed [27:0] scaled = ac >>> 11; // common 0.5 gain; no 16-bit mixer wrap
    wire signed [24:0] interpolated = $signed({{9{previous[15]}},previous})+(product>>>8);
    wire signed [24:0] wide_mix = (interpolated<<<1)+($signed({{7{psg[17]}},psg})<<<5);
    reg [2:0] step;
    always @(posedge clk or negedge reset_n)
        if(!reset_n) begin
            sample_last<=0; fm_prev<=0; fm_cur<=0; fraction<=0; ninth<=0;
            phase<=0; micro<=0; ssg_filter1<=0; ssg_filter2<=0;
            product<=0; previous<=0; psg<=0; mixed<=0; dc<=0; ac<=0;
            step<=0; pcm<=0; valid<=0;
        end else begin
            sample_last<=fm_sample; valid<=0;
            micro<=micro+1'b1;
            if(!running) begin
                fm_prev<=0; fm_cur<=0; fraction<=0; ninth<=0;
                ssg_filter1<=0; ssg_filter2<=0;
            end else begin
                if(fm_sample && !sample_last) begin
                    fm_prev<=fm_cur; fm_cur<=fm; fraction<=0; ninth<=0;
                end else begin
                    if(ninth==8) ninth<=0;
                    else ninth<=ninth+1'b1;
                    if(ninth!=0) fraction<=fraction+1'b1;
                end
                if(micro==0) begin
                    ssg_filter1<=ssg_filter1+((ssg_target-ssg_filter1)>>>3);
                    ssg_filter2<=ssg_filter2+((ssg_filter1-ssg_filter2)>>>3);
                end
            end
            if(phase>=997) begin
                phase<=phase-997; step<=1;
                product<=difference*$signed({1'b0,fraction});
                previous<=fm_prev>>>1;
                psg<=ssg_filter2>>>6;
            end else phase<=phase+3;
            case(step)
                1: begin mixed<=wide_mix[17:0]; step<=2; end
                2: begin ac<=error; dc<=running ? dc+(error>>>10) : 0; step<=3; end
                3: begin
                    if(!running) pcm<=0;
                    else if(scaled>32767) pcm<=16'h7fff;
                    else if(scaled< -32768) pcm<=16'h8000;
                    else pcm<=scaled[15:0];
                    valid<=1; step<=0;
                end
                default: ;
            endcase
        end
endmodule
