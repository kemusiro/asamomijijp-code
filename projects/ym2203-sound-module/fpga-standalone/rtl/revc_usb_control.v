// SPDX-License-Identifier: MIT
// EP0 standard + CDC ACM control requests. Mutating requests commit only after
// the host ACKs the status IN packet; a new SETUP cancels the previous request.
module revc_usb_control #(
    parameter [15:0] VID=0,PID=0,
    parameter [63:0] SERIAL=0
)(
    input wire clk,reset,
    input wire setup_valid,
    input wire [63:0] setup_packet,
    input wire out_success,in_success,
    input wire [6:0] out_length,in_offset,
    input wire [55:0] out_data,
    output wire [7:0] in_data,
    output wire [6:0] in_length,
    output wire [1:0] in_handshake,out_handshake,
    output wire in_toggle,out_toggle,
    output reg [6:0] address,
    output reg configured,dtr,
    output reg configuration_event,line_event,
    output reg [4:0] halted,clear_endpoint,
    output reg [55:0] line_coding,
    output reg [31:0] stalls
);
    localparam IDLE=3'd0,DATA_IN=3'd1,DATA_OUT=3'd2,STATUS_IN=3'd3,STATUS_OUT=3'd4,STALL=3'd5;
    localparam DESC=3'd0,CONFIG=3'd1,STATUS=3'd2,INTERFACE=3'd3,LINE=3'd4;
    localparam NONE=3'd0,ADDRESS=3'd1,CONFIGURE=3'd2,CONTROL=3'd3,CLEAR=3'd4,HALT=3'd5,CODING=3'd6,ALT=3'd7;
    reg [2:0] state,response,action;
    reg [15:0] descriptor_key,position,remaining;
    reg [6:0] pending_value;
    reg [15:0] status_value;
    reg [4:0] pending_endpoint;
    reg [55:0] pending_coding;
    reg toggle,zlp;
    wire [7:0] bm=setup_packet[7:0],request=setup_packet[15:8];
    wire [15:0] value=setup_packet[31:16],index=setup_packet[47:32],length=setup_packet[63:48];
    wire [7:0] descriptor_data;
    wire [15:0] descriptor_length;
    wire descriptor_valid;
    wire [15:0] key=setup_valid ? value : descriptor_key;
    revc_usb_descriptors #(.VID(VID),.PID(PID),.SERIAL(SERIAL)) descriptors (
        .key(key),.offset(position+{9'd0,in_offset}),.data(descriptor_data),.length(descriptor_length),.valid(descriptor_valid));
    function [4:0] endpoint_mask;
        input [15:0] endpoint;
        begin case(endpoint)
            16'h81:endpoint_mask=1;16'h02:endpoint_mask=2;16'h82:endpoint_mask=4;
            16'h03:endpoint_mask=8;16'h83:endpoint_mask=16;default:endpoint_mask=0;
        endcase end
    endfunction
    wire [4:0] selected_endpoint=endpoint_mask(index);
    assign in_handshake=state==DATA_IN||state==STATUS_IN ? 2'd0 : state==STALL ? 2'd3 : 2'd2;
    assign out_handshake=state==DATA_OUT||state==STATUS_OUT ? 2'd0 : state==STALL ? 2'd3 : 2'd2;
    assign in_toggle=state==STATUS_IN ? 1'b1 : toggle;
    assign out_toggle=1'b1;
    assign in_length=state==STATUS_IN ? 7'd0 : remaining>=64 ? 7'd64 : remaining[6:0];
    assign in_data=response==DESC ? descriptor_data : response==CONFIG ? {7'd0,configured} :
        response==STATUS ? (in_offset==0 ? status_value[7:0] : status_value[15:8]) :
        response==LINE ? 8'(line_coding>>(8*in_offset)) : 8'd0;
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;response<=DESC;action<=NONE;descriptor_key<=0;position<=0;remaining<=0;pending_value<=0;
            status_value<=0;pending_endpoint<=0;pending_coding<=0;toggle<=1;zlp<=0;
            address<=0;configured<=0;dtr<=0;configuration_event<=0;line_event<=0;
            halted<=0;clear_endpoint<=0;line_coding<=56'h0800000001c200;stalls<=0;
        end else begin
            configuration_event<=0;line_event<=0;clear_endpoint<=0;
            if(setup_valid) begin
                state<=STALL;action<=NONE;position<=0;remaining<=0;toggle<=1;zlp<=0;
                pending_value<=value[6:0];pending_endpoint<=selected_endpoint;
                if(out_length!=8) stalls<=stalls+1'b1;
                else if(bm==8'h80&&request==6&&descriptor_valid&&
                    (value[15:8]==3 ? (index==0||index==16'h409) : index==0)) begin
                    response<=DESC;descriptor_key<=value;
                    remaining<=length<descriptor_length ? length : descriptor_length;
                    zlp<=descriptor_length<length&&descriptor_length[5:0]==0;
                    state<=length==0 ? STATUS_OUT : DATA_IN;
                end else if(bm==0&&request==5&&value<128&&index==0&&length==0&&!configured) begin
                    action<=ADDRESS;state<=STATUS_IN;
                end else if(bm==0&&request==9&&value<2&&index==0&&length==0) begin
                    action<=CONFIGURE;state<=STATUS_IN;
                end else if(bm==8'h80&&request==8&&value==0&&index==0&&length==1) begin
                    response<=CONFIG;remaining<=1;state<=DATA_IN;
                end else if(request==0&&value==0&&length==2&&
                    ((bm==8'h80&&index==0)||(bm==8'h81&&configured&&index<4)||
                    (bm==8'h82&&(index==0||index==128||(configured&&selected_endpoint!=0))))) begin
                    response<=STATUS;remaining<=2;state<=DATA_IN;
                    status_value<=bm==8'h80 ? 16'd1 : bm==8'h82&&|(halted&selected_endpoint) ? 16'd1 : 16'd0;
                end else if(bm==8'h02&&(request==1||request==3)&&value==0&&length==0&&configured&&selected_endpoint!=0) begin
                    action<=request==1 ? CLEAR : HALT;state<=STATUS_IN;
                end else if(bm==8'h81&&request==10&&value==0&&index<4&&length==1&&configured) begin
                    response<=INTERFACE;remaining<=1;state<=DATA_IN;
                end else if(bm==8'h01&&request==11&&value==0&&index<4&&length==0&&configured) begin
                    action<=ALT;pending_endpoint<=index==3 ? 5'b11000 : index==1 ? 5'b00110 : index==0 ? 5'b00001 : 5'd0;state<=STATUS_IN;
                end else if(bm==8'h21&&request==8'h20&&value==0&&index==0&&length==7&&configured) begin
                    action<=CODING;state<=DATA_OUT;
                end else if(bm==8'ha1&&request==8'h21&&value==0&&index==0&&length==7&&configured) begin
                    response<=LINE;remaining<=7;state<=DATA_IN;
                end else if(bm==8'h21&&request==8'h22&&value<4&&index==0&&length==0&&configured) begin
                    action<=CONTROL;state<=STATUS_IN;
                end else stalls<=stalls+1'b1;
            end else begin
                if(out_success) begin
                    if(state==DATA_OUT&&out_length==7&&out_data[31:0]!=0&&out_data[39:32]<=2&&out_data[47:40]<=4&&
                        ((out_data[55:48]>=5&&out_data[55:48]<=8)||out_data[55:48]==16)) begin
                        pending_coding<=out_data;state<=STATUS_IN;
                    end else if(state==STATUS_OUT&&out_length==0) state<=IDLE;
                    else begin state<=STALL;stalls<=stalls+1'b1;end
                end
                if(in_success) begin
                    if(state==DATA_IN) begin
                        toggle<=!toggle;position<=position+{9'd0,in_length};remaining<=remaining-{9'd0,in_length};
                        if(remaining=={9'd0,in_length}) begin
                            if(zlp&&in_length==64) zlp<=0;
                            else state<=STATUS_OUT;
                        end
                    end else if(state==STATUS_IN) begin
                        state<=IDLE;action<=NONE;
                        case(action)
                            ADDRESS:address<=pending_value[6:0];
                            CONFIGURE:begin configured<=pending_value[0];dtr<=0;halted<=0;clear_endpoint<=31;configuration_event<=1;end
                            CONTROL:begin dtr<=pending_value[0];line_event<=1;end
                            CLEAR,ALT:begin halted<=halted&~pending_endpoint;clear_endpoint<=pending_endpoint;end
                            HALT:begin halted<=halted|pending_endpoint;clear_endpoint<=pending_endpoint;end
                            CODING:line_coding<=pending_coding;
                            default:begin end
                        endcase
                    end
                end
            end
        end
    end
endmodule
