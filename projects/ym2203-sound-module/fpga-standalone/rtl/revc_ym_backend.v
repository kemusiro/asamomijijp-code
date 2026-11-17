// SPDX-License-Identifier: MIT
// External YM bus supervisor and audio adapter for the unchanged v2 session ports.
module revc_ym_backend #(
    parameter integer CONTROL_HZ=48000000,
    parameter integer GAIN_EIGHTHS=8,
    parameter integer DYNAMIC_CLOCK=0
) (
    input wire clk,audio_clk,reset,permit,clock_good,
    input wire [63:0] now_us,
    input wire [23:0] ym_frequency,
    input wire prepare_request,silence_request,gate_request,
    output reg prepare_done,silence_done,
    output reg [3:0] prepare_result,
    output wire audio_ok,
    input wire event_valid,
    input wire [7:0] event_register,event_value,
    output wire event_ready,event_error,
    input wire [7:0] ym_data_in,
    output wire [7:0] ym_data_out,
    output wire ym_data_oe,translator_dir,translator_oe_n,
    output wire ym_a0,ym_cs_n,ym_wr_n,ym_rd_n,ym_reset_n,arm_request,dac_allow,line_allow,
    input wire fm_sd,fm_clk,fm_sh,
    output wire i2s_bclk,i2s_lrck,i2s_data,
    output wire [31:0] rx_frames,pcm_samples,clipped,rejections,bus_completed,busy_polls,
    output wire [6:0] pcm_level,native_level,
    output wire [23:0] raw_word,
    output wire [31:0] tx_frames,
    output wire [4:0] backend_state,
    output wire audio_fault,
    output wire [15:0] pcm_probe,
    output wire pcm_probe_valid
);
    localparam WAIT_CLOCK=5'd0,ARM=5'd1,RESET_LOW=5'd2,RELEASE=5'd3,
        INIT_SEND=5'd4,INIT_WAIT=5'd5,PRIME=5'd6,READY=5'd7,
        EVENT_SEND=5'd8,EVENT_WAIT=5'd9,CANCEL_WAIT=5'd10,
        CLEAN_SEND=5'd11,CLEAN_WAIT=5'd12,FAULT=5'd13;
    reg [4:0] state;
    reg [63:0] entered,heartbeat_at;
    reg [3:0] index;
    reg [7:0] pending_reg,pending_value;
    reg for_prepare,for_silence,served_prepare,served_silence,boot_done;
    reg audio_stalled;
    reg pipeline_reset,arm_state,release_state,run_eligible,gate_open;
    wire control_reset,audio_reset,stream_reset;
    wire bus_reset=control_reset||pipeline_reset;
    wire bus_ready,bus_reply,bus_error,bus_aborted;
    wire [7:0] bus_read_data;
    wire bus_cancel=state==CANCEL_WAIT||((state==EVENT_SEND||state==EVENT_WAIT)&&
                                      (silence_request||prepare_request));
    wire initializing=state==INIT_SEND;
    wire cleaning=state==CLEAN_SEND;
    wire normal=state==EVENT_SEND&&!silence_request&&!prepare_request;
    wire bus_request=initializing||cleaning||normal;
    wire [3:0] setup_index=cleaning ? index+4'd2 : index;
    wire [7:0] setup_reg=setup_index==0 ? 8'h27 : setup_index==1 ? 8'h07 :
                               setup_index[0] ? 8'd8+{6'd0,setup_index[2:1]}-8'd1 : 8'h28;
    wire [7:0] setup_value=setup_index==1 ? 8'h3f :
                                setup_index>=2&&!setup_index[0] ? {6'd0,setup_index[2:1]}-8'd1 : 8'd0;
    wire [7:0] bus_reg=normal ? pending_reg : setup_reg;
    wire [7:0] bus_value=normal ? pending_value : setup_value;
    wire cleanup_busy=state==CANCEL_WAIT||state==CLEAN_SEND||state==CLEAN_WAIT;
    wire response_take=state==INIT_WAIT||state==CLEAN_WAIT||state==CANCEL_WAIT||
                            (state==EVENT_WAIT&&(event_valid||bus_error||silence_request||prepare_request));
    wire path_healthy,path_fault,audio_heartbeat;
    (* async_reg="true",keep=1 *) reg healthy_meta,healthy_sync,hb_meta,hb_sync,fault_meta,fault_sync;
    (* async_reg="true",keep=1 *) reg audible_meta,audible_sync,sys_meta,sys_sync;
    reg hb_seen,sys_seen,sys_stalled;
    // Bundled configuration: source holds frequency stable before clock_good
    // and throughout operation. Capture only while stream reset is asserted.
    (* async_reg="true",keep=1 *) reg [23:0] rate_meta,rate_sync;
    always @(posedge audio_clk) begin
        if(audio_reset) begin rate_meta<=4000000;rate_sync<=4000000;end
        else if(stream_reset) begin rate_meta<=ym_frequency;rate_sync<=rate_meta;end
    end
    reg [16:0] sys_age;
    wire running_state=state==READY||state==EVENT_SEND||state==EVENT_WAIT;
    wire raw_fault=path_fault||sys_stalled;
    wire allow=gate_open&&!silence_request&&!prepare_request&&
               !raw_fault&&permit&&clock_good&&!reset;
    assign backend_state=state;
    // Raw sticky fault asserts the external inhibit immediately. All control
    // decisions and diagnostics consume its two-flop synchronized copy.
    assign audio_fault=raw_fault;
    assign audio_ok=healthy_sync&&boot_done&&!audio_stalled&&!fault_sync&&clock_good&&permit&&!control_reset;
    assign arm_request=arm_state&&clock_good&&permit&&!reset;
    assign ym_reset_n=arm_request&&release_state&&!raw_fault;
    assign dac_allow=allow;
    assign line_allow=allow;
    assign event_ready=state==EVENT_WAIT&&bus_reply&&!bus_error&&!bus_aborted&&event_valid&&
                       event_register==pending_reg&&event_value==pending_value&&
                       !silence_request&&!prepare_request&&audio_ok&&!fault_sync;
    assign event_error=state==EVENT_WAIT&&bus_reply&&bus_error;
    revc_domain_reset cr(.clk(clk),.async_reset(reset||!permit),.reset(control_reset));
    revc_domain_reset ar(.clk(audio_clk),.async_reset(reset||!permit),.reset(audio_reset));
    revc_domain_reset sr(.clk(audio_clk),.async_reset(reset||!permit||pipeline_reset),.reset(stream_reset));
    always @(posedge clk) begin
        if(control_reset) begin pipeline_reset<=1;arm_state<=0;release_state<=0;run_eligible<=0;gate_open<=0;end
        else begin
            pipeline_reset<=state==WAIT_CLOCK||state==ARM||state==RESET_LOW||state==FAULT||!clock_good;
            arm_state<=state!=WAIT_CLOCK&&state!=FAULT&&clock_good;
            release_state<=state!=WAIT_CLOCK&&state!=ARM&&state!=RESET_LOW&&state!=FAULT&&clock_good;
            run_eligible<=running_state;
            gate_open<=gate_request&&run_eligible&&!silence_request&&!prepare_request&&audio_ok&&!fault_sync;
        end
    end
    revc_ym_bus #(.CLOCK_HZ(CONTROL_HZ)) bus (
        .clk(clk),.reset(bus_reset),.cancel(bus_cancel),.request_valid(bus_request),.request_read(1'b0),
        .request_register(bus_reg),.request_value(bus_value),.request_ready(bus_ready),
        .response_valid(bus_reply),.response_error(bus_error),.response_aborted(bus_aborted),
        .response_data(bus_read_data),.response_ready(response_take),.ym_data_in(ym_data_in),
        .ym_data_out(ym_data_out),.ym_data_oe(ym_data_oe),.translator_dir(translator_dir),
        .translator_oe_n(translator_oe_n),.ym_a0(ym_a0),.ym_cs_n(ym_cs_n),.ym_wr_n(ym_wr_n),.ym_rd_n(ym_rd_n),
        .completed(bus_completed),.busy_polls(busy_polls));
    revc_audio_path #(.GAIN_EIGHTHS(GAIN_EIGHTHS),.DYNAMIC_CLOCK(DYNAMIC_CLOCK)) audio (
        .clk(audio_clk),.clock_reset(audio_reset),.stream_reset(stream_reset),.audible(audible_sync),
        .ym_frequency(rate_sync),.sd_in(fm_sd),.bitclk_in(fm_clk),.sh_in(fm_sh),.bclk(i2s_bclk),.lrck(i2s_lrck),.data(i2s_data),
        .healthy(path_healthy),.heartbeat(audio_heartbeat),.fault(path_fault),
        .rx_frames(rx_frames),.pcm_samples(pcm_samples),.clipped(clipped),.rejections(rejections),
        .pcm_level(pcm_level),.native_level(native_level),.raw_word(raw_word),.tx_frames(tx_frames),
        .pcm_probe(pcm_probe),.pcm_probe_valid(pcm_probe_valid));
    always @(posedge audio_clk) begin
        if(audio_reset) begin audible_meta<=0;audible_sync<=0;sys_meta<=0;sys_sync<=0;end
        else begin audible_meta<=allow;audible_sync<=audible_meta;sys_meta<=now_us[8];sys_sync<=sys_meta;end
        if(stream_reset) begin sys_seen<=0;sys_age<=0;sys_stalled<=0;end
        else if(sys_sync!=sys_seen) begin sys_seen<=sys_sync;sys_age<=0;end
        else if(sys_age<98304) sys_age<=sys_age+1'b1;
        else sys_stalled<=1;
    end
    always @(posedge clk) begin
        if(control_reset) begin healthy_meta<=0;healthy_sync<=0;hb_meta<=0;hb_sync<=0;fault_meta<=0;fault_sync<=0;end
        else begin healthy_meta<=path_healthy&&!sys_stalled;healthy_sync<=healthy_meta;hb_meta<=audio_heartbeat;hb_sync<=hb_meta;fault_meta<=raw_fault;fault_sync<=fault_meta;end
        if(control_reset||pipeline_reset) begin hb_seen<=0;heartbeat_at<=now_us;audio_stalled<=0;end
        else if(hb_sync!=hb_seen) begin hb_seen<=hb_sync;heartbeat_at<=now_us;end
        else if(healthy_sync&&now_us-heartbeat_at>=2000) audio_stalled<=1;
    end
    always @(posedge clk) begin
        if(control_reset) begin
            state<=WAIT_CLOCK;entered<=0;index<=0;pending_reg<=0;pending_value<=0;
            prepare_done<=0;silence_done<=0;prepare_result<=0;
            for_prepare<=0;for_silence<=0;served_prepare<=0;served_silence<=0;boot_done<=0;
        end else begin
            if(!prepare_request) begin prepare_done<=0;served_prepare<=0;end
            if(!silence_request) begin silence_done<=0;served_silence<=0;end
            if(!clock_good) begin state<=WAIT_CLOCK;boot_done<=0;entered<=now_us;end
            else case(state)
                WAIT_CLOCK: begin state<=ARM;entered<=now_us;for_prepare<=0;for_silence<=0;end
                ARM: if(now_us-entered>=2000) begin state<=RESET_LOW;entered<=now_us;end
                RESET_LOW: if(now_us-entered>=2000) begin state<=RELEASE;entered<=now_us;end
                RELEASE: if(now_us-entered>=2000) begin state<=INIT_SEND;index<=0;end
                INIT_SEND: if(bus_ready) state<=INIT_WAIT;
                INIT_WAIT: if(bus_reply) begin
                    if(bus_error) begin state<=FAULT;if(for_prepare) begin prepare_done<=1;prepare_result<=12;served_prepare<=1;end end
                    else if(index==7) begin state<=PRIME;entered<=now_us;end
                    else begin index<=index+1'b1;state<=INIT_SEND;end
                end
                PRIME: if(healthy_sync&&!audio_stalled&&!fault_sync) begin
                    boot_done<=1;state<=READY;
                    if(for_prepare) begin prepare_done<=1;prepare_result<=0;served_prepare<=1;end
                    if(for_silence) begin silence_done<=1;served_silence<=1;end
                    for_prepare<=0;for_silence<=0;
                end else if(now_us-entered>=50000) begin
                    state<=FAULT;if(for_prepare) begin prepare_done<=1;prepare_result<=12;served_prepare<=1;end
                end
                READY: begin
                    if(silence_request&&!served_silence) begin
                        for_silence<=1;for_prepare<=0;index<=0;state<=CLEAN_SEND;
                    end else if(prepare_request&&!served_prepare) begin
                        for_prepare<=1;for_silence<=0;prepare_result<=0;state<=RESET_LOW;entered<=now_us;
                    end else if(event_valid) begin pending_reg<=event_register;pending_value<=event_value;state<=EVENT_SEND;end
                    else if(fault_sync||audio_stalled) state<=FAULT;
                end
                EVENT_SEND,EVENT_WAIT: begin
                    if(silence_request||prepare_request) begin
                        for_silence<=silence_request;for_prepare<=!silence_request&&prepare_request;state<=CANCEL_WAIT;
                    end else if(state==EVENT_SEND&&bus_ready) state<=EVENT_WAIT;
                    else if(state==EVENT_WAIT&&bus_reply) begin
                        if(bus_error) state<=FAULT;
                        else if(event_ready) state<=READY;
                    end
                end
                CANCEL_WAIT: if(bus_ready||bus_reply) begin
                    if(for_prepare) begin state<=RESET_LOW;entered<=now_us;end
                    else begin state<=CLEAN_SEND;index<=0;end
                end
                CLEAN_SEND: if(bus_ready) state<=CLEAN_WAIT;
                CLEAN_WAIT: if(bus_reply) begin
                    if(bus_error) begin state<=RESET_LOW;entered<=now_us;end
                    else if(index==5) begin silence_done<=1;served_silence<=1;for_silence<=0;state<=READY;end
                    else begin index<=index+1'b1;state<=CLEAN_SEND;end
                end
                FAULT: if(silence_request&&!served_silence) begin
                    for_silence<=1;for_prepare<=0;state<=RESET_LOW;entered<=now_us;
                end
                default:state<=WAIT_CLOCK;
            endcase
        end
    end
    // Read data remains available as a diagnostic monitor even though v2 only writes.
    wire unused_bus_data=&bus_read_data;
    wire unused_cleanup=cleanup_busy;
endmodule
