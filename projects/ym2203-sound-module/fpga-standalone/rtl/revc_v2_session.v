// SPDX-License-Identifier: MIT
// Rev C C I2C v2 session, atomic FIFO publication, scheduler and status snapshot.
// All ports are synchronous. Physical I2C, timebase, audio and YM bus are adapters.
module revc_v2_session #(parameter integer CHECK_CLOCK=0) (
    input wire clk, reset,
    input wire [63:0] now_us,
    input wire [23:0] configured_clock_hz,
    input wire audio_ok, other_owned, global_stop, transport_error,
    input wire frame_valid,
    output wire frame_take,
    input wire [3:0] frame_result,
    input wire [8:0] frame_length,
    input wire [7:0] frame_opcode,
    input wire [31:0] frame_sequence,
    input wire [15:0] frame_payload_length,
    output reg [7:0] frame_address,
    input wire [7:0] frame_data,
    output wire prepare_request,
    input wire prepare_done,
    input wire [3:0] prepare_result,
    output reg silence_request,
    input wire silence_done,
    output wire gate_request,source_reserved,
    output wire event_valid,
    output wire [7:0] event_register, event_value,
    input wire event_ready, event_error,
    input wire status_request,
    output wire status_busy,
    output reg status_valid,
    input wire [7:0] status_address,
    output wire [7:0] status_data,
    output reg [2:0] session_state,
    output reg [3:0] result, error,
    output wire [10:0] queued,
    output reg [31:0] next_sequence, ack_sequence, received, executed,
    output reg sealed
);
    localparam IDLE = 3'd0, PREFILL = 3'd1, RUNNING = 3'd2,
               DONE = 3'd3, STOPPED = 3'd4, FAULT = 3'd5;
    localparam C_IDLE = 4'd0, C_DUP = 4'd1, C_PAYLOAD = 4'd2,
               C_APPLY = 4'd3, C_PREPARE = 4'd4, C_COPY = 4'd5,
               C_COMMIT = 4'd6, C_RELEASE = 4'd7, C_SILENCE = 4'd8;
    reg [3:0] command_state;
    reg [7:0] op;
    reg [31:0] seq;
    reg [8:0] length;
    reg [7:0] payload_length, cursor;
    reg [31:0] total, period_ms, last_ms, stream_crc, expected_crc, max_late_us;
    reg [10:0] min_queue;
    reg [63:0] origin_us, lease_us, prepare_started, silence_started;
    reg [31:0] word0, word1, word2, word3, word4;
    reg [31:0] work_crc, trial_ms, event_ms;
    reg [7:0] event_reg;
    reg [2:0] event_byte;
    reg [5:0] event_index, batch_count;
    reg have_last, last_bank, finishing;
    reg [31:0] last_seq;
    reg [8:0] last_length;
    reg [7:0] last_packet [0:511];
    reg fifo_clear;
    wire fifo_stage;
    wire [47:0] fifo_head;
    wire fifo_head_valid, fifo_pop;
    wire owned = session_state == PREFILL || session_state == RUNNING;
    assign source_reserved=owned||(frame_valid&&frame_result==0&&frame_opcode==2)||
        (command_state!=C_IDLE&&op==2);
    wire lease_expired = owned && now_us - lease_us >= 64'd1000000;
    wire audio_fault = owned && !audio_ok;
    // Keep BRAM -> ms scaling -> lateness -> global stop out of one cycle.
    // The head is immutable until pop; invalidate all stages on every flush/pop.
    reg [41:0] head_due,period_due;
    reg [63:0] due_at,late_at,period_at;
    reg [2:0] head_ready;
    wire [31:0] late_us = now_us[31:0] - due_at[31:0];
    wire scheduler = command_state == C_IDLE && !frame_valid && !finishing &&
                     session_state == RUNNING && now_us >= origin_us &&
                     !lease_expired && audio_ok && !global_stop && !transport_error;
    wire due = scheduler && fifo_head_valid && head_ready[2] && now_us >= due_at;
    wire late_fault = due && now_us > late_at;
    wire empty_fault = scheduler && queued == 0 && received < total;
    wire writer_fault = due && !late_fault && event_error;
    wire silence_timeout = silence_request && !silence_done &&
                           now_us - silence_started >= 64'd100000;
    wire fail_now = transport_error || lease_expired || audio_fault ||
                    late_fault || empty_fault || writer_fault || silence_timeout;
    wire [3:0] failure = transport_error ? 4'd7 : lease_expired ? 4'd8 :
                        audio_fault ? 4'd12 : late_fault ? 4'd10 :
                        empty_fault ? 4'd9 : 4'd7;
    // At most 32 six-byte events. Decode the finite legal lengths instead of
    // inferring a generic integer divide/modulo on the command acceptance path.
    function [5:0] payload_events;
        input [15:0] bytes;
        begin case(bytes)
            16'd6:payload_events=6'd1;
            16'd12:payload_events=6'd2;
            16'd18:payload_events=6'd3;
            16'd24:payload_events=6'd4;
            16'd30:payload_events=6'd5;
            16'd36:payload_events=6'd6;
            16'd42:payload_events=6'd7;
            16'd48:payload_events=6'd8;
            16'd54:payload_events=6'd9;
            16'd60:payload_events=6'd10;
            16'd66:payload_events=6'd11;
            16'd72:payload_events=6'd12;
            16'd78:payload_events=6'd13;
            16'd84:payload_events=6'd14;
            16'd90:payload_events=6'd15;
            16'd96:payload_events=6'd16;
            16'd102:payload_events=6'd17;
            16'd108:payload_events=6'd18;
            16'd114:payload_events=6'd19;
            16'd120:payload_events=6'd20;
            16'd126:payload_events=6'd21;
            16'd132:payload_events=6'd22;
            16'd138:payload_events=6'd23;
            16'd144:payload_events=6'd24;
            16'd150:payload_events=6'd25;
            16'd156:payload_events=6'd26;
            16'd162:payload_events=6'd27;
            16'd168:payload_events=6'd28;
            16'd174:payload_events=6'd29;
            16'd180:payload_events=6'd30;
            16'd186:payload_events=6'd31;
            16'd192:payload_events=6'd32;
            default:payload_events=0;
        endcase end
    endfunction
    wire [5:0] incoming_count=payload_events(frame_payload_length);
    wire [10:0] free_events=11'd1024-queued;
    wire event_ok = valid_register(event_reg, frame_data) && event_ms >= trial_ms && event_ms <= period_ms;
    assign fifo_stage = command_state == C_PAYLOAD && op == 3 && event_byte == 5 && event_ok && !fail_now && !global_stop;
    wire [5:0] publish_count = command_state == C_COMMIT && op == 3 && !fail_now && !global_stop ? batch_count : 6'd0;
    assign fifo_pop = event_valid && event_ready;
    assign event_valid = due && !fail_now && !event_error;
    assign event_register = fifo_head[15:8];
    assign event_value = fifo_head[7:0];
    assign gate_request = session_state == RUNNING && now_us >= origin_us &&
                          !finishing && !silence_request && !fail_now && !global_stop;
    assign prepare_request = command_state == C_PREPARE && !fail_now && !global_stop;
    assign frame_take = command_state == C_RELEASE || global_stop || transport_error ||
                        (fail_now && command_state != C_IDLE);

    revc_event_fifo fifo (
        .clk(clk), .reset(reset), .clear(fifo_clear || global_stop || fail_now),
        .stage_write(fifo_stage), .stage_offset(event_index[4:0]),
        .stage_data({event_ms, event_reg, frame_data}), .publish_count(publish_count),
        .pop(fifo_pop), .level(queued), .head_valid(fifo_head_valid), .head_data(fifo_head)
    );

    always @(posedge clk) begin
        if(reset) begin head_due<=0;period_due<=0;due_at<=0;late_at<=0;period_at<=0;head_ready<=0;end
        else begin
            period_due<=42'(ms_to_us(period_ms));
            period_at<=origin_us+{22'd0,period_due};
            if(fifo_clear||global_stop||fail_now||fifo_pop||!fifo_head_valid) head_ready<=0;
            else begin
                head_due<=42'(ms_to_us(fifo_head[47:16]));
                due_at<=origin_us+{22'd0,head_due};
                late_at<=due_at+64'd100000;
                head_ready<={head_ready[1:0],1'b1};
            end
        end
    end

    function [31:0] crc_byte;
        input [31:0] prior; input [7:0] value;
        reg [31:0] c; integer i;
        begin
            c = prior ^ {24'd0,value};
            for (i = 0; i < 8; i = i + 1) c = (c >> 1) ^ (c[0] ? 32'hedb88320 : 0);
            crc_byte = c;
        end
    endfunction
    function [63:0] ms_to_us;
        input [31:0] ms;
        reg [63:0] wide;
        begin wide = {32'd0,ms}; ms_to_us = (wide << 10) - (wide << 4) - (wide << 3); end
    endfunction
    function valid_register;
        input [7:0] r, v;
        reg [7:0] mask;
        begin
            valid_register = 0; mask = 0;
            if (r <= 13) begin
                case (r)
                    1,3,5,13: valid_register = v <= 15;
                    6: valid_register = v <= 31;
                    7: valid_register = v <= 63;
                    8,9,10: valid_register = v <= 31;
                    default: valid_register = 1;
                endcase
            end else if (r == 8'h28) valid_register = !(|(v & 8'h0c)) && v[1:0] != 3;
            else if (r == 8'h24 || r == 8'h26) valid_register = 1;
            else if (r == 8'h25) valid_register = v <= 3;
            else if (r == 8'h27) valid_register = v <= 63;
            else if (r >= 8'h30 && r <= 8'h9e && r[1:0] != 3) begin
                case (r[7:4])
                    3,4: mask = 127;
                    5: mask = 223;
                    6: mask = 159;
                    7: mask = 31;
                    8: mask = 255;
                    default: mask = 15;
                endcase
                valid_register = !(|(v & ~mask));
            end else if (r >= 8'ha0 && r <= 8'ha2) valid_register = 1;
            else if ((r >= 8'ha4 && r <= 8'ha6) || (r >= 8'hb0 && r <= 8'hb2)) valid_register = v <= 63;
        end
    endfunction

    always @* begin
        frame_address = cursor;
        if (command_state == C_PAYLOAD) frame_address = cursor + 8'd12;
    end

    always @(posedge clk) begin
        if (reset) begin
            session_state <= IDLE; command_state <= C_IDLE;
            next_sequence <= 0; ack_sequence <= 32'hffffffff;
            result <= 0; error <= 0; total <= 0; period_ms <= 0;
            received <= 0; executed <= 0; sealed <= 0;
            last_ms <= 0; stream_crc <= 0; expected_crc <= 0; max_late_us <= 0;
            min_queue <= 1024; origin_us <= 0; lease_us <= 0;
            have_last <= 0; last_bank <= 0; last_seq <= 0; last_length <= 0;
            fifo_clear <= 0; silence_request <= 0; finishing <= 0;
            silence_started <= 0; prepare_started <= 0;
            cursor <= 0; op <= 0; seq <= 0; length <= 0; payload_length <= 0;
            word0 <= 0; word1 <= 0; word2 <= 0; word3 <= 0; word4 <= 0;
            work_crc <= 0; trial_ms <= 0; event_ms <= 0; event_reg <= 0;
            event_byte <= 0; event_index <= 0; batch_count <= 0;
        end else begin
            fifo_clear <= 0;
            if (silence_request && silence_done) silence_request <= 0;
            if (global_stop) begin
                session_state <= STOPPED; command_state <= C_RELEASE;
                error <= 0; sealed <= 0; finishing <= 0;
                silence_request <= 1; silence_started <= now_us;
            end else if (fail_now) begin
                session_state <= FAULT; error <= failure;
                // Consume an interrupted request without claiming successful ACK.
                if (command_state != C_IDLE && command_state != C_RELEASE) result <= failure;
                // A newly arrived command still sees the expired FAULT state,
                // matching C's expire-before-command ordering and ACK semantics.
                command_state <= command_state == C_IDLE && !transport_error ? C_IDLE : C_RELEASE;
                finishing <= 0;
                silence_request <= 1; silence_started <= now_us;
            end else begin
                if (finishing && silence_done) begin
                    finishing <= 0; session_state <= DONE;
                end
                if (scheduler) begin
                    if (queued < min_queue) min_queue <= queued;
                    if (queued == 0 && sealed && received == total && executed == total &&
                        now_us >= period_at) begin
                        finishing <= 1; silence_request <= 1; silence_started <= now_us;
                    end
                    if (fifo_pop) begin
                        executed <= executed + 1'b1;
                        if (late_us[31:0] > max_late_us) max_late_us <= late_us[31:0];
                    end
                end
                case (command_state)
                    C_IDLE: if (frame_valid) begin
                        op <= frame_opcode; seq <= frame_sequence;
                        length <= frame_length; payload_length <= frame_payload_length[7:0];
                        cursor <= 0; work_crc <= stream_crc; trial_ms <= last_ms;
                        event_ms <= 0; event_reg <= 0; event_byte <= 0; event_index <= 0;
                        word0 <= 0; word1 <= 0; word2 <= 0; word3 <= 0; word4 <= 0;
                        if (frame_result != 0) begin
                            result <= frame_result; command_state <= C_RELEASE;
                            if (frame_result == 7) begin
                                session_state <= FAULT; error <= 7; fifo_clear <= 1;
                                silence_request <= 1; silence_started <= now_us;
                            end
                        end else begin
                            ack_sequence <= frame_sequence;
                            if (have_last && frame_sequence == last_seq) begin
                                if (frame_length != last_length) begin result <= 3; command_state <= C_RELEASE; end
                                else command_state <= C_DUP;
                            end else if (frame_sequence != next_sequence && frame_opcode != 1) begin
                                result <= 3; command_state <= C_RELEASE;
                            end else begin
                                result <= 0;
                                case (frame_opcode)
                                    0,1: if (frame_payload_length != 0) begin result <= 2; command_state <= C_RELEASE; end
                                         else if (frame_opcode == 1) begin
                                             session_state <= STOPPED; error <= 0; sealed <= 0; finishing <= 0;
                                             fifo_clear <= 1; silence_request <= 1; silence_started <= now_us;
                                             command_state <= C_SILENCE;
                                         end else command_state <= C_COPY;
                                    2: if (frame_payload_length != 20) begin result <= 2; command_state <= C_RELEASE; end
                                       else begin work_crc <= 32'hffffffff; command_state <= C_PAYLOAD; end
                                    3: if (incoming_count == 0) begin
                                           result <= 2; command_state <= C_RELEASE;
                                       end else if (!owned || sealed) begin result <= 4; command_state <= C_RELEASE; end
                                       else if ({26'd0,incoming_count} > total - received) begin
                                           result <= 6; command_state <= C_RELEASE;
                                       end else if ({5'd0,incoming_count} > free_events) begin
                                           result <= 5; command_state <= C_RELEASE;
                                       end else begin
                                           batch_count <= incoming_count;
                                           command_state <= C_PAYLOAD;
                                       end
                                    4: if (frame_payload_length != 0 || session_state != PREFILL ||
                                           {21'd0,queued} < (total < 512 ? total : 32'd512)) begin
                                           result <= 4; command_state <= C_RELEASE;
                                       end else command_state <= C_COPY;
                                    5: if (frame_payload_length != 0 || !owned) begin result <= 4; command_state <= C_RELEASE; end
                                       else command_state <= C_COPY;
                                    6: if (frame_payload_length != 0 || !owned || received != total) begin
                                           result <= 4; command_state <= C_RELEASE;
                                       end else if (~stream_crc != expected_crc) begin
                                           result <= 11; error <= 11; session_state <= FAULT; fifo_clear <= 1;
                                           silence_request <= 1; silence_started <= now_us; command_state <= C_RELEASE;
                                       end else command_state <= C_COPY;
                                    default: begin result <= 2; command_state <= C_RELEASE; end
                                endcase
                            end
                        end
                    end
                    C_DUP: begin
                        if (frame_data != last_packet[{last_bank,cursor}]) begin
                            result <= 3; command_state <= C_RELEASE;
                        end else if ({1'b0,cursor} + 9'd1 == length) begin
                            result <= 0; command_state <= C_RELEASE;
                        end else cursor <= cursor + 1'b1;
                    end
                    C_PAYLOAD: begin
                        if (op == 2) begin
                            case (cursor[7:2])
                                0: word0[cursor[1:0]*8 +: 8] <= frame_data;
                                1: word1[cursor[1:0]*8 +: 8] <= frame_data;
                                2: word2[cursor[1:0]*8 +: 8] <= frame_data;
                                3: word3[cursor[1:0]*8 +: 8] <= frame_data;
                                4: word4[cursor[1:0]*8 +: 8] <= frame_data;
                                default: begin end
                            endcase
                            if (cursor < 16) work_crc <= crc_byte(work_crc,frame_data);
                        end else begin
                            work_crc <= crc_byte(work_crc,frame_data);
                            case (event_byte)
                                0: event_ms[7:0] <= frame_data;
                                1: event_ms[15:8] <= frame_data;
                                2: event_ms[23:16] <= frame_data;
                                3: event_ms[31:24] <= frame_data;
                                4: event_reg <= frame_data;
                                default: begin
                                    if (!event_ok) begin result <= 6; command_state <= C_RELEASE; end
                                    trial_ms <= event_ms; event_index <= event_index + 1'b1;
                                end
                            endcase
                            event_byte <= event_byte == 5 ? 3'd0 : event_byte + 1'b1;
                        end
                        if (cursor + 8'd1 == payload_length) begin
                            if (op == 2 || event_ok) command_state <= C_APPLY;
                        end
                        cursor <= cursor + 1'b1;
                    end
                    C_APPLY: begin
                        cursor <= 0;
                        if (op == 2) begin
                            if (word0 != 32'h314d5957) begin result <= 2; command_state <= C_RELEASE; end
                            else if (word1 == 0 || word1 > 131071 || word2 == 0 || (word3 != 4000000 || (CHECK_CLOCK!=0 && configured_clock_hz!=4000000))) begin
                                result <= 6; command_state <= C_RELEASE;
                            end else if (owned || session_state == FAULT) begin result <= 4; command_state <= C_RELEASE; end
                            else if (other_owned) begin result <= 4; command_state <= C_RELEASE; end
                            else if (!audio_ok) begin
                                result <= 12; error <= 12; session_state <= FAULT; fifo_clear <= 1;
                                silence_request <= 1; silence_started <= now_us; command_state <= C_RELEASE;
                            end else begin prepare_started <= now_us; command_state <= C_PREPARE; end
                        end else command_state <= C_COPY;
                    end
                    C_PREPARE: begin
                        // Preparation intentionally resets/reprimes the audio
                        // path. Health may fall temporarily; judge it at done.
                        if (!prepare_done && now_us - prepare_started >= 64'd100000) begin
                            result <= 12; error <= 12; session_state <= FAULT; fifo_clear <= 1;
                            silence_request <= 1; silence_started <= now_us; command_state <= C_RELEASE;
                        end else if (prepare_done) begin
                            if (!audio_ok && prepare_result == 0) begin
                                result <= 12; error <= 12; session_state <= FAULT; fifo_clear <= 1;
                                silence_request <= 1; silence_started <= now_us; command_state <= C_RELEASE;
                            end else if (prepare_result == 0) command_state <= C_COPY;
                            else begin
                                result <= prepare_result; command_state <= C_RELEASE;
                                if (prepare_result == 12) begin
                                    session_state <= FAULT; error <= 12; fifo_clear <= 1;
                                    silence_request <= 1; silence_started <= now_us;
                                end
                            end
                        end
                    end
                    C_SILENCE: if (silence_done) begin cursor <= 0; command_state <= C_COPY; end
                    C_COPY: begin
                        // Double-bank the replay cache; failure cannot corrupt the prior success.
                        last_packet[{!last_bank,cursor}] <= frame_data;
                        if ({1'b0,cursor} + 9'd1 == length) command_state <= C_COMMIT;
                        else cursor <= cursor + 1'b1;
                    end
                    C_COMMIT: begin
                        have_last <= 1; last_bank <= !last_bank; last_seq <= seq; last_length <= length;
                        next_sequence <= seq + 1'b1; result <= 0;
                        case (op)
                            2: begin
                                fifo_clear <= 1; received <= 0; executed <= 0; total <= word1; period_ms <= word2;
                                last_ms <= 0; stream_crc <= work_crc; expected_crc <= word4;
                                max_late_us <= 0; min_queue <= 1024; sealed <= 0; session_state <= PREFILL;
                                error <= 0; lease_us <= now_us;
                            end
                            3: begin
                                received <= received + {26'd0,batch_count}; last_ms <= trial_ms;
                                stream_crc <= work_crc; lease_us <= now_us;
                            end
                            4: begin
                                origin_us <= now_us + 64'd250000; session_state <= RUNNING;
                                min_queue <= queued; lease_us <= now_us;
                            end
                            5: lease_us <= now_us;
                            6: begin sealed <= 1; lease_us <= now_us; end
                            default: begin end
                        endcase
                        command_state <= C_RELEASE;
                    end
                    C_RELEASE: command_state <= C_IDLE;
                    default: command_state <= C_IDLE;
                endcase
            end
        end
    end

    // Status is immutable until the next request. Division by 1000 is serial,
    // avoiding a long combinational 64-bit divider in the snapshot path.
    reg [1:0] snapshot_state;
    reg [6:0] snapshot_index;
    reg [31:0] status_crc, generation;
    reg [63:0] dividend;
    reg [9:0] remainder;
    reg [30:0] quotient;
    reg [7:0] snapshot [0:63];
    wire [10:0] shifted_remainder = {remainder,dividend[63]};
    wire divide_bit = shifted_remainder >= 1000;
    wire [9:0] next_remainder = divide_bit ? shifted_remainder[9:0] - 10'd1000 : shifted_remainder[9:0];
    wire [31:0] next_quotient = {quotient,divide_bit};
    assign status_busy = snapshot_state != 0;
    assign status_data = status_address < 64 ? snapshot[status_address[5:0]] : 8'hff;
    integer j;
    always @(posedge clk) begin
        if (reset) begin
            snapshot_state <= 0; snapshot_index <= 0; status_valid <= 0;
            status_crc <= 0; generation <= 0; dividend <= 0; quotient <= 0; remainder <= 0;
        end else begin
            case (snapshot_state)
                0: if (status_request && command_state == C_IDLE && !frame_valid) begin
                    status_valid <= 0; status_crc <= 32'hffffffff;
                    snapshot_index <= 0; snapshot_state <= 1;
                    dividend <= session_state >= RUNNING && now_us >= origin_us ? now_us-origin_us : 64'd0;
                    quotient <= 0; remainder <= 0;
                    snapshot[0] <= "Y"; snapshot[1] <= "M"; snapshot[2] <= "2"; snapshot[3] <= "2";
                    snapshot[4] <= "S"; snapshot[5] <= "0"; snapshot[6] <= "0"; snapshot[7] <= "2";
                    snapshot[8] <= 2; snapshot[9] <= {5'd0,session_state}; snapshot[10] <= {4'd0,result};
                    snapshot[11] <= {2'd0,error==8,owned,sealed,session_state==RUNNING,audio_ok,1'b1};
                    for (j = 0; j < 4; j = j + 1) begin
                        snapshot[12+j] <= ack_sequence[j*8 +: 8]; snapshot[16+j] <= next_sequence[j*8 +: 8];
                        snapshot[20+j] <= received[j*8 +: 8]; snapshot[24+j] <= executed[j*8 +: 8];
                        snapshot[28+j] <= total[j*8 +: 8]; snapshot[32+j] <= period_ms[j*8 +: 8];
                        snapshot[48+j] <= max_late_us[j*8 +: 8]; snapshot[52+j] <= ~stream_crc[j*8 +: 8];
                        snapshot[56+j] <= generation[j*8 +: 8];
                    end
                    snapshot[36] <= queued[7:0]; snapshot[37] <= {5'd0,queued[10:8]};
                    snapshot[38] <= 8'(11'd1024-queued); snapshot[39] <= 8'((11'd1024-queued)>>8);
                    snapshot[44] <= {4'd0,error}; snapshot[45] <= 0;
                    snapshot[46] <= min_queue[7:0]; snapshot[47] <= {5'd0,min_queue[10:8]};
                    generation <= generation + 1'b1;
                end
                1: begin
                    dividend <= {dividend[62:0],1'b0}; remainder <= next_remainder; quotient <= next_quotient[30:0];
                    if (snapshot_index == 63) begin
                        for (j = 0; j < 4; j = j + 1) snapshot[40+j] <= next_quotient[j*8 +: 8];
                        snapshot_index <= 0; snapshot_state <= 2;
                    end else snapshot_index <= snapshot_index + 1'b1;
                end
                2: begin
                    status_crc <= crc_byte(status_crc,snapshot[snapshot_index[5:0]]);
                    if (snapshot_index == 59) begin snapshot_state <= 3; end
                    else snapshot_index <= snapshot_index + 1'b1;
                end
                3: begin
                    for (j = 0; j < 4; j = j + 1) snapshot[60+j] <= ~status_crc[j*8 +: 8];
                    status_valid <= 1; snapshot_state <= 0;
                end
                default: snapshot_state <= 0;
            endcase
        end
    end
endmodule
