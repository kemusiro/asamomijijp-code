// SPDX-License-Identifier: MIT
module revc_domain_reset(input wire clk, async_reset, output wire reset);
    (* async_reg="true",keep=1 *) reg [1:0] release_pipe;
    always @(posedge clk or posedge async_reset)
        if(async_reset) release_pipe<=2'b11;
        else release_pipe<={release_pipe[0],1'b0};
    assign reset=release_pipe[1];
endmodule
