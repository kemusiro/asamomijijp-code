// SPDX-License-Identifier: MIT
// Independent control-clock Si5351A startup, verified RMW, lock monitoring and
// stopped-only profile changes. No USB/API extension; HOST I2C is a separate bus.
module revc_si5351_manager #(
    parameter integer CLOCK_HZ=48000000
)(
    input wire clk,reset,scl_in,sda_in,
    output wire scl_low,sda_low,
    input wire config_valid,
    input wire [3:0] config_profile,
    input wire safe_to_change,
    output reg config_done,change_started,
    output reg [3:0] config_error,
    output reg ready,
    output reg [3:0] clock_error,
    output reg [2:0] active_profile,
    output wire [23:0] ym_frequency,
    output wire busy,
    output wire [5:0] state_monitor
);
    localparam POWER=6'd0,INIT_SEND=6'd1,INIT_WAIT=6'd2,ROW_SEND=6'd3,ROW_WAIT=6'd4,
        WRITE_SEND=6'd5,WRITE_WAIT=6'd6,VERIFY_SEND=6'd7,VERIFY_WAIT=6'd8,
        RESET_DELAY=6'd9,RESET_SEND=6'd10,RESET_WAIT=6'd11,LOCK_SEND=6'd12,LOCK_WAIT=6'd13,
        ENABLE_SEND=6'd14,ENABLE_WAIT=6'd15,ENABLE_CHECK=6'd16,ENABLE_REPLY=6'd17,
        RUN=6'd18,MONITOR_SEND=6'd19,MONITOR_WAIT=6'd20,SHUT_SEND=6'd21,SHUT_WAIT=6'd22,FAULT=6'd23,
        STICKY_READ=6'd24,STICKY_VALUE=6'd25,STICKY_WRITE=6'd26,STICKY_WRITTEN=6'd27,
        STICKY_CHECK=6'd28,STICKY_REPLY=6'd29,MONITOR_STICKY_SEND=6'd30,MONITOR_STICKY_WAIT=6'd31;
    reg [5:0] state;
    reg [31:0] age,wait_age,poll_age;
    reg [6:0] index;
    reg [7:0] merged;
    reg [1:0] locked_reads;
    reg seen,configuring;
    wire [23:0] row;
    wire [6:0] count;
    wire [7:0] regno=row[23:16],value=row[15:8],mask=row[7:0];
    wire request_ready,reply;
    wire [2:0] bus_error;
    wire [7:0] data;
    wire requesting=state==INIT_SEND||state==ROW_SEND||state==WRITE_SEND||state==VERIFY_SEND||
        state==RESET_SEND||state==LOCK_SEND||state==ENABLE_SEND||state==ENABLE_CHECK||state==MONITOR_SEND||state==SHUT_SEND||
        state==STICKY_READ||state==STICKY_WRITE||state==STICKY_CHECK||state==MONITOR_STICKY_SEND;
    wire writing=state==WRITE_SEND||state==ENABLE_SEND||state==SHUT_SEND||state==STICKY_WRITE;
    wire [7:0] address=state==INIT_SEND||state==LOCK_SEND||state==MONITOR_SEND ? 8'd0 :
        state==STICKY_READ||state==STICKY_WRITE||state==STICKY_CHECK||state==MONITOR_STICKY_SEND ? 8'd1 :
        state==RESET_SEND ? 8'd177 : state==ENABLE_SEND||state==ENABLE_CHECK||state==SHUT_SEND ? 8'd3 : regno;
    wire [7:0] write_value=state==ENABLE_SEND ? 8'hfc : state==SHUT_SEND ? 8'hff : merged;
    wire taking=state==INIT_WAIT||state==ROW_WAIT||state==WRITE_WAIT||state==VERIFY_WAIT||state==RESET_WAIT||
        state==LOCK_WAIT||state==ENABLE_WAIT||state==ENABLE_REPLY||state==MONITOR_WAIT||state==SHUT_WAIT||
        state==STICKY_VALUE||state==STICKY_WRITTEN||state==STICKY_REPLY||state==MONITOR_STICKY_WAIT;
    assign busy=state!=RUN&&state!=MONITOR_SEND&&state!=MONITOR_WAIT&&state!=MONITOR_STICKY_SEND&&state!=MONITOR_STICKY_WAIT&&state!=FAULT;
    assign state_monitor=state;
    revc_si5351_rom rom(.profile(active_profile),.index(index),.row(row),.frequency(ym_frequency),.count(count));
    revc_i2c_register_master #(.CLOCK_HZ(CLOCK_HZ)) master (
        .clk(clk),.reset(reset),.scl_in(scl_in),.sda_in(sda_in),.scl_low(scl_low),.sda_low(sda_low),
        .request_valid(requesting),.request_read(!writing),.register_address(address),.write_data(write_value),
        .request_ready(request_ready),.response_valid(reply),.response_ready(taking||state==SHUT_SEND),.response_error(bus_error),.read_data(data));
    task fail;
        input [3:0] reason;
        begin ready<=0;clock_error<=reason;if(configuring) begin config_error<=reason;config_done<=1;end configuring<=0;state<=(reason==4||(reason==7&&data[7])) ? FAULT : SHUT_SEND;end
    endtask
    always @(posedge clk) begin
        if(reset) begin
            state<=POWER;age<=0;wait_age<=0;poll_age<=0;index<=0;merged<=0;locked_reads<=0;seen<=0;configuring<=1;
            ready<=0;clock_error<=0;config_error<=0;config_done<=0;change_started<=0;active_profile<=0;
        end else begin
            config_done<=0;change_started<=0;
            if(!config_valid) seen<=0;
            if(age<CLOCK_HZ) age<=age+1'b1;
            if(wait_age<CLOCK_HZ) wait_age<=wait_age+1'b1;
            if(poll_age<CLOCK_HZ) poll_age<=poll_age+1'b1;
            if(config_valid&&!seen) begin
                seen<=1;
                if(config_profile>7) begin config_done<=1;config_error<=1;end
                else if(!safe_to_change||!(state==RUN||state==FAULT)) begin config_done<=1;config_error<=2;end
                else begin
                    configuring<=1;change_started<=1;active_profile<=config_profile[2:0];ready<=0;clock_error<=0;config_error<=0;
                    age<=0;wait_age<=0;poll_age<=0;index<=0;locked_reads<=0;state<=POWER;
                end
            end else if((state<=ENABLE_REPLY||(state>=STICKY_READ&&state<=STICKY_REPLY))&&age>=CLOCK_HZ/2) fail(8);
            else case(state)
                POWER: if(wait_age>=CLOCK_HZ/100) state<=INIT_SEND;
                INIT_SEND: if(request_ready) state<=INIT_WAIT;
                INIT_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if(data[7]) begin if(age>=CLOCK_HZ/10) fail(4);else state<=INIT_SEND;end
                    else begin index<=0;state<=ROW_SEND;end
                end
                ROW_SEND: if(request_ready) state<=ROW_WAIT;
                ROW_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else begin merged<=(data&~mask)|(value&mask);state<=WRITE_SEND;end
                end
                WRITE_SEND: if(request_ready) state<=WRITE_WAIT;
                WRITE_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if(index==count-1'b1) begin state<=RESET_DELAY;wait_age<=0;end
                    else state<=VERIFY_SEND;
                end
                VERIFY_SEND: if(request_ready) state<=VERIFY_WAIT;
                VERIFY_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if((data&mask)!=(merged&mask)) fail(6);
                    else begin index<=index+1'b1;state<=ROW_SEND;end
                end
                RESET_DELAY: if(wait_age>=CLOCK_HZ/500) state<=RESET_SEND;
                RESET_SEND: if(request_ready) state<=RESET_WAIT;
                RESET_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if(wait_age>=CLOCK_HZ/10) fail(5);
                    else if((data&8'ha0)==0) state<=LOCK_SEND;
                    else state<=RESET_SEND;
                end
                LOCK_SEND: if(request_ready) state<=LOCK_WAIT;
                LOCK_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if(wait_age>=CLOCK_HZ/10) fail(5);
                    else if((data&8'he8)!=0) begin locked_reads<=0;state<=RESET_DELAY;end
                    else if(locked_reads==2) state<=STICKY_READ;
                    else begin locked_reads<=locked_reads+1'b1;state<=LOCK_SEND;end
                end
                STICKY_READ: if(request_ready) state<=STICKY_VALUE;
                STICKY_VALUE: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else begin merged<=data&8'h17;state<=STICKY_WRITE;end
                end
                STICKY_WRITE: if(request_ready) state<=STICKY_WRITTEN;
                STICKY_WRITTEN: if(reply) begin if(bus_error!=0) fail(3);else state<=STICKY_CHECK;end
                STICKY_CHECK: if(request_ready) state<=STICKY_REPLY;
                STICKY_REPLY: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if((data&8'he8)!=0) fail(7);
                    else state<=ENABLE_SEND;
                end
                ENABLE_SEND: if(request_ready) state<=ENABLE_WAIT;
                ENABLE_WAIT: if(reply) begin if(bus_error!=0) fail(3);else state<=ENABLE_CHECK;end
                ENABLE_CHECK: if(request_ready) state<=ENABLE_REPLY;
                ENABLE_REPLY: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if(data!=8'hfc) fail(6);
                    else begin ready<=1;config_done<=1;config_error<=0;configuring<=0;state<=RUN;poll_age<=0;end
                end
                RUN: if(poll_age>=CLOCK_HZ/200) begin poll_age<=0;state<=MONITOR_SEND;end
                MONITOR_SEND: if(request_ready) state<=MONITOR_WAIT;
                MONITOR_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if((data&8'he8)!=0) fail(7);
                    else state<=MONITOR_STICKY_SEND;
                end
                MONITOR_STICKY_SEND: if(request_ready) state<=MONITOR_STICKY_WAIT;
                MONITOR_STICKY_WAIT: if(reply) begin
                    if(bus_error!=0) fail(3);
                    else if((data&8'he8)!=0) fail(7);
                    else state<=RUN;
                end
                SHUT_SEND: if(request_ready) state<=SHUT_WAIT;
                SHUT_WAIT: if(reply) state<=FAULT;
                FAULT:ready<=0;
                default:fail(8);
            endcase
        end
    end
endmodule
