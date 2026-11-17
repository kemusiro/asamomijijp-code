// SPDX-License-Identifier: MIT
// Dedicated, single-master 100kHz open-drain register bus. Clock stretching is
// bounded by a whole-transaction 5ms timeout. Random read uses repeated START.
module revc_i2c_register_master #(
    parameter integer CLOCK_HZ=48000000,
    parameter [6:0] ADDRESS=7'h60
)(
    input wire clk,reset,scl_in,sda_in,
    output wire scl_low,sda_low,
    input wire request_valid,request_read,
    input wire [7:0] register_address,write_data,
    output wire request_ready,
    output reg response_valid,
    input wire response_ready,
    output reg [2:0] response_error,
    output reg [7:0] read_data
);
    localparam integer HALF=CLOCK_HZ/200000,TIMEOUT=CLOCK_HZ/200;
    localparam IDLE=4'd0,FREE=4'd1,START=4'd2,LOW=4'd3,RISE=4'd4,HIGH=4'd5,
        ACK_LOW=4'd6,ACK_RISE=4'd7,ACK_HIGH=4'd8,
        RESTART_LOW=4'd9,RESTART_RISE=4'd10,STOP_LOW=4'd11,STOP_RISE=4'd12,STOP_HIGH=4'd13,REPLY=4'd14;
    reg [3:0] state;
    reg [31:0] ticks,age;
    reg scl_drive,sda_drive,reading,receiving;
    reg [1:0] byte_index;
    reg [2:0] bit_index;
    reg [7:0] tx,rx,regno,value;
    (* async_reg="true",keep=1 *) reg scl_meta,scl_sync,sda_meta,sda_sync;
    assign scl_low=scl_drive&&!reset;
    assign sda_low=sda_drive&&!reset;
    assign request_ready=state==IDLE;
    always @(posedge clk) begin
        if(reset) begin scl_meta<=1;scl_sync<=1;sda_meta<=1;sda_sync<=1;end
        else begin scl_meta<=scl_in;scl_sync<=scl_meta;sda_meta<=sda_in;sda_sync<=sda_meta;end
    end
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;ticks<=0;age<=0;scl_drive<=0;sda_drive<=0;reading<=0;receiving<=0;
            byte_index<=0;bit_index<=0;tx<=0;rx<=0;regno<=0;value<=0;
            response_valid<=0;response_error<=0;read_data<=0;
        end else if(state==IDLE) begin
            if(request_valid) begin
                regno<=register_address;value<=write_data;reading<=request_read;receiving<=0;
                byte_index<=0;bit_index<=0;tx<={ADDRESS,1'b0};rx<=0;age<=0;ticks<=0;
                response_error<=0;state<=FREE;
            end
        end else if(state==REPLY) begin
            if(response_ready) begin response_valid<=0;state<=IDLE;end
        end else if(age>=TIMEOUT-1) begin
            scl_drive<=0;sda_drive<=0;response_error<=2;response_valid<=1;state<=REPLY;
        end else begin
            age<=age+1'b1;
            if(ticks<HALF-1) ticks<=ticks+1'b1;
            else ticks<=0;
            case(state)
                FREE: if(!scl_sync||!sda_sync) ticks<=0;
                      else if(ticks==HALF-1) begin sda_drive<=1;state<=START;end
                START: if(ticks==HALF-1) begin scl_drive<=1;sda_drive<=!tx[7];state<=LOW;end
                LOW: if(ticks==HALF-1) begin scl_drive<=0;state<=RISE;end
                RISE: begin ticks<=0;if(scl_sync) state<=HIGH;end
                HIGH: if(ticks==HALF-1) begin
                    scl_drive<=1;
                    if(receiving) rx<={rx[6:0],sda_sync};
                    if(!receiving&&tx[7]&&!sda_sync) begin response_error<=3;sda_drive<=1;state<=STOP_LOW;end
                    else if(bit_index==7) begin sda_drive<=0;state<=ACK_LOW;end
                    else begin bit_index<=bit_index+1'b1;tx<={tx[6:0],1'b1};sda_drive<=receiving?1'b0:!tx[6];state<=LOW;end
                end
                ACK_LOW: if(ticks==HALF-1) begin scl_drive<=0;state<=ACK_RISE;end
                ACK_RISE: begin ticks<=0;if(scl_sync) state<=ACK_HIGH;end
                ACK_HIGH: if(ticks==HALF-1) begin
                    scl_drive<=1;bit_index<=0;
                    if(receiving) begin read_data<=rx;sda_drive<=1;state<=STOP_LOW;end
                    else if(sda_sync) begin response_error<=1;sda_drive<=1;state<=STOP_LOW;end
                    else if(byte_index==0) begin byte_index<=1;tx<=regno;sda_drive<=!regno[7];state<=LOW;end
                    else if(byte_index==1&&reading) begin sda_drive<=0;state<=RESTART_LOW;end
                    else if(byte_index==1) begin byte_index<=2;tx<=value;sda_drive<=!value[7];state<=LOW;end
                    else if(reading) begin receiving<=1;sda_drive<=0;state<=LOW;end
                    else begin sda_drive<=1;state<=STOP_LOW;end
                end
                RESTART_LOW: if(ticks==HALF-1) begin scl_drive<=0;state<=RESTART_RISE;end
                RESTART_RISE: begin ticks<=0;if(scl_sync) begin tx<={ADDRESS,1'b1};byte_index<=2;state<=FREE;end end
                STOP_LOW: if(ticks==HALF-1) begin scl_drive<=0;state<=STOP_RISE;end
                STOP_RISE: begin ticks<=0;if(scl_sync) state<=STOP_HIGH;end
                STOP_HIGH: if(ticks==HALF-1) begin sda_drive<=0;response_valid<=1;state<=REPLY;end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
