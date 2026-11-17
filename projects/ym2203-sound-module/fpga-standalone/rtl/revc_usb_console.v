// SPDX-License-Identifier: MIT
// Bounded CDC console. Parsing and STOP remain live while the IN endpoint NAKs.
// Status is a coherent snapshot; responses may be replaced by a newer command.
module revc_usb_console (
 input wire clk,reset,connected,
 input wire [7:0] rx_data,input wire rx_valid,output wire rx_ready,
 output reg [7:0] tx_data,output wire tx_valid,input wire tx_ready,
 output reg stop_request,panic_request,
 input wire audio_ok,audio_fault,input wire [2:0] state,
 input wire [31:0] executed,input wire [1:0] gates,
 input wire midi_owned,input wire [5:0] midi_mask
);
 reg [127:0] command;
 reg [4:0] count;
 reg overflow;
 reg [2:0] reply;
 reg [7:0] pos;
 reg [223:0] snapshot;
 reg [7:0] length;
 function [7:0] hexchar;
 input [3:0] n;
 begin hexchar=n<10 ? 8'd48+{4'd0,n} : 8'd87+{4'd0,n};end
 endfunction
 assign rx_ready=1;
 assign tx_valid=reply!=0&&connected;
 always @* begin
  tx_data=0;length=0;
  case(reply)
   3'd1:begin length=8'd62;case(pos)
    8'd0:tx_data=8'd70;
    8'd1:tx_data=8'd49;
    8'd2:tx_data=8'd32;
    8'd3:tx_data=8'd67;
    8'd4:tx_data=8'd68;
    8'd5:tx_data=8'd67;
    8'd6:tx_data=8'd58;
    8'd7:tx_data=8'd32;
    8'd8:tx_data=8'd115;
    8'd9:tx_data=8'd116;
    8'd10:tx_data=8'd97;
    8'd11:tx_data=8'd116;
    8'd12:tx_data=8'd117;
    8'd13:tx_data=8'd115;
    8'd14:tx_data=8'd44;
    8'd15:tx_data=8'd104;
    8'd16:tx_data=8'd101;
    8'd17:tx_data=8'd108;
    8'd18:tx_data=8'd112;
    8'd19:tx_data=8'd44;
    8'd20:tx_data=8'd115;
    8'd21:tx_data=8'd116;
    8'd22:tx_data=8'd111;
    8'd23:tx_data=8'd112;
    8'd24:tx_data=8'd44;
    8'd25:tx_data=8'd115;
    8'd26:tx_data=8'd44;
    8'd27:tx_data=8'd112;
    8'd28:tx_data=8'd97;
    8'd29:tx_data=8'd110;
    8'd30:tx_data=8'd105;
    8'd31:tx_data=8'd99;
    8'd32:tx_data=8'd59;
    8'd33:tx_data=8'd32;
    8'd34:tx_data=8'd77;
    8'd35:tx_data=8'd73;
    8'd36:tx_data=8'd68;
    8'd37:tx_data=8'd73;
    8'd38:tx_data=8'd32;
    8'd39:tx_data=8'd99;
    8'd40:tx_data=8'd104;
    8'd41:tx_data=8'd97;
    8'd42:tx_data=8'd110;
    8'd43:tx_data=8'd110;
    8'd44:tx_data=8'd101;
    8'd45:tx_data=8'd108;
    8'd46:tx_data=8'd115;
    8'd47:tx_data=8'd49;
    8'd48:tx_data=8'd46;
    8'd49:tx_data=8'd46;
    8'd50:tx_data=8'd54;
    8'd51:tx_data=8'd59;
    8'd52:tx_data=8'd32;
    8'd53:tx_data=8'd110;
    8'd54:tx_data=8'd111;
    8'd55:tx_data=8'd32;
    8'd56:tx_data=8'd82;
    8'd57:tx_data=8'd69;
    8'd58:tx_data=8'd80;
    8'd59:tx_data=8'd76;
    8'd60:tx_data=8'd13;
    8'd61:tx_data=8'd10;
    default:tx_data=0;endcase end
   3'd2:begin length=8'd126;case(pos)
    8'd0:tx_data=8'd83;
    8'd1:tx_data=8'd84;
    8'd2:tx_data=8'd65;
    8'd3:tx_data=8'd84;
    8'd4:tx_data=8'd85;
    8'd5:tx_data=8'd83;
    8'd6:tx_data=8'd32;
    8'd7:tx_data=8'd70;
    8'd8:tx_data=8'd49;
    8'd9:tx_data=8'd32;
    8'd10:tx_data=8'd97;
    8'd11:tx_data=8'd117;
    8'd12:tx_data=8'd100;
    8'd13:tx_data=8'd105;
    8'd14:tx_data=8'd111;
    8'd15:tx_data=8'd95;
    8'd16:tx_data=8'd111;
    8'd17:tx_data=8'd107;
    8'd18:tx_data=8'd61;
    8'd19:tx_data=hexchar(snapshot[220 +: 4]);
    8'd20:tx_data=hexchar(snapshot[216 +: 4]);
    8'd21:tx_data=hexchar(snapshot[212 +: 4]);
    8'd22:tx_data=hexchar(snapshot[208 +: 4]);
    8'd23:tx_data=hexchar(snapshot[204 +: 4]);
    8'd24:tx_data=hexchar(snapshot[200 +: 4]);
    8'd25:tx_data=hexchar(snapshot[196 +: 4]);
    8'd26:tx_data=hexchar(snapshot[192 +: 4]);
    8'd27:tx_data=8'd32;
    8'd28:tx_data=8'd102;
    8'd29:tx_data=8'd97;
    8'd30:tx_data=8'd117;
    8'd31:tx_data=8'd108;
    8'd32:tx_data=8'd116;
    8'd33:tx_data=8'd61;
    8'd34:tx_data=hexchar(snapshot[188 +: 4]);
    8'd35:tx_data=hexchar(snapshot[184 +: 4]);
    8'd36:tx_data=hexchar(snapshot[180 +: 4]);
    8'd37:tx_data=hexchar(snapshot[176 +: 4]);
    8'd38:tx_data=hexchar(snapshot[172 +: 4]);
    8'd39:tx_data=hexchar(snapshot[168 +: 4]);
    8'd40:tx_data=hexchar(snapshot[164 +: 4]);
    8'd41:tx_data=hexchar(snapshot[160 +: 4]);
    8'd42:tx_data=8'd32;
    8'd43:tx_data=8'd115;
    8'd44:tx_data=8'd116;
    8'd45:tx_data=8'd97;
    8'd46:tx_data=8'd116;
    8'd47:tx_data=8'd101;
    8'd48:tx_data=8'd61;
    8'd49:tx_data=hexchar(snapshot[156 +: 4]);
    8'd50:tx_data=hexchar(snapshot[152 +: 4]);
    8'd51:tx_data=hexchar(snapshot[148 +: 4]);
    8'd52:tx_data=hexchar(snapshot[144 +: 4]);
    8'd53:tx_data=hexchar(snapshot[140 +: 4]);
    8'd54:tx_data=hexchar(snapshot[136 +: 4]);
    8'd55:tx_data=hexchar(snapshot[132 +: 4]);
    8'd56:tx_data=hexchar(snapshot[128 +: 4]);
    8'd57:tx_data=8'd32;
    8'd58:tx_data=8'd101;
    8'd59:tx_data=8'd120;
    8'd60:tx_data=8'd101;
    8'd61:tx_data=8'd99;
    8'd62:tx_data=8'd117;
    8'd63:tx_data=8'd116;
    8'd64:tx_data=8'd101;
    8'd65:tx_data=8'd100;
    8'd66:tx_data=8'd61;
    8'd67:tx_data=hexchar(snapshot[124 +: 4]);
    8'd68:tx_data=hexchar(snapshot[120 +: 4]);
    8'd69:tx_data=hexchar(snapshot[116 +: 4]);
    8'd70:tx_data=hexchar(snapshot[112 +: 4]);
    8'd71:tx_data=hexchar(snapshot[108 +: 4]);
    8'd72:tx_data=hexchar(snapshot[104 +: 4]);
    8'd73:tx_data=hexchar(snapshot[100 +: 4]);
    8'd74:tx_data=hexchar(snapshot[96 +: 4]);
    8'd75:tx_data=8'd32;
    8'd76:tx_data=8'd103;
    8'd77:tx_data=8'd97;
    8'd78:tx_data=8'd116;
    8'd79:tx_data=8'd101;
    8'd80:tx_data=8'd115;
    8'd81:tx_data=8'd61;
    8'd82:tx_data=hexchar(snapshot[92 +: 4]);
    8'd83:tx_data=hexchar(snapshot[88 +: 4]);
    8'd84:tx_data=hexchar(snapshot[84 +: 4]);
    8'd85:tx_data=hexchar(snapshot[80 +: 4]);
    8'd86:tx_data=hexchar(snapshot[76 +: 4]);
    8'd87:tx_data=hexchar(snapshot[72 +: 4]);
    8'd88:tx_data=hexchar(snapshot[68 +: 4]);
    8'd89:tx_data=hexchar(snapshot[64 +: 4]);
    8'd90:tx_data=8'd32;
    8'd91:tx_data=8'd77;
    8'd92:tx_data=8'd73;
    8'd93:tx_data=8'd68;
    8'd94:tx_data=8'd73;
    8'd95:tx_data=8'd95;
    8'd96:tx_data=8'd111;
    8'd97:tx_data=8'd119;
    8'd98:tx_data=8'd110;
    8'd99:tx_data=8'd101;
    8'd100:tx_data=8'd100;
    8'd101:tx_data=8'd61;
    8'd102:tx_data=hexchar(snapshot[60 +: 4]);
    8'd103:tx_data=hexchar(snapshot[56 +: 4]);
    8'd104:tx_data=hexchar(snapshot[52 +: 4]);
    8'd105:tx_data=hexchar(snapshot[48 +: 4]);
    8'd106:tx_data=hexchar(snapshot[44 +: 4]);
    8'd107:tx_data=hexchar(snapshot[40 +: 4]);
    8'd108:tx_data=hexchar(snapshot[36 +: 4]);
    8'd109:tx_data=hexchar(snapshot[32 +: 4]);
    8'd110:tx_data=8'd32;
    8'd111:tx_data=8'd109;
    8'd112:tx_data=8'd97;
    8'd113:tx_data=8'd115;
    8'd114:tx_data=8'd107;
    8'd115:tx_data=8'd61;
    8'd116:tx_data=hexchar(snapshot[28 +: 4]);
    8'd117:tx_data=hexchar(snapshot[24 +: 4]);
    8'd118:tx_data=hexchar(snapshot[20 +: 4]);
    8'd119:tx_data=hexchar(snapshot[16 +: 4]);
    8'd120:tx_data=hexchar(snapshot[12 +: 4]);
    8'd121:tx_data=hexchar(snapshot[8 +: 4]);
    8'd122:tx_data=hexchar(snapshot[4 +: 4]);
    8'd123:tx_data=hexchar(snapshot[0 +: 4]);
    8'd124:tx_data=8'd13;
    8'd125:tx_data=8'd10;
    default:tx_data=0;endcase end
   3'd3:begin length=8'd37;case(pos)
    8'd0:tx_data=8'd83;
    8'd1:tx_data=8'd84;
    8'd2:tx_data=8'd79;
    8'd3:tx_data=8'd80;
    8'd4:tx_data=8'd32;
    8'd5:tx_data=8'd114;
    8'd6:tx_data=8'd101;
    8'd7:tx_data=8'd113;
    8'd8:tx_data=8'd117;
    8'd9:tx_data=8'd101;
    8'd10:tx_data=8'd115;
    8'd11:tx_data=8'd116;
    8'd12:tx_data=8'd101;
    8'd13:tx_data=8'd100;
    8'd14:tx_data=8'd59;
    8'd15:tx_data=8'd32;
    8'd16:tx_data=8'd110;
    8'd17:tx_data=8'd111;
    8'd18:tx_data=8'd32;
    8'd19:tx_data=8'd97;
    8'd20:tx_data=8'd117;
    8'd21:tx_data=8'd116;
    8'd22:tx_data=8'd111;
    8'd23:tx_data=8'd109;
    8'd24:tx_data=8'd97;
    8'd25:tx_data=8'd116;
    8'd26:tx_data=8'd105;
    8'd27:tx_data=8'd99;
    8'd28:tx_data=8'd32;
    8'd29:tx_data=8'd114;
    8'd30:tx_data=8'd101;
    8'd31:tx_data=8'd112;
    8'd32:tx_data=8'd108;
    8'd33:tx_data=8'd97;
    8'd34:tx_data=8'd121;
    8'd35:tx_data=8'd13;
    8'd36:tx_data=8'd10;
    default:tx_data=0;endcase end
   3'd4:begin length=8'd22;case(pos)
    8'd0:tx_data=8'd77;
    8'd1:tx_data=8'd73;
    8'd2:tx_data=8'd68;
    8'd3:tx_data=8'd73;
    8'd4:tx_data=8'd32;
    8'd5:tx_data=8'd112;
    8'd6:tx_data=8'd97;
    8'd7:tx_data=8'd110;
    8'd8:tx_data=8'd105;
    8'd9:tx_data=8'd99;
    8'd10:tx_data=8'd32;
    8'd11:tx_data=8'd114;
    8'd12:tx_data=8'd101;
    8'd13:tx_data=8'd113;
    8'd14:tx_data=8'd117;
    8'd15:tx_data=8'd101;
    8'd16:tx_data=8'd115;
    8'd17:tx_data=8'd116;
    8'd18:tx_data=8'd101;
    8'd19:tx_data=8'd100;
    8'd20:tx_data=8'd13;
    8'd21:tx_data=8'd10;
    default:tx_data=0;endcase end
   3'd5:begin length=8'd33;case(pos)
    8'd0:tx_data=8'd69;
    8'd1:tx_data=8'd82;
    8'd2:tx_data=8'd82;
    8'd3:tx_data=8'd79;
    8'd4:tx_data=8'd82;
    8'd5:tx_data=8'd32;
    8'd6:tx_data=8'd117;
    8'd7:tx_data=8'd110;
    8'd8:tx_data=8'd115;
    8'd9:tx_data=8'd117;
    8'd10:tx_data=8'd112;
    8'd11:tx_data=8'd112;
    8'd12:tx_data=8'd111;
    8'd13:tx_data=8'd114;
    8'd14:tx_data=8'd116;
    8'd15:tx_data=8'd101;
    8'd16:tx_data=8'd100;
    8'd17:tx_data=8'd32;
    8'd18:tx_data=8'd99;
    8'd19:tx_data=8'd111;
    8'd20:tx_data=8'd109;
    8'd21:tx_data=8'd109;
    8'd22:tx_data=8'd97;
    8'd23:tx_data=8'd110;
    8'd24:tx_data=8'd100;
    8'd25:tx_data=8'd59;
    8'd26:tx_data=8'd32;
    8'd27:tx_data=8'd104;
    8'd28:tx_data=8'd101;
    8'd29:tx_data=8'd108;
    8'd30:tx_data=8'd112;
    8'd31:tx_data=8'd13;
    8'd32:tx_data=8'd10;
    default:tx_data=0;endcase end
   default:begin tx_data=0;length=0;end
  endcase
 end
 always @(posedge clk) begin
  if(reset||!connected) begin command<=0;count<=0;overflow<=0;reply<=0;pos<=0;snapshot<=0;stop_request<=0;panic_request<=0;end
  else begin
   stop_request<=0;panic_request<=0;
   if(tx_valid&&tx_ready) begin
    if(pos+1'b1==length) begin reply<=0;pos<=0;end else pos<=pos+1'b1;
   end
   if(rx_valid) begin
    if(rx_data==3) begin stop_request<=1;reply<=3;pos<=0;command<=0;count<=0;overflow<=0;end
    else if(rx_data==10||rx_data==13) begin
     if(count!=0||overflow) begin
      pos<=0;reply<=5;
      if(!overflow) begin
       if(command==128'h73746f70||command==128'h73) begin stop_request<=1;reply<=3;end
       else if(command==128'h70616e6963) begin panic_request<=1;reply<=4;end
       else if(command==128'h68656c70) reply<=1;
       else if(command==128'h737461747573) begin
        reply<=2;snapshot<={31'd0,audio_ok,31'd0,audio_fault,29'd0,state,executed,30'd0,gates,31'd0,midi_owned,26'd0,midi_mask};
       end
      end
     end
     command<=0;count<=0;overflow<=0;
    end else if(rx_data==8||rx_data==127) begin if(count!=0) begin command<=command>>8;count<=count-1'b1;end end
    else if(rx_data>=32&&rx_data<=126) begin
     if(count<16) begin command<={command[119:0],rx_data};count<=count+1'b1;end else overflow<=1;
    end else overflow<=1;
   end
  end
 end
endmodule
