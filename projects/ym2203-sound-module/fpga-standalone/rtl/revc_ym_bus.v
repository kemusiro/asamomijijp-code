// SPDX-License-Identifier: MIT
// External YM2203 register access. Conservative Rev C fast timing: 1us phases,
// 2us write recovery, status BUSY before address AND data, break-before-make.
module revc_ym_bus #(
    parameter integer CLOCK_HZ=48000000
) (
    input wire clk, reset, cancel,
    input wire request_valid, request_read,
    input wire [7:0] request_register, request_value,
    output wire request_ready,
    output reg response_valid, response_error, response_aborted,
    output reg [7:0] response_data,
    input wire response_ready,
    input wire [7:0] ym_data_in,
    output wire [7:0] ym_data_out,
    output wire ym_data_oe,
    output reg translator_dir,
    output wire translator_oe_n,
    output wire ym_a0, ym_cs_n, ym_wr_n, ym_rd_n,
    output reg [31:0] completed, busy_polls
);
    localparam integer PHASE=CLOCK_HZ/1000000;
    localparam integer LIMIT=CLOCK_HZ/10;
    localparam IDLE=5'd0, R_OFF=5'd1, R_DIR=5'd2, R_SET=5'd3,
               R_LOW=5'd4, R_HOLD=5'd5, R_END=5'd6,
               W_OFF=5'd7, W_DIR=5'd8, W_SET=5'd9, W_CS=5'd10,
               W_LOW=5'd11, W_HOLD=5'd12, W_END=5'd13, REPLY=5'd14;
    reg [4:0] state;
    reg [31:0] ticks, age;
    reg [7:0] regno, value, sampled;
    reg reading, addressed, data_read, aborted;
    reg [7:0] data_pin;
    reg a0_pin,cs_pin,wr_pin,rd_pin,oe_pin,drive_pin;
    (* async_reg="true", keep=1 *) reg [7:0] data_meta, data_sync;
    wire write_drive=state>=W_SET && state<=W_END;
    wire read_drive=state>=R_SET && state<=R_HOLD;
    assign request_ready=state==IDLE;
    // Pin strobes are flops, never binary-FSM combinational decodes.
    assign ym_a0=a0_pin;
    assign ym_data_out=data_pin;
    assign ym_data_oe=drive_pin&&!reset&&!response_error;
    assign translator_oe_n=oe_pin||reset||response_error;
    assign ym_cs_n=cs_pin||reset||response_error;
    assign ym_rd_n=rd_pin||reset||response_error;
    assign ym_wr_n=wr_pin||reset||response_error;
    always @(posedge clk) begin
        if(reset) begin data_pin<=0;a0_pin<=0;cs_pin<=1;wr_pin<=1;rd_pin<=1;oe_pin<=1;drive_pin<=0;end
        else begin
            data_pin<=addressed ? value : regno;
            a0_pin<=write_drive ? addressed : data_read;
            drive_pin<=write_drive;oe_pin<=!(write_drive||read_drive);
            cs_pin<=!(state==R_LOW||(state>=W_CS&&state<=W_HOLD));
            rd_pin<=!(state>=R_SET&&state<=R_HOLD);wr_pin<=state!=W_LOW;
        end
    end
    always @(posedge clk) begin
        if(reset) begin data_meta<=0;data_sync<=0;end
        else begin data_meta<=ym_data_in;data_sync<=data_meta;end
    end
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;ticks<=0;age<=0;regno<=0;value<=0;sampled<=0;
            reading<=0;addressed<=0;data_read<=0;aborted<=0;translator_dir<=0;
            response_valid<=0;response_error<=0;response_aborted<=0;response_data<=0;
            completed<=0;busy_polls<=0;
        end else if(state==IDLE) begin
            if(request_valid && !cancel) begin
                regno<=request_register;value<=request_value;reading<=request_read;
                addressed<=0;data_read<=0;aborted<=0;age<=0;
                response_error<=0;response_aborted<=0;response_valid<=0;
                state<=R_OFF;ticks<=PHASE-1;
            end
        end else if(state==REPLY) begin
            if(response_ready) begin response_valid<=0;state<=IDLE;end
        end else begin
            age<=age+1'b1;
            if(cancel) aborted<=1;
            if(age>=LIMIT-1) begin
                response_error<=1;response_valid<=1;response_aborted<=aborted||cancel;
                state<=REPLY;
            end else if(ticks!=0) ticks<=ticks-1'b1;
            else begin
                ticks<=PHASE-1;
                case(state)
                    R_OFF: begin translator_dir<=0;state<=R_DIR;end
                    R_DIR: state<=R_SET;
                    R_SET: state<=R_LOW;
                    R_LOW: begin sampled<=data_sync;state<=R_HOLD;end
                    R_HOLD: state<=R_END;
                    R_END: begin
                        if(aborted||cancel) begin response_valid<=1;response_aborted<=1;state<=REPLY;end
                        else if(data_read) begin response_data<=sampled;response_valid<=1;state<=REPLY;completed<=completed+1'b1;end
                        else if(sampled[7]) begin busy_polls<=busy_polls+1'b1;state<=R_OFF;end
                        else if(reading&&addressed) begin data_read<=1;state<=R_OFF;end
                        else state<=W_OFF;
                    end
                    W_OFF: begin translator_dir<=1;state<=W_DIR;end
                    W_DIR: state<=W_SET;
                    W_SET: state<=W_CS;
                    W_CS: state<=W_LOW;
                    W_LOW: state<=W_HOLD;
                    W_HOLD: begin state<=W_END;ticks<=2*PHASE-1;end
                    W_END: begin
                        if(aborted||cancel) begin response_valid<=1;response_aborted<=1;state<=REPLY;end
                        else if(!addressed) begin addressed<=1;state<=R_OFF;end
                        else begin response_valid<=1;state<=REPLY;completed<=completed+1'b1;end
                    end
                    default: state<=IDLE;
                endcase
            end
        end
    end
endmodule
