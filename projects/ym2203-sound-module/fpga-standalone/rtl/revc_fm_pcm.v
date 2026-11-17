// SPDX-License-Identifier: MIT
// Streaming rational linear interpolation. Default 125:108 equals Rev C C's
// constant-gain 4MHz conversion across every 125-sample block boundary.
module revc_fm_pcm #(
    parameter integer STEP_NUM=125,
    parameter integer STEP_DEN=108,
    parameter integer DYNAMIC_STEP=0
) (
    input wire clk, reset,
    input wire input_valid,
    input wire [15:0] input_sample,
    output wire input_take,
    input wire [4:0] gain_eighths,
    input wire [23:0] step_hz,
    output wire output_valid,
    output reg [15:0] output_sample,
    input wire output_ready,
    output reg fault,
    output reg [31:0] samples, clipped
);
    localparam integer F=$clog2(STEP_DEN+1);
    localparam integer A=$clog2(STEP_DEN+STEP_NUM+1);
    localparam integer W=18+F;
    localparam NEED_A=4'd0,NEED_B=4'd1,WEIGHTS=4'd2,SUM=4'd3,ABS=4'd4,
               DIVIDE=4'd5,ROUND=4'd6,GAIN=4'd7,CLAMP=4'd8,EMIT=4'd9,ADVANCE=4'd10;
    reg [3:0] state;
    reg signed [15:0] left,right;
    reg [F-1:0] fraction;
    reg [A-1:0] phase;
    reg [4:0] gain;
    reg signed [W-1:0] weighted_left,weighted_right,numerator;
    reg [W-1:0] dividend;
    reg [15:0] quotient;
    reg [F-1:0] remainder;
    reg negative;
    reg [$clog2(W)-1:0] bit_count;
    reg signed [16:0] interpolated;
    reg signed [29:0] gain_product;
    wire [A-1:0] step=DYNAMIC_STEP!=0 ? A'(step_hz) : A'(STEP_NUM);
    wire [F:0] shifted_remainder={remainder,dividend[W-1]};
    wire divide_bit=shifted_remainder>=(F+1)'(STEP_DEN);
    wire [F-1:0] rem_next=divide_bit ? shifted_remainder[F-1:0]-F'(STEP_DEN) : shifted_remainder[F-1:0];
    wire [15:0] quot_next={quotient[14:0],divide_bit};
    wire signed [29:0] scaled=gain_product>>>10;
    wire [F:0] left_weight=(F+1)'(STEP_DEN)-{1'b0,fraction};
    assign input_take=!fault&&input_valid&&(state==NEED_A||state==NEED_B);
    assign output_valid=!fault&&state==EMIT;
    always @(posedge clk) begin
        if(reset) begin
            state<=NEED_A;left<=0;right<=0;fraction<=0;phase<=0;gain<=8;
            weighted_left<=0;weighted_right<=0;numerator<=0;dividend<=0;quotient<=0;
            remainder<=0;negative<=0;bit_count<=0;interpolated<=0;gain_product<=0;
            output_sample<=0;fault<=0;samples<=0;clipped<=0;
        end else if(!fault) begin
            if(gain_eighths>16 || (DYNAMIC_STEP!=0 && (step_hz<1500000 || step_hz>4000000))) fault<=1;
            case(state)
                NEED_A: if(input_take) begin left<=$signed(input_sample);state<=NEED_B;end
                NEED_B: if(input_take) begin right<=$signed(input_sample);state<=ADVANCE;end
                ADVANCE: begin
                    if(phase>=A'(STEP_DEN)) begin phase<=phase-A'(STEP_DEN);left<=right;state<=NEED_B;end
                    else begin fraction<=F'(phase);state<=WEIGHTS;end
                end
                WEIGHTS: begin
                    weighted_left<=left*$signed({1'b0,left_weight});
                    weighted_right<=right*$signed({1'b0,fraction});
                    gain<=gain_eighths;state<=SUM;
                end
                SUM: begin numerator<=weighted_left+weighted_right;state<=ABS;end
                ABS: begin
                    negative<=numerator[W-1];dividend<=numerator[W-1] ? $unsigned(-numerator) : $unsigned(numerator);
                    quotient<=0;remainder<=0;bit_count<=0;state<=DIVIDE;
                end
                DIVIDE: begin
                    dividend<={dividend[W-2:0],1'b0};quotient<=quot_next;remainder<=rem_next;
                    if(bit_count==$clog2(W)'(W-1)) state<=ROUND;
                    else bit_count<=bit_count+1'b1;
                end
                ROUND: begin
                    // Arithmetic floor, including negative values with a remainder.
                    interpolated<=negative ? -$signed({1'b0,quotient[15:0]})-(remainder!=0 ? 17'sd1 : 17'sd0) : $signed({1'b0,quotient[15:0]});
                    state<=GAIN;
                end
                GAIN: begin gain_product<=interpolated*$signed({1'b0,gain,7'd0});state<=CLAMP;end
                CLAMP: begin
                    if(scaled>32767) begin output_sample<=16'h7fff;clipped<=clipped+1'b1;end
                    else if(scaled< -32768) begin output_sample<=16'h8000;clipped<=clipped+1'b1;end
                    else output_sample<=scaled[15:0];
                    state<=EMIT;
                end
                EMIT: if(output_ready) begin
                    samples<=samples+1'b1;phase<=A'(fraction)+step;state<=ADVANCE;
                end
                default:state<=NEED_A;
            endcase
        end
    end
endmodule
