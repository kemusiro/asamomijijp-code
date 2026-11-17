// SPDX-License-Identifier: GPL-3.0-or-later
// Asynchronous assertion, two-clock synchronous release in each domain.
module reset_sync(input clk, input async_n, output reset_n);
    (* async_reg = "true" *) reg [1:0] pipe;
    always @(posedge clk or negedge async_n)
        if (!async_n) pipe <= 0;
        else pipe <= {pipe[0], 1'b1};
    assign reset_n = pipe[1];
endmodule
