// SPDX-License-Identifier: MIT
// Six monophonic voices, matching Rev C C's Note/CC subset and setup/pitch ROM.
// Latest desired notes coalesce; a latched register never changes while BUSY.
module revc_midi_planner #(
    parameter integer QUIET_US=200000
)(
    input wire clk,reset,
    input wire [63:0] now_us,
    input wire online,blocked,cancel,malformed,audio_ok,
    input wire packet_valid,packet_blocked,
    input wire [31:0] packet,
    output wire packet_ready,quarantined,
    output reg owned,gate,fault,
    output wire prepare_request,silence_request,event_valid,
    input wire prepare_done,silence_done,event_ready,event_error,
    input wire [3:0] prepare_result,
    output reg [7:0] event_register,event_value,
    output wire [5:0] mask,
    output wire [3:0] state_monitor,
    output reg [31:0] received,applied,rejected,invalid,ignored,panics
);
    localparam IDLE=4'd0,SETUP=4'd1,PRIME=4'd2,READY=4'd3,FAULT=4'd4,
        PREPARE=4'd5,BUILD=4'd6,WRITE=4'd7,CLEAN=4'd8;
    reg [3:0] state;
    reg [7:0] notes[0:5];
    reg [31:0] revision[0:5],done_revision[0:5];
    reg [6:0] setup_index;
    reg [2:0] cursor,voice;
    reg [7:0] note;
    reg [31:0] job_revision;
    reg [1:0] step;
    reg setup_job,releasing;
    reg [63:0] deadline,discard_until,io_started,release_at;
    wire [3:0] cin=packet[3:0],channel=packet[11:8];
    wire [7:0] status=packet[15:8],data1=packet[23:16],data2=packet[31:24];
    wire packet_supported=cin==8||cin==9||cin==11;
    wire packet_bad=packet_supported&&(status[7:4]!=cin||data1>127||data2>127);
    wire packet_on=cin==9&&data2!=0;
    wire candidate_valid;
    wire [7:0] unused_first,unused_second;
    revc_midi_rom candidate(.voice(channel[2:0]),.note(data1[6:0]),.valid(candidate_valid),.first(unused_first),.second(unused_second));
    wire want_on=packet_on&&candidate_valid;
    wire [7:0] new_note=want_on ? data1 : 8'hff;
    wire packet_panic=(cin==15&&status==255)||(cin==11&&channel<6&&data1==120)||packet_bad;
    wire can_update=packet_valid&&!packet_blocked&&online&&now_us>=discard_until&&packet[7:4]==0&&packet_supported&&!packet_bad&&channel<6&&
        !(cin==11&&data1!=123)&&!packet_panic&&state!=CLEAN&&state!=FAULT&&
        (want_on ? (owned||(!blocked&&!fault&&audio_ok)) : owned&&(cin==11||new_note==255&&(packet_on||data1==notes[channel[2:0]])));
    wire [7:0] pitch_first,pitch_second;
    wire pitch_valid;
    revc_midi_rom pitch(.voice(voice),.note(note[6:0]),.valid(pitch_valid),.first(pitch_first),.second(pitch_second));
    wire [2:0] ch=voice<3 ? voice : voice-3'd3;
    reg pending;
    reg [2:0] chosen;
    integer k;
    reg [3:0] scan;
    always @* begin
        pending=0;chosen=0;scan=0;
        for(integer n=0;n<6;n=n+1) begin
            scan={1'b0,cursor}+4'(n);if(scan>=6) scan=scan-6;
            if(!pending&&revision[scan[2:0]]!=done_revision[scan[2:0]]) begin pending=1;chosen=scan[2:0];end
        end
    end
    assign mask={notes[5]!=255,notes[4]!=255,notes[3]!=255,notes[2]!=255,notes[1]!=255,notes[0]!=255};
    assign packet_ready=1;
    assign quarantined=!online||now_us<discard_until||state==CLEAN||fault;
    assign state_monitor=state;
    assign prepare_request=owned&&state==PREPARE;
    assign silence_request=owned&&state==CLEAN;
    assign event_valid=owned&&state==WRITE&&!cancel&&online;
    wire same_update=can_update&&channel[2:0]==voice;
    function [15:0] setup_word;
        input [6:0] i;
        reg [7:0] regno,value,base;
        reg [1:0] c,slot;
        reg [4:0] part;
        reg [2:0] group;
        begin
            if(i<29) begin c=0;part=i[4:0];end
            else if(i<58) begin c=1;part=5'(i-7'd29);end
            else begin c=2;part=5'(i-7'd58);end
            if(part<7) begin slot=0;group=part[2:0];end
            else if(part<14) begin slot=1;group=3'(part-5'd7);end
            else if(part<21) begin slot=2;group=3'(part-5'd14);end
            else begin slot=3;group=3'(part-5'd21);end
            case(group)
                0:begin base=8'h30;value=1;end 1:begin base=8'h40;value=slot==0?8'd0:8'd127;end
                2:begin base=8'h50;value=31;end 3:begin base=8'h60;value=0;end
                4:begin base=8'h70;value=0;end 5:begin base=8'h80;value=15;end
                default:begin base=8'h90;value=0;end
            endcase
            regno=base+{4'd0,slot,2'd0}+{6'd0,c};
            if(part==28) begin regno=8'hb0+8'(c);value=7;end
            if(i==87) begin regno=7;value=8'h38;end
            setup_word={regno,value};
        end
    endfunction
    wire [15:0] setup_pair=setup_word(setup_index);
    task stop_notes;
        begin
            gate<=0;releasing<=0;
            for(integer n=0;n<6;n=n+1) begin notes[n]<=255;revision[n]<=0;done_revision[n]<=0;end
            if(owned) begin state<=CLEAN;io_started<=now_us;end
        end
    endtask
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;owned<=0;gate<=0;fault<=0;setup_index<=0;cursor<=0;voice<=0;note<=255;job_revision<=0;step<=0;
            setup_job<=0;releasing<=0;deadline<=0;discard_until<=0;io_started<=0;release_at<=0;event_register<=0;event_value<=0;
            received<=0;applied<=0;rejected<=0;invalid<=0;ignored<=0;panics<=0;
            for(k=0;k<6;k=k+1) begin notes[k]<=255;revision[k]<=0;done_revision[k]<=0;end
        end else begin
            if(cancel||!online) discard_until<=now_us+64'(QUIET_US);
            if(packet_valid) begin
                received<=received+1'b1;
                if(!online||packet_blocked||now_us<discard_until||packet[7:4]!=0) ignored<=ignored+1'b1;
                else if(packet_bad) invalid<=invalid+1'b1;
                else if(!packet_supported&&!(cin==15&&status==255)) ignored<=ignored+1'b1;
                else if(channel>=6&&packet_supported) ignored<=ignored+1'b1;
                else if(cin==11&&data1!=120&&data1!=123) ignored<=ignored+1'b1;
                else if(want_on&&!owned&&(blocked||fault||!audio_ok)) rejected<=rejected+1'b1;
            end
            if(state==PREPARE) begin
                if(prepare_done) begin
                    if(prepare_result!=0||!audio_ok) begin fault<=1;stop_notes();end
                    else begin setup_index<=0;state<=SETUP;end
                end else if(now_us-io_started>=100000) begin fault<=1;stop_notes();end
            end else if(state==SETUP) begin
                event_register<=setup_pair[15:8];event_value<=setup_pair[7:0];setup_job<=1;io_started<=now_us;state<=WRITE;
            end else if(state==PRIME) begin
                if(now_us>=deadline) state<=READY;
            end else if(state==READY) begin
                if(pending) begin
                    voice<=chosen;note<=notes[chosen];job_revision<=revision[chosen];step<=0;setup_job<=0;state<=BUILD;releasing<=0;
                end else if(mask==0) begin
                    if(!releasing) begin releasing<=1;release_at<=now_us+135000;end
                    else if(now_us>=release_at) begin owned<=0;gate<=0;state<=IDLE;releasing<=0;end
                end
            end else if(state==BUILD) begin
                if(job_revision!=revision[voice]) state<=READY;
                else begin
                    event_register<=voice<3 ? (step==0||step==3 ? 8'h28 : (step==1 ? 8'ha4 : 8'ha0)+{5'd0,ch}) :
                        step==0||step==3 ? 8'd8+{5'd0,ch} : 8'(2*ch)+(step==2 ? 8'd1 : 8'd0);
                    event_value<=step==0||note==255 ? (voice<3 ? {5'd0,ch} : 8'd0) :
                        step==1 ? pitch_first : step==2 ? pitch_second : voice<3 ? (8'hf0|{5'd0,ch}) : 8'd7;
                    io_started<=now_us;state<=WRITE;
                end
            end else if(state==WRITE) begin
                if(event_error||now_us-io_started>=100000) begin fault<=1;stop_notes();end
                else if(event_ready) begin
                    applied<=applied+1'b1;
                    if(setup_job) begin
                        if(setup_index==87) begin deadline<=now_us+6750;state<=PRIME;end
                        else begin setup_index<=setup_index+1'b1;state<=SETUP;end
                    end else if(step==3||note==255) begin
                        done_revision[voice]<=job_revision;cursor<=voice==5?3'd0:voice+1'b1;state<=READY;
                        if(step==3&&note!=255&&job_revision==revision[voice]&&!same_update) gate<=1;
                    end else begin step<=step+1'b1;state<=BUILD;end
                end
            end else if(state==CLEAN) begin
                if(silence_done) begin owned<=0;state<=fault?FAULT:IDLE;end
                else if(now_us-io_started>=100000) begin fault<=1;owned<=0;state<=FAULT;end
            end
            if(can_update&&!cancel) begin
                notes[channel[2:0]]<=new_note;revision[channel[2:0]]<=revision[channel[2:0]]+1'b1;releasing<=0;
                if(want_on&&!owned) begin
                    owned<=1;gate<=0;state<=PREPARE;io_started<=now_us;cursor<=0;
                end
            end
            if(cancel||!online||(owned&&(!audio_ok&&state!=PREPARE))||
                (owned&&(malformed||(packet_valid&&!packet_blocked&&packet[7:4]==0&&packet_panic&&now_us>=discard_until)))) begin
                if(owned&&state!=CLEAN) begin stop_notes();panics<=panics+1'b1;discard_until<=now_us+64'(QUIET_US);end
            end
        end
    end
    wire unused_pitch=&{unused_first,unused_second,pitch_valid};
endmodule
