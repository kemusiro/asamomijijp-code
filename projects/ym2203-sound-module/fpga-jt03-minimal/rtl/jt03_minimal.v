// SPDX-License-Identifier: GPL-3.0-or-later
// Analysis prototype, not a board pinout. External clock/reset/permit assumed.
module jt03_minimal #(
    parameter LEASE_CYCLES=16000000,
    parameter AUDIO_TIMEOUT_CYCLES=32000,
    parameter EMPTY_TIMEOUT_CYCLES=16000
)(
    input synth_clk, audio_clk, reset_n, permit,
    input spi_cs_n, spi_sck, spi_mosi, output spi_miso,
    output i2s_bclk, i2s_lrck, i2s_data, output line_allow,
    output fault_out
`ifdef VERILATOR
    ,input debug_force_busy, output debug_commit, output [15:0] debug_pair, output [31:0] debug_us,
    output [7:0] debug_error, output [9:0] debug_level,
    output debug_running, debug_primed, debug_clear
`endif
);
    wire por_n=reset_n && permit;
    wire sys_reset_n, aud_reset_n;
    reset_sync rs0(synth_clk,por_n,sys_reset_n);
    reset_sync ra0(audio_clk,por_n,aud_reset_n);
    reg [6:0] flush;
    reg clear;
    wire session_n = por_n && !clear;
    wire sys_session_n, aud_session_n;
    reset_sync rs1(synth_clk,session_n,sys_session_n);
    reset_sync ra1(audio_clk,session_n,aud_session_n);
    reg running, sealed;
    reg [7:0] error_code, ack;
    reg [31:0] now_us, last_time, end_time;
    reg [3:0] us_div;
    reg [23:0] lease;
    reg [15:0] audio_timeout, empty_timeout, busy_timeout;
    reg hb_last;
    wire [63:0] cmd;
    wire cmd_valid, frame_error;
    wire [7:0] op=cmd[63:56];
    wire [31:0] command_time=cmd[39:8];
    wire pcm_primed, pcm_fault, heartbeat;
    (* async_reg="true", keep = 1 *) reg [1:0] prime_sync, bad_sync, hb_sync;
    (* async_reg="true", keep = 1 *) reg [1:0] run_sync;
    wire [9:0] event_level;
    wire [15:0] free_slots=16'd257-{6'b0,event_level};
    wire [7:0] flags={3'b0,sealed,prime_sync[1],(error_code!=0),running,(!clear && sys_session_n && error_code==0)};
    wire [55:0] status_payload={8'h4a,8'h01,flags,error_code,free_slots,ack};
    spi_command spi(synth_clk,sys_reset_n,spi_cs_n,spi_sck,spi_mosi,spi_miso,
                    status_payload,cmd,cmd_valid,frame_error);
    wire enqueue=cmd_valid && op==8'h01 && !clear && sys_session_n &&
                 error_code==0 && !sealed && cmd[55:48]!=8'h2d &&
                 cmd[55:48]!=8'h2e && cmd[55:48]!=8'h2f && command_time>=last_time;
    wire event_wready, event_valid, event_ready, bus_idle;
    wire [47:0] event_data;
    event_fifo events(synth_clk,sys_session_n,{command_time,cmd[55:40]},enqueue,
                     event_wready,event_data,event_valid,event_ready,event_level);
    wire bus_addr, bus_cs_n, bus_wr_n, committed;
    wire [7:0] bus_din, bus_status;
    wire [15:0] committed_pair;
    wire [7:0] observed_status = bus_status
`ifdef VERILATOR
        | {debug_force_busy,7'b0}
`endif
        ;
    ym_bus_writer writer(synth_clk,sys_session_n,running,now_us,event_data,event_valid,
                         event_ready,bus_idle,observed_status,bus_addr,bus_cs_n,bus_wr_n,
                         bus_din,committed,committed_pair);
    reg [1:0] cen_div;
    always @(posedge synth_clk or negedge sys_reset_n)
        if(!sys_reset_n) cen_div<=0;
        else cen_div<=cen_div+1'b1;
    wire signed [15:0] fm;
    wire [7:0] a,b,c;
    wire sample;
    revc_jt03 chip(.rst(!sys_session_n || !running),.clk(synth_clk),.cen(cen_div==0),
        .din(bus_din),.addr(bus_addr),.cs_n(bus_cs_n),.wr_n(bus_wr_n),.dout(bus_status),
        .fm_snd(fm),.psg_A(a),.psg_B(b),.psg_C(c),.snd_sample(sample));
    wire [15:0] pcm_wdata, pcm_rdata;
    wire pcm_valid, pcm_wready, pcm_rvalid, pcm_rready;
    wire [6:0] pcm_level;
    audio_bridge bridge(synth_clk,sys_session_n,running,fm,sample,a,b,c,pcm_wdata,pcm_valid);
    async_pcm_fifo pcm_fifo(synth_clk,sys_session_n,pcm_wdata,pcm_valid,pcm_wready,
        audio_clk,aud_session_n,pcm_rdata,pcm_rvalid,pcm_rready,pcm_level);
    i2s_output tx(audio_clk,aud_reset_n,aud_session_n,run_sync[1],pcm_rdata,pcm_rvalid,pcm_level,
        pcm_rready,i2s_bclk,i2s_lrck,i2s_data,pcm_primed,pcm_fault,heartbeat);
    always @(posedge audio_clk or negedge aud_session_n)
        if(!aud_session_n) run_sync<=0;
        else run_sync<={run_sync[0],running};
    always @(posedge synth_clk or negedge sys_session_n)
        if(!sys_session_n) begin prime_sync<=0; bad_sync<=0; hb_sync<=0; end
        else begin
            prime_sync<={prime_sync[0],pcm_primed};
            bad_sync<={bad_sync[0],pcm_fault}; hb_sync<={hb_sync[0],heartbeat};
        end
    // Audio-side fault closes the gate without waiting for a live synth clock.
    assign line_allow=por_n && sys_session_n && running && error_code==0 &&
                      pcm_primed && !pcm_fault && aud_session_n;
    assign fault_out=(error_code!=0) || pcm_fault;
`ifdef VERILATOR
    assign debug_commit=committed; assign debug_pair=committed_pair;
    assign debug_us=now_us; assign debug_error=error_code; assign debug_level=event_level;
    assign debug_running=running; assign debug_primed=pcm_primed; assign debug_clear=clear;
`endif
    // Fault codes: 1 framing/CRC, 2 command/state, 3 event overflow, 4 order/register,
    // 5 lease, 6 PCM overflow, 7 PCM underflow, 8 audio clock, 9 event starvation,
    // 10 unfinished deadline, 11 timeline wrap, 12 stuck BUSY. BEGIN is the only fault clear.
    task stop_with_error;
        input [7:0] code;
        begin running<=0; flush<=64; clear<=1; error_code<=code; end
    endtask
    always @(posedge synth_clk or negedge sys_reset_n)
        if(!sys_reset_n) begin
            flush<=64; clear<=1; running<=0; sealed<=0; error_code<=0; ack<=0;
            now_us<=0; last_time<=0; end_time<=0; us_div<=0;
            lease<=0; audio_timeout<=0; empty_timeout<=0; busy_timeout<=0; hb_last<=0;
        end else begin
            if(clear) begin
                if(flush==1) begin flush<=0; clear<=0; end
                else flush<=flush-1'b1;
            end
            if(running) begin
                us_div<=us_div+1'b1;
                if(us_div==15) begin
                    now_us<=now_us+1'b1;
                    if(now_us==32'hffffffff) stop_with_error(11);
                end
                lease<=lease+1'b1;
                if(lease==LEASE_CYCLES-1) stop_with_error(5);
                if(hb_sync[1]!=hb_last) begin hb_last<=hb_sync[1]; audio_timeout<=0; end
                else begin
                    audio_timeout<=audio_timeout+1'b1;
                    if(audio_timeout==AUDIO_TIMEOUT_CYCLES-1) stop_with_error(8);
                end
                if(!event_valid && event_level==0 && bus_idle && !sealed) begin
                    empty_timeout<=empty_timeout+1'b1;
                    if(empty_timeout==EMPTY_TIMEOUT_CYCLES-1) stop_with_error(9);
                end else empty_timeout<=0;
                if(event_valid && event_data[47:16]<=now_us && bus_idle && observed_status[7]) begin
                    busy_timeout<=busy_timeout+1'b1;
                    if(busy_timeout==15999) stop_with_error(12);
                end else busy_timeout<=0;
                if(pcm_valid && !pcm_wready) stop_with_error(6);
                if(bad_sync[1]) stop_with_error(7);
                if(sealed && now_us>=end_time) begin
                    if(!event_valid && event_level==0 && bus_idle) begin running<=0; flush<=64; clear<=1; end
                    else stop_with_error(10);
                end
            end
            if(frame_error) stop_with_error(1);
            if(cmd_valid) begin
                if(op==8'h10 && cmd[55:8]==0) begin
                    running<=0; flush<=64; clear<=1; sealed<=0; error_code<=0; ack<=ack+1'b1;
                    now_us<=0; last_time<=0; end_time<=0; us_div<=0;
                    lease<=0; audio_timeout<=0; empty_timeout<=0; busy_timeout<=0; hb_last<=0;
                end else if(op==8'h04 && cmd[55:8]==0) begin
                    running<=0; flush<=64; clear<=1; sealed<=0; ack<=ack+1'b1;
                end else if(op==0 && cmd[55:8]==0) begin end // status reads never renew lease
                else if(clear || !sys_session_n || error_code!=0) begin end // status exposes not-ready/fault
                else begin
                    ack<=ack+1'b1;
                    case(op)
                        8'h01: begin
                            if(!enqueue) stop_with_error(4);
                            else if(!event_wready) stop_with_error(3);
                            else begin last_time<=command_time; if(running) lease<=0; end
                        end
                        8'h02: begin
                            if(running || !event_valid || !prime_sync[1] || cmd[55:8]!=0)
                                stop_with_error(2);
                            else begin
                                running<=1; now_us<=0; us_div<=0; lease<=0;
                                audio_timeout<=0; empty_timeout<=0; hb_last<=hb_sync[1];
                            end
                        end
                        8'h03: if(cmd[55:8]!=0 || !running) stop_with_error(2); else lease<=0;
                        8'h05: begin
                            if(cmd[55:40]!=0 || sealed || command_time<last_time ||
                               (running && command_time<now_us)) stop_with_error(2);
                            else begin sealed<=1; end_time<=command_time; if(running) lease<=0; end
                        end
                        default: stop_with_error(2);
                    endcase
                end
            end
        end
endmodule
