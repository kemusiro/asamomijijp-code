// SPDX-License-Identifier: MIT
// USB full-speed CDC ACM + MIDI 1.0. Packet staging is committed only after a
// validated SIE success and receive EOP. USB-local resets do not reset I2C/audio.
module revc_usb_composite #(
    parameter [15:0] VID=0,PID=0,
    parameter [63:0] SERIAL=0
)(
    input wire clk,reset,permit,usb_vbus,dp_in,dn_in,
    output wire dp_out,dn_out,tx_enable,pullup_enable,
    output wire configured,online,suspended,
    output wire dtr,
    input wire midi_blocked,flush_midi,
    output reg [31:0] midi_packet,
    output wire midi_valid,midi_tag_blocked,
    input wire midi_ready,
    output reg malformed_midi,
    output wire [7:0] cdc_rx_data,
    output wire cdc_rx_valid,
    input wire cdc_rx_ready,
    input wire [7:0] cdc_tx_data,
    input wire cdc_tx_valid,
    output wire cdc_tx_ready,
    output wire session_clear,
    output reg [31:0] rejected_packets
);
    localparam ID_VALID=VID!=0&&PID!=0;
    (* async_reg="true",keep=1 *) reg [1:0] rx_meta,rx_sync;
    (* async_reg="true",keep=1 *) reg vbus_meta,vbus_sync;
    wire se0=rx_sync==0,se1=rx_sync==3,j=rx_sync==2;
    reg [7:0] se0_age;
    reg eop_owned,eop_valid;
    reg [2:0] j_age;
    reg [17:0] sof_age;
    reg [10:0] last_sof;
    reg sof_seen;
    wire phy_tx,phy_j,phy_se0,phy_rst,phy_start,phy_sof;
    wire [10:0] phy_frame;
    wire [3:0] ep;
    wire phy_dir,phy_setup,phy_active,phy_strobe,phy_success;
    wire [7:0] phy_data,send_data;
    wire send_valid,toggle;
    wire [1:0] handshake;
    wire bus_reset=se0_age>=120;
    wire local_reset;
    revc_domain_reset usb_domain(.clk(clk),.async_reset(reset||!permit||!vbus_sync||!ID_VALID||bus_reset),.reset(local_reset));
    wire bad_eop=!se0&&se0_age!=0&&se0_age<7&&eop_owned;
    reg [6:0] capture_count,tx_count;
    reg capture_blocked,packet_pending;
    reg [3:0] pending_ep;
    reg pending_dir,pending_setup;
    reg [6:0] pending_length;
    reg [7:0] capture[0:63];
    wire too_long=phy_active&&!phy_dir&&phy_strobe&&(capture_count>=64||(phy_setup&&capture_count>=8));
    wire receive_error=(se1&&!phy_tx)||bad_eop||too_long;
    wire commit=packet_pending&&eop_valid&&j_age>=4&&!receive_error&&!local_reset;
    wire [6:0] address;
    wire [1:0] ctrl_in_hs,ctrl_out_hs;
    wire ctrl_in_toggle,ctrl_out_toggle;
    wire [7:0] ctrl_data;
    wire [6:0] ctrl_length;
    wire [4:0] halted,clear_endpoint;
    wire configuration_event,line_event;
    wire [55:0] line_coding;
    wire [31:0] control_stalls;
    wire ctrl_setup=commit&&pending_ep==0&&!pending_dir&&pending_setup;
    wire ctrl_out=commit&&pending_ep==0&&!pending_dir&&!pending_setup;
    wire ctrl_in=commit&&pending_ep==0&&pending_dir;
    wire [63:0] setup_bytes={capture[7],capture[6],capture[5],capture[4],capture[3],capture[2],capture[1],capture[0]};
    revc_usb_control #(.VID(VID),.PID(PID),.SERIAL(SERIAL)) control (
        .clk(clk),.reset(local_reset),.setup_valid(ctrl_setup),.setup_packet(setup_bytes),
        .out_success(ctrl_out),.in_success(ctrl_in),.out_length(pending_length),.in_offset(tx_count),.out_data(setup_bytes[55:0]),
        .in_data(ctrl_data),.in_length(ctrl_length),.in_handshake(ctrl_in_hs),.out_handshake(ctrl_out_hs),
        .in_toggle(ctrl_in_toggle),.out_toggle(ctrl_out_toggle),.address(address),.configured(configured),.dtr(dtr),
        .configuration_event(configuration_event),.line_event(line_event),.halted(halted),.clear_endpoint(clear_endpoint),
        .line_coding(line_coding),.stalls(control_stalls));
    usb phy(.rst_n(!local_reset),.clk_48(clk),.rx_j(rx_sync[1]),.rx_se0(se0),.rx_error(receive_error),
        .tx_en(phy_tx),.tx_j(phy_j),.tx_se0(phy_se0),.usb_address(address),.usb_rst(phy_rst),
        .transaction_start(phy_start),.sof_tick(phy_sof),.sof_number(phy_frame),
        .transaction_active(phy_active),.endpoint(ep),.direction_in(phy_dir),.setup(phy_setup),.data_toggle(toggle),
        .handshake(handshake),.data_out(phy_data),.data_in(send_data),.data_in_valid(send_valid),.data_strobe(phy_strobe),.success(phy_success));
    assign tx_enable=phy_tx&&usb_vbus&&permit&&!reset&&ID_VALID;
    assign dp_out=!phy_se0&&phy_j;
    assign dn_out=!phy_se0&&!phy_j;
    assign pullup_enable=usb_vbus&&vbus_sync&&permit&&!reset&&ID_VALID;
    assign suspended=configured&&sof_age>=144000;
    assign online=configured&&!suspended&&!local_reset;
    assign session_clear=local_reset||configuration_event||clear_endpoint[3]||clear_endpoint[4];
    always @(posedge clk) begin
        if(reset) begin rx_meta<=2;rx_sync<=2;vbus_meta<=0;vbus_sync<=0;end
        else begin rx_meta<={dp_in,dn_in};rx_sync<=rx_meta;vbus_meta<=usb_vbus;vbus_sync<=vbus_meta;end
        if(reset||!permit||!vbus_sync) begin se0_age<=0;j_age<=0;eop_owned<=0;eop_valid<=0;end
        else begin
            if(se0) begin
                if(se0_age==0) eop_owned<=!phy_tx;
                if(se0_age<255) se0_age<=se0_age+1'b1;
            end else begin
                if(se0_age>=7&&eop_owned) eop_valid<=1;
                se0_age<=0;
            end
            if(j&&!phy_tx) begin if(j_age<7) j_age<=j_age+1'b1;end else j_age<=0;
            if(phy_start||commit||receive_error||bus_reset) eop_valid<=0;
        end
        if(local_reset||configuration_event) begin sof_age<=0;last_sof<=0;sof_seen<=0;end
        else if(phy_sof&&(!sof_seen||phy_frame!=last_sof)) begin sof_age<=0;last_sof<=phy_frame;sof_seen<=1;end
        else if(sof_age<144000) sof_age<=sof_age+1'b1;
    end
    reg cdc_out_full,midi_out_full,cdc_in_full;
    reg [6:0] cdc_out_length,cdc_out_pos,midi_out_length,midi_out_pos,cdc_fill,cdc_length;
    reg [7:0] cdc_out[0:63],midi_out[0:63],cdc_in[0:63];
    reg midi_blocked_latch,cdc_need_zlp,midi_word_valid;
    reg [4:0] toggles;
    reg notify_pending,notify_dirty,notify_snapshot;
    reg [3:0] notify_position;
    wire [6:0] notify_length=notify_position==0 ? 7'd8 : 7'd2;
    function [7:0] notification;
        input [6:0] n;
        begin case(n)
            0:notification=8'ha1;1:notification=8'h20;6:notification=2;
            8:notification=notify_snapshot?8'd3:8'd0;default:notification=0;
        endcase end
    endfunction
    assign cdc_rx_valid=cdc_out_full&&configured&&dtr&&online;
    assign cdc_rx_data=cdc_out[cdc_out_pos[5:0]];
    assign cdc_tx_ready=!cdc_in_full&&configured&&dtr&&online;
    assign midi_valid=midi_word_valid&&online;
    wire [31:0] buffered_packet={midi_out[6'(midi_out_pos+3)],midi_out[6'(midi_out_pos+2)],midi_out[6'(midi_out_pos+1)],midi_out[midi_out_pos[5:0]]};
    assign midi_tag_blocked=midi_blocked_latch;
    assign toggle=ep==0 ? (phy_setup&&!phy_dir ? 1'b0 : phy_dir ? ctrl_in_toggle : ctrl_out_toggle) :
        ep==1 ? toggles[0] : ep==2 ? (phy_dir?toggles[2]:toggles[1]) : phy_dir ? toggles[4] : toggles[3];
    assign handshake=ep!=0&&phy_setup&&!phy_dir ? 2'd3 : ep==0 ? (phy_setup&&!phy_dir ? 2'd0 : phy_dir ? ctrl_in_hs : ctrl_out_hs) :
        !configured ? 2'd3 : ep==1&&phy_dir ? (halted[0]?2'd3:notify_pending?2'd0:2'd2) :
        ep==2 ? (phy_dir?(halted[2]?2'd3:cdc_in_full&&online?2'd0:2'd2):(halted[1]?2'd3:!cdc_out_full&&online?2'd0:2'd2)) :
        ep==3 ? (phy_dir?(halted[4]?2'd3:2'd2):(halted[3]?2'd3:!midi_out_full&&online?2'd0:2'd2)) : 2'd3;
    wire [6:0] send_length=ep==0 ? ctrl_length : ep==1 ? notify_length : ep==2 ? cdc_length : 7'd0;
    assign send_valid=tx_count<send_length;
    assign send_data=ep==0 ? ctrl_data : ep==1 ? notification({3'd0,notify_position}+tx_count) : cdc_in[tx_count[5:0]];
    integer i;
    always @(posedge clk) begin
        if(local_reset) begin
            capture_count<=0;tx_count<=0;capture_blocked<=0;packet_pending<=0;pending_ep<=0;pending_dir<=0;pending_setup<=0;pending_length<=0;
            cdc_out_full<=0;midi_out_full<=0;cdc_in_full<=0;cdc_out_length<=0;cdc_out_pos<=0;
            midi_out_length<=0;midi_out_pos<=0;cdc_fill<=0;cdc_length<=0;midi_blocked_latch<=0;cdc_need_zlp<=0;toggles<=0;
            notify_pending<=0;notify_dirty<=0;notify_snapshot<=0;notify_position<=0;malformed_midi<=0;rejected_packets<=0;midi_word_valid<=0;midi_packet<=0;
        end else begin
            malformed_midi<=0;
            if(phy_start) begin capture_count<=0;tx_count<=0;capture_blocked<=midi_blocked;packet_pending<=0;end
            if(phy_active&&phy_strobe) begin
                if(phy_dir) begin if(tx_count<127) tx_count<=tx_count+1'b1;end
                else if(capture_count<64) begin capture[capture_count[5:0]]<=phy_data;capture_count<=capture_count+1'b1;end
            end
            if(phy_success) begin
                packet_pending<=1;pending_ep<=ep;pending_dir<=phy_dir;pending_setup<=phy_setup;
                pending_length<=phy_dir ? send_length : capture_count;
            end
            if(receive_error) begin
                packet_pending<=0;rejected_packets<=rejected_packets+1'b1;
                if(ep==3&&!phy_dir) malformed_midi<=1;
            end
            if(commit) begin
                packet_pending<=0;
                if(pending_ep==2) begin
                    if(pending_dir) begin
                        toggles[2]<=!toggles[2];cdc_in_full<=0;cdc_fill<=0;cdc_need_zlp<=pending_length==64;
                    end else begin
                        toggles[1]<=!toggles[1];cdc_out_full<=pending_length!=0;cdc_out_length<=pending_length;cdc_out_pos<=0;
                        for(i=0;i<64;i=i+1) if(i<32'(pending_length)) cdc_out[i]<=capture[i];
                    end
                end else if(pending_ep==3&&!pending_dir) begin
                    toggles[3]<=!toggles[3];midi_out_pos<=0;
                    if(pending_length[1:0]!=0) begin malformed_midi<=1;rejected_packets<=rejected_packets+1'b1;end
                    else begin
                        midi_out_full<=pending_length!=0;midi_out_length<=pending_length;midi_blocked_latch<=capture_blocked||midi_blocked;
                        for(i=0;i<64;i=i+1) if(i<32'(pending_length)) midi_out[i]<=capture[i];
                    end
                end else if(pending_ep==1&&pending_dir) begin
                    toggles[0]<=!toggles[0];
                    if(notify_position==0) notify_position<=8;
                    else begin notify_position<=0;notify_pending<=notify_dirty;notify_dirty<=0;notify_snapshot<=dtr;end
                end
            end
            if(cdc_rx_valid&&cdc_rx_ready) begin
                if(cdc_out_pos+1'b1==cdc_out_length) begin cdc_out_full<=0;cdc_out_pos<=0;end else cdc_out_pos<=cdc_out_pos+1'b1;
            end
            // Register the four-byte RAM/mux result before MIDI decode/pitch
            // validity/revision updates. The packet and tag remain immutable
            // while the consumer applies backpressure.
            if(midi_out_full&&!midi_word_valid&&online) begin midi_packet<=buffered_packet;midi_word_valid<=1;end
            if(midi_valid&&midi_ready) begin
                midi_word_valid<=0;
                if(midi_out_pos+7'd4==midi_out_length) begin midi_out_full<=0;midi_out_pos<=0;end else midi_out_pos<=midi_out_pos+7'd4;
            end
            if(cdc_tx_valid&&cdc_tx_ready) begin
                cdc_in[cdc_fill[5:0]]<=cdc_tx_data;cdc_fill<=cdc_fill+1'b1;cdc_need_zlp<=0;
                if(cdc_fill==63) begin cdc_in_full<=1;cdc_length<=64;end
            end else if(!cdc_in_full&&!cdc_tx_valid&&(cdc_fill!=0||cdc_need_zlp)) begin
                cdc_in_full<=1;cdc_length<=cdc_fill;cdc_need_zlp<=0;
            end
            if(line_event) begin
                if(!notify_pending) begin notify_pending<=1;notify_snapshot<=dtr;notify_position<=0;end else notify_dirty<=1;
            end
            if(configuration_event) begin
                toggles<=0;cdc_out_full<=0;midi_out_full<=0;midi_word_valid<=0;cdc_in_full<=0;cdc_fill<=0;cdc_need_zlp<=0;
                notify_pending<=0;notify_dirty<=0;notify_position<=0;
            end else begin
                if(clear_endpoint[0]) begin toggles[0]<=0;notify_pending<=0;notify_dirty<=0;notify_position<=0;end
                if(clear_endpoint[1]) begin toggles[1]<=0;cdc_out_full<=0;end
                if(clear_endpoint[2]) begin toggles[2]<=0;cdc_in_full<=0;cdc_fill<=0;cdc_need_zlp<=0;end
                if(clear_endpoint[3]||clear_endpoint[4]) begin toggles[3]<=0;toggles[4]<=0;midi_out_full<=0;midi_word_valid<=0;end
            end
            if(flush_midi||!online) begin midi_out_full<=0;midi_word_valid<=0;capture_blocked<=1;end
            if(!online||!dtr) begin cdc_out_full<=0;cdc_in_full<=0;cdc_fill<=0;cdc_need_zlp<=0;end
        end
    end
    wire unused_monitors=&{line_coding,control_stalls,phy_rst};
endmodule
