// SPDX-License-Identifier: MIT
// 49.152MHz / 16 = 3.072MHz BCLK. 32-bit I2S slots, 48kHz frames.
// Left is signed PCM16 with zero padding; right is zero, as in Rev C's DAC path.
module revc_i2s_tx (
    input wire clk, clock_reset, stream_reset, audible,
    input wire sample_valid,
    input wire [15:0] sample,
    input wire [6:0] level,
    output wire take,
    output wire bclk,
    output reg lrck, data,
    output reg primed, fault,
    output reg heartbeat,
    output reg [31:0] frames
);
    reg [3:0] divider;
    reg [5:0] position;
    reg [15:0] held;
    wire falling=divider==15;
    wire boundary=falling&&position==0;
    assign bclk=divider[3];
    assign take=boundary&&primed&&!fault&&!stream_reset&&sample_valid;
    always @(posedge clk) begin
        // Start in the right slot so the first left word has an observable
        // WS transition followed by the standard one-bit delay.
        if(clock_reset) begin divider<=0;position<=0;lrck<=1;data<=0;end
        else begin
            divider<=divider+1'b1;
            if(falling) begin
                position<=position+1'b1;
                if(position==0) begin lrck<=0;data<=0;end
                else if(position==32) begin lrck<=1;data<=0;end
                else if(position>=1&&position<=16) data<=held[16-position[4:0]];
                else data<=0;
            end
        end
    end
    always @(posedge clk) begin
        if(clock_reset||stream_reset) begin primed<=0;fault<=0;held<=0;heartbeat<=0;frames<=0;end
        else begin
            if(!primed&&level>=16&&!fault) primed<=1;
            if(boundary) begin
                heartbeat<=!heartbeat;frames<=frames+1'b1;
                if(primed&&!fault) begin
                    if(!sample_valid) begin fault<=1;primed<=0;held<=0;end
                    else held<=audible ? sample : 16'd0;
                end else held<=0;
            end
        end
    end
endmodule
