// SPDX-License-Identifier: GPL-3.0-or-later
// Oversampled SPI mode 0, MSB first, <=1 MHz with a 16 MHz system clock.
// A command commits only on CS rising after exactly 64 bits and a valid CRC8.
module spi_command(
    input clk, reset_n, input cs_n, sck, mosi, output miso,
    input [55:0] status_payload,
    output reg [63:0] command, output reg command_valid, frame_error
);
    (* async_reg="true", keep = 1 *) reg [1:0] cs_sync, sck_sync, mosi_sync;
    reg cs_last, sck_last;
    reg [6:0] bits;
    reg overrun;
    reg [63:0] rx, tx;
    reg [7:0] crc;
    function [7:0] crc_byte;
        input [7:0] previous, data;
        reg [7:0] c;
        integer i;
        begin
            c=previous^data;
            for(i=0;i<8;i=i+1) c=c[7] ? (c<<1)^8'h07 : c<<1;
            crc_byte=c;
        end
    endfunction
    function [7:0] status_crc;
        input [55:0] payload;
        reg [7:0] c;
        integer i;
        begin
            c=0;
            for(i=6;i>=0;i=i-1) c=crc_byte(c,payload[i*8+:8]);
            status_crc=c;
        end
    endfunction
    assign miso = cs_n ? 1'bz : tx[63];
    always @(posedge clk or negedge reset_n)
        if(!reset_n) begin
            cs_sync<=3; sck_sync<=0; mosi_sync<=0;
            cs_last<=1; sck_last<=0; bits<=0; overrun<=0;
            rx<=0; tx<=0; crc<=0; command<=0; command_valid<=0; frame_error<=0;
        end else begin
            cs_sync<={cs_sync[0],cs_n}; sck_sync<={sck_sync[0],sck};
            mosi_sync<={mosi_sync[0],mosi}; cs_last<=cs_sync[1]; sck_last<=sck_sync[1];
            command_valid<=0; frame_error<=0;
            if(cs_last && !cs_sync[1]) begin
                bits<=0; overrun<=0; rx<=0; crc<=0;
                tx<={status_payload,status_crc(status_payload)};
            end else if(!cs_last && cs_sync[1]) begin
                if(bits==64 && !overrun && crc==rx[7:0]) begin
                    command<=rx; command_valid<=1;
                end else frame_error<=1;
            end else if(!cs_sync[1]) begin
                if(!sck_last && sck_sync[1]) begin
                    if(bits<64) begin
                        rx<={rx[62:0],mosi_sync[1]}; bits<=bits+1'b1;
                        if(bits[2:0]==7 && bits<56)
                            crc<=crc_byte(crc,{rx[6:0],mosi_sync[1]});
                    end else overrun<=1;
                end
                if(sck_last && !sck_sync[1]) tx<={tx[62:0],1'b0};
            end
        end
endmodule
