# SPDX-License-Identifier: MIT
from drawing import Block

def layout(board,parts):
 blocks=[]
 def block(title,x,y,w,h):
  b=Block(title,x,y,w,h,parts);blocks.append(b);return b
 def row(b,refs,x,y,step=27,orientation='v'):
  for i,r in enumerate(refs):b.add(r,x+i*step,y,orientation)
 if board=='panel':
  b=block('01  Grove power and reset',20,50,230,205)
  b.add('JUPLINK',60,95);b.add('DPOWER',155,105,'hf');b.add('CPIN',195,155,'v');b.add('RPANELRUN',70,155,'v');row(b,['C1','C3','C4'],65,215,48)
  b=block('02  Editor controller - physical Pico pin numbers',270,50,265,245);b.add('UPICO',400,170)
  b=block('03  32 KiB patch EEPROM',555,50,265,110)
  b.add('U1',680,107,sides=([1,2,3,4,7],[5,6,8]));b.add('REEPSDA',760,86,'v');b.add('REEPSCL',790,116,'v');b.add('C2',590,115,'v')
  b=block('04  LCD socket - SPI, not I2C',555,180,265,145)
  b.add('J5',737,247);b.add('R18',625,230);b.add('R19',625,260);b.add('R16',675,290,'v');b.add('R17',585,290,'v')
  b=block('05  Four knobs, RC filters and analog multiplexer',20,315,515,240)
  for i in range(4):
   y=360+i*48;b.add('RV'+str(i+1),70,y);b.add('R'+str(i+1),155,y);b.add('C'+str(i+5),205,y+17,'v')
  b.add('UMUX',390,430,sides=([13,14,15,12,1,5,2,4,8],[3,11,10,9,6,7,16]));b.add('CMUX',330,530,'v')
  b=block('06  Rotary encoder / push switch',555,350,135,205)
  b.add('ENC1',610,415);row(b,['R5','R7','R9'],575,530,36);b.add('R6',620,375);b.add('R8',620,460);b.add('C9',655,390,'v');b.add('C10',655,475,'v')
  b=block('07  Operator select, NOTE and STOP',710,350,110,195)
  for i in range(6):
   y=380+i*28;b.add('R'+str(10+i),735,y);b.add('SW'+str(i+1),785,y)
  return 'A1',blocks
 if board=='base':
  b=block('01  External 5V, AUX regulator, analog supply',20,50,180,230)
  b.add('JPOWER',58,95);b.add('F1',135,95);b.add('C1',145,145,'v');b.add('UAUX',97,202,sides=([3,1],[2]));row(b,['CAUXIN','CAUXOUT'],55,250,85)
  b=block('02  USB Type-C, ESD and VBUS detection',210,50,240,230)
  b.add('JUSB',265,125);b.add('UESD',380,110,sides=([1,3,2],[6,4,5]));row(b,['RCC1','RCC2'],280,225,48);b.add('CVBUS',415,155,'v');b.add('RVB1',340,200,'v');b.add('RVB2',340,250,'v');b.add('CVBD',390,245,'v');b.add('UVBUS',400,195,sides=([2,1,3],[4,5]));row(b,['CVB3','RVB3'],240,265,60)
  b=block('03  HOST I2C, SWD and reset',460,50,140,230)
  b.add('JHOST',500,100);b.add('JSWD',500,160);row(b,['R45','R46'],480,220,55);b.add('RRUN',495,260,'v');b.add('SWRESET',560,260);b.add('CRUN',560,200,'v')
  b=block('04  Base MCU / GPIO allocation',610,50,240,230);b.add('UBASE',730,160);b.add('C2',660,255,'v')
  b=block('05  Variable sound clock and editor I2C',860,50,310,230)
  b.add('U13',980,140,sides=([1,2,3,4,8],[5,6,7]));b.add('RCLK0',1085,115);b.add('RCLK1',1085,150);b.add('RCLK2',1085,185);b.add('JEDIT',1100,245)
  row(b,['R37','R38','C21','C22','CPANELPORT'],885,235,36)
  b=block('06  G40 interface - parallel/SPI, clocks, I2S and analog',20,300,620,235)
  b.add('JMOD',500,420)
  for i in range(8):b.add('RBD'+str(i),75,340+23*i)
  for i in range(4):b.add('RBCTL'+str(i),190,340+25*i)
  for i,r in enumerate(['RLKEN','RALERT','RLKBCK','RLKLR']):b.add(r,190,445+23*i)
  for i,r in enumerate(['RBEN','RBCS','RBMISO','RBSCK','RBMOSI','RBALERT','RBI1','RBSD']):b.add(r,310 if r=='RBSD' else 290+(i%2)*52,515 if r=='RBSD' else 350+(i//2)*45,'v')
  b.add('URXDATA',365,495,sides=([1,2,3],[4,5]));b.add('CURXDATA',580,520,'v')
  b=block('07  Clock DIP, status LEDs, STOP/TEST and mute gate',650,300,520,235)
  b.add('URGB',825,360);b.add('DRGB',825,440);b.add('RRGB',900,415);b.add('RRGBPD',745,365,'v');b.add('CURGB',690,350,'v');b.add('CRGB',900,365,'v')
  b.add('SWCLOCK',1025,370)
  for i in range(4):b.add('RP'+str(i),950,333+i*25)
  row(b,['RP4','RP5'],700,405,50);b.add('SWSTOP',700,455);b.add('SWTEST',755,455)
  for i,(r,d) in enumerate([('RPOWER','DPOWER'),('RLED0','DLED0'),('RTX','DTX')]):b.add(r,970+i*70,465,'vf');b.add(d,970+i*70,505,'vf')
  b.add('UMUTE',825,510,sides=([1,2,3],[4,5]));row(b,['RPDAC','RPLINE','CUMUTE'],690,515,36)
  b=block('08  Two-channel analog input / attenuation / protection',20,555,275,240)
  for side,y in [('L',630),('R',735)]:
   b.add('RATT'+side,60,y);b.add('RSHUNT'+side,90,y+35,'v');b.add('CAC'+side,140,y);b.add('RLIMIT'+side,205,y);b.add('CAAF'+side,235,y+35,'v');b.add('DCLAMP'+side,250,y-35)
  b=block('09  Common ADC / I2S to MCU',305,555,285,240)
  b.add('UADC',430,660,sides=([3,4,1,2,27,28,29,30,5,6,7,8,11,12,13,14],[16,17,18,23,24,21,25,26,19,20,22,9,10,15]))
  row(b,['RADCBCK','RADCLR','RADCDATA'],350,735,75,orientation='h');row(b,['RADCDATAPD','RDMINPD'],350,705,200)
  row(b,['CADCAV0','CADCAV1','CADCDV0','CADCDV1','CADCIO0','CADCIO1','CADCLDO0','CADCLDO1','CADCVREF'],325,775,28)
  b=block('10  PCM5102A DAC and I2S termination',600,555,300,240)
  b.add('U17',760,665,sides=([13,14,15,17,10,11,12,16,19,20],[6,7,2,4,5,18,1,3,8,9]));b.add('FB1',855,595)
  for i,r in enumerate(['R47','R48','R49']):b.add(r,645,625+i*32)
  row(b,['RI2SD','RI2SB','RI2SL','R50'],630,735,63)
  b.add('C28',850,665,'v');row(b,['C29','C30','C31','C32','C33','C34','C35'],620,775,40)
  b=block('11  Line filtering, onboard dual volume and TRS output',910,555,260,240)
  b.add('R53',960,625);b.add('R53R',960,700);b.add('C38',995,655,'v');b.add('C38R',995,730,'v');b.add('RVOL',1045,650);b.add('R59',1115,620);b.add('R60',1115,700);b.add('JLINE',1120,770)
  b=block('12  PHONES / VARIABLE LINE driver - 3.3V, unity gain, shared mute',20,815,1150,200)
  b.add('UHP',600,910,sides=([1,2,4,5,6,7,8],[14,13,12,9,10,11,3]))
  for side,y in [('L',875),('R',955)]:
   b.add('CHPIN'+side,110,y);b.add('RHPIN'+side,250,y);b.add('RHPFB'+side,405,y)
   b.add('CHPOUT'+side,1080,y,'v')
  row(b,['FBHP','CHPVDD','CHPHF','CHPFLY','CHPVSS','RHPMUTE'],690,955,60)
  return 'User',blocks
 if board=='module':
  b=block('01  G40 connector and 3.3V link buffers',20,50,265,255)
  b.add('JMOD',88,163);b.add('ULINK0',220,112,sides=([1,2,4,5,10,9,13,12,7],[3,6,8,11,14]));b.add('ULINK1',220,240,sides=([1,2,4,5,10,9,13,12,7],[3,6,8,11,14]))
  b=block('02  Picossci2B controller and isolated MCU feed',305,50,230,255)
  b.add('USOURCE',420,168);b.add('DMCU5V',360,85,'hf');b.add('JSWD',500,260);row(b,['CCORE','CCOREB'],350,285,75)
  b=block('03  YM2203 parallel bus, 3.3V / 5V translation',555,50,265,255)
  b.add('U8',685,115);b.add('U9',685,235)
  for r,x in [('RDIR',580),('RDOE',760),('RCOE',800)]:b.add(r,x,280,'v')
  # Decoupling for both bus translators follows the device supplies in section 7.
  b=block('04  Real YM2203C and FM capture buffers',20,325,265,230)
  b.add('U12',91,440);b.add('U16',225,405,sides=([1,2,4,5,10,9,13,12,7],[3,6,8,11,14]));
  for i,r in enumerate(['RS3','RS6','RS8']):b.add(r,225,465+i*33)
  b.add('R39',55,535);b.add('R40',125,535,'v')
  b=block('05  YM3014B-F DAC and dual voltage follower',305,325,315,230)
  b.add('UDAC',425,425,sides=([7,10,4,1,12,3,5,6],[14,16,2,8,9,11,13,15]));b.add('UAF',545,430)
  for i,r in enumerate(['RFMSD','RFMCLK','RFMSH']):b.add(r,345,365+i*30)
  b.add('RFMOUT',580,510);row(b,['CFMDAC','COPAMP','CRB','CANABULK'],340,535,62)
  b=block('06  SSG mix, reset and safe transmit',640,325,180,230)
  for i,r in enumerate(['RL0','RL1','RL2']):b.add(r,665,365+i*38,'v')
  for i,r in enumerate(['RSMIXA','RSMIXB','RSMIXC']):b.add(r,740,365+i*38)
  b.add('URUNOD',700,490,sides=([2,1,3],[4,5]));row(b,['RYMRESET','RRELDEFAULT','RENPD','RRUNUP'],660,535,40)
  # A separate lower bank is deliberate: all remaining passives are on this
  # same physical drawing and their rail/signal names connect to the blocks.
  # Expand the sheet for spacious bank wiring rather than shrinking labels.
  b=block('07  Defaults, link enables and local supply bypass',20,575,800,200)
  row(b,['C11','C12','C13','C14','C15','C16','C19','C20','C27','CMOD5','CURUNOD','CULINK0','CULINK1','CUTXOR','CUALERT'],45,625,50)
  row(b,['R32','RMC32','R33','RMC33','R34','RMC34','R35','RMA','RMSCK','RMMOSI','RMCS','RMBCK','RMLR','RMCLK','RMADR'],45,690,50)
  b.add('UTXOR',135,745,sides=([1,2,3],[4,5]));b.add('UALERT',320,745,sides=([2,1,3],[4,5]));b.add('RTXDIS',440,745,'v');b.add('RMTXMISO',570,730);b.add('RMTXDATA',570,760)
  row(b,['RD'+str(i) for i in range(8)],620,750,24)
  b=block('08  Source-local voice indicators - key enable, not PCM level',20,795,800,105)
  for i in range(1,7):b.add('RVOICE'+str(i),70+(i-1)*130,835,'vf');b.add('DVOICE'+str(i),70+(i-1)*130,880,'vf')
  return 'User',blocks
 raise ValueError(board)
