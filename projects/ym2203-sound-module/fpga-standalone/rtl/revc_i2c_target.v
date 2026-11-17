// SPDX-License-Identifier: MIT
// Single-controller 100 kHz I2C target, 7-bit address 0x42. Open-drain outputs.
// clock >= 16 MHz; input synchronizers plus three-sample deglitching.
module revc_i2c_target (
    input wire clk, reset,
    input wire scl_in, sda_in,
    output reg scl_low, sda_low,
    output reg write_start, write_valid, write_end,
    output reg [7:0] write_data,
    output wire status_request,
    input wire status_busy, status_valid,
    output reg [7:0] status_address,
    input wire [7:0] status_data
);
    (* async_reg = "true", keep = 1 *) reg scl_meta, scl_sync, sda_meta, sda_sync;
    reg [2:0] scl_samples, sda_samples;
    reg scl, sda, scl_prior, sda_prior;
    wire rise = scl && !scl_prior;
    wire fall = !scl && scl_prior;
    wire start = scl && scl_prior && !sda && sda_prior;
    wire stop = scl && scl_prior && sda && !sda_prior;
    localparam ADDRESS = 3'd0, ADDRESS_ACK = 3'd1, WRITE = 3'd2, WRITE_ACK = 3'd3,
               READ_WAIT = 3'd4, READ = 3'd5, READ_ACK = 3'd6, IGNORE = 3'd7;
    reg [2:0] state, bit_count;
    reg [1:0] ack_phase;
    reg [6:0] shift, tx;
    reg addressed, read_mode, nack, first_byte, snapshot_started;
    wire [7:0] incoming = {shift,sda};
    assign status_request = state == READ_WAIT && first_byte && !snapshot_started;
    always @(posedge clk) begin
        if (reset) begin
            scl_meta <= 1; scl_sync <= 1; sda_meta <= 1; sda_sync <= 1;
            scl_samples <= 7; sda_samples <= 7;
            scl <= 1; sda <= 1; scl_prior <= 1; sda_prior <= 1;
        end else begin
            scl_meta <= scl_in; scl_sync <= scl_meta;
            sda_meta <= sda_in; sda_sync <= sda_meta;
            scl_samples <= {scl_samples[1:0],scl_sync};
            sda_samples <= {sda_samples[1:0],sda_sync};
            if (&scl_samples) scl <= 1;
            else if (~|scl_samples) scl <= 0;
            if (&sda_samples) sda <= 1;
            else if (~|sda_samples) sda <= 0;
            scl_prior <= scl; sda_prior <= sda;
        end
    end
    always @(posedge clk) begin
        if (reset) begin
            state <= IGNORE; scl_low <= 0; sda_low <= 0;
            write_start <= 0; write_valid <= 0; write_end <= 0; write_data <= 0;
            status_address <= 0; bit_count <= 0; ack_phase <= 0; shift <= 0; tx <= 0;
            addressed <= 0; read_mode <= 0; nack <= 0; first_byte <= 1; snapshot_started <= 0;
        end else begin
            write_start <= 0; write_valid <= 0; write_end <= 0;
            if (stop) begin
                if (addressed && !read_mode) write_end <= 1;
                addressed <= 0; state <= IGNORE; sda_low <= 0; scl_low <= 0;
            end else if (start) begin
                // Repeated-start writes are outside v2's contract; drop the
                // preceding address phase without publishing an unfinished write.
                state <= ADDRESS; shift <= 0; bit_count <= 0; addressed <= 0;
                sda_low <= 0; scl_low <= 0;
            end else begin
                case (state)
                    ADDRESS: if (rise) begin
                        shift <= incoming[6:0];
                        if (bit_count == 7) begin
                            addressed <= incoming[7:1] == 7'h42;
                            read_mode <= incoming[0]; state <= ADDRESS_ACK; ack_phase <= 0;
                        end else bit_count <= bit_count + 1'b1;
                    end
                    ADDRESS_ACK: begin
                        if (fall && ack_phase == 0) begin sda_low <= addressed; ack_phase <= 1; end
                        if (rise && ack_phase == 1) ack_phase <= 2;
                        if (fall && ack_phase == 2) begin
                            sda_low <= 0; bit_count <= 0;
                            if (!addressed) state <= IGNORE;
                            else if (!read_mode) begin write_start <= 1; state <= WRITE; end
                            else begin
                                state <= READ_WAIT; first_byte <= 1;
                                snapshot_started <= 0; status_address <= 0; scl_low <= 1;
                            end
                        end
                    end
                    WRITE: if (rise) begin
                        shift <= incoming[6:0];
                        if (bit_count == 7) begin
                            write_data <= incoming; write_valid <= 1; state <= WRITE_ACK; ack_phase <= 0;
                        end else bit_count <= bit_count + 1'b1;
                    end
                    WRITE_ACK: begin
                        if (fall && ack_phase == 0) begin sda_low <= 1; ack_phase <= 1; end
                        if (rise && ack_phase == 1) ack_phase <= 2;
                        if (fall && ack_phase == 2) begin sda_low <= 0; bit_count <= 0; state <= WRITE; end
                    end
                    READ_WAIT: begin
                        if (first_byte && !snapshot_started) begin
                            if (status_busy) snapshot_started <= 1;
                        end else if ((!first_byte || !status_busy) && status_valid) begin
                            tx <= status_data[6:0]; sda_low <= !status_data[7]; scl_low <= 0;
                            state <= READ; bit_count <= 0;
                        end
                    end
                    READ: begin
                        if (rise) begin
                            if (bit_count == 7) begin state <= READ_ACK; ack_phase <= 0; end
                            else bit_count <= bit_count + 1'b1;
                        end
                        if (fall) begin tx <= {tx[5:0],1'b1}; sda_low <= !tx[6]; end
                    end
                    READ_ACK: begin
                        if (fall && ack_phase == 0) begin sda_low <= 0; ack_phase <= 1; end
                        if (rise && ack_phase == 1) begin nack <= sda; ack_phase <= 2; end
                        if (fall && ack_phase == 2) begin
                            if (nack) begin state <= IGNORE; sda_low <= 0; end
                            else begin
                                if (status_address < 64) status_address <= status_address + 1'b1;
                                first_byte <= 0; state <= READ_WAIT; scl_low <= 1;
                            end
                        end
                    end
                    default: begin end
                endcase
            end
        end
    end
endmodule
