// SPDX-License-Identifier: GPL-3.0-or-later
// Consume one ordered (us timestamp, register, value) event, then wait JT03 BUSY.
module ym_bus_writer(
    input clk, reset_n, running,
    input [31:0] now_us, input [47:0] event_data, input event_valid,
    output event_ready, output idle,
    input [7:0] status,
    output reg addr, cs_n, wr_n, output reg [7:0] din,
    output reg committed, output reg [15:0] committed_pair
);
    reg [2:0] state;
    reg [5:0] wait_cycles;
    reg [15:0] pair;
    assign idle = state==0;
    assign event_ready = reset_n && running && idle && event_valid &&
                         event_data[47:16]<=now_us && !status[7];
    always @(posedge clk or negedge reset_n)
        if(!reset_n) begin
            state<=0; wait_cycles<=0; pair<=0;
            addr<=0; cs_n<=1; wr_n<=1; din<=0; committed<=0; committed_pair<=0;
        end else begin
            committed<=0;
            case(state)
                0: if(event_ready) begin
                    pair<=event_data[15:0]; din<=event_data[15:8];
                    addr<=0; cs_n<=0; wr_n<=0; wait_cycles<=31; state<=1;
                end
                1: if(wait_cycles==0) begin
                    cs_n<=1; wr_n<=1; wait_cycles<=31; state<=2;
                end else wait_cycles<=wait_cycles-1'b1;
                2: if(wait_cycles==0) begin
                    din<=pair[7:0]; addr<=1; cs_n<=0; wr_n<=0;
                    wait_cycles<=31; state<=3; committed<=1; committed_pair<=pair;
                end else wait_cycles<=wait_cycles-1'b1;
                3: if(wait_cycles==0) begin
                    cs_n<=1; wr_n<=1; addr<=0; wait_cycles<=31; state<=4;
                end else wait_cycles<=wait_cycles-1'b1;
                4: if(wait_cycles==0) state<=0;
                   else wait_cycles<=wait_cycles-1'b1;
                default: state<=0;
            endcase
        end
endmodule
