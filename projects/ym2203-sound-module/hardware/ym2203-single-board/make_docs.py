"""Create a checked Japanese review PDF and self-contained fabrication packages."""
from pathlib import Path
import json, math, os, csv, zipfile, hashlib
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import A3, landscape
from pypdf import PdfReader, PdfWriter
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'rev-c';PDFDIR=ROOT/'output/pdf';PDFDIR.mkdir(parents=True,exist_ok=True)
D=json.loads((OUT/'design.json').read_text());CHECK=json.loads((OUT/'verification.json').read_text())
assert CHECK['result']=='pass'
NAME='ym2203-single';BOARD=OUT/NAME
font=os.environ.get('PDF_JAPANESE_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
pdfmetrics.registerFont(TTFont('JP',font))
W,H=landscape(A3);NAVY=HexColor('#15283f');INK=HexColor('#20364a');TEAL=HexColor('#087f83');LIGHT=HexColor('#eaf2f5')
C=canvas.Canvas(str(PDFDIR/'guide-body.pdf'),pagesize=(W,H))
C.setTitle('YM2203C専用 1枚基板 Rev C');C.setAuthor('MicroPython WebLab contributors')
PAGE=0
def text(t,x,y,size=12,color=INK):
    C.setFillColor(color);C.setFont('JP',size);C.drawString(x,y,str(t))


def lines(s,width,size=12):
    out=[];line=''
    for ch in str(s):
        if ch=='\n':out.append(line);line='';continue
        if pdfmetrics.stringWidth(line+ch,'JP',size)>width:out.append(line);line=ch
        else:line+=ch
    if line:out.append(line)
    return out


def para(s,x,y,width,size=12,leading=19):
    for line in lines(s,width,size):text(line,x,y,size);y-=leading
    return y-9


def begin(title,sub=''):
    global PAGE
    PAGE+=1;C.setFillColor(NAVY);C.rect(0,H-87,W,87,fill=1,stroke=0)
    text(title,35,H-42,23,white);text(sub,36,H-66,11,HexColor('#d4e6ee'))
    text('YM2203C SINGLE BOARD  /  REV C  /  2026-10-18',35,24,9)
    text(str(PAGE),W-47,24,10)
    C.setStrokeColor(TEAL);C.setLineWidth(1);C.line(35,40,W-35,40)


def end():C.showPage()


def table(headers,rows,x,y,widths,rowh=22,size=10):
    total=sum(widths);C.setFillColor(TEAL);C.rect(x,y-rowh,total,rowh,fill=1,stroke=0)
    xx=x
    for h,w in zip(headers,widths):text(h,xx+6,y-rowh+7,size,white);xx+=w
    y-=rowh
    for i,row in enumerate(rows):
        C.setFillColor(LIGHT if i%2==0 else white);C.rect(x,y-rowh,total,rowh,fill=1,stroke=0)
        xx=x
        for s,w in zip(row,widths):
            assert pdfmetrics.stringWidth(str(s),'JP',size)<=w-10,(s,w,size)
            text(s,xx+6,y-rowh+7,size);xx+=w
        y-=rowh
    return y


def box(label,x,y,w,h,sub='',fill=LIGHT):
    C.setFillColor(fill);C.setStrokeColor(TEAL);C.setLineWidth(1)
    C.roundRect(x,y,w,h,7,fill=1,stroke=1)
    yy=y+h-23
    for line in lines(label,w-20,13):text(line,x+10,yy,13);yy-=19
    if sub:para(sub,x+10,yy-4,w-20,10,15)


def arrow(x1,y1,x2,y2):
    C.setStrokeColor(TEAL);C.setFillColor(TEAL);C.setLineWidth(2);C.line(x1,y1,x2,y2)
    a=math.atan2(y2-y1,x2-x1);p=C.beginPath();p.moveTo(x2,y2)
    for d in (-.45,.45):p.lineTo(x2-9*math.cos(a+d),y2-9*math.sin(a+d))
    p.close();C.drawPath(p,stroke=0,fill=1)


def draw_board(name,x,y,scale):
    g=json.loads((OUT/name/'geometry.json').read_text());w,h=g['size_mm']
    C.setFillColor(HexColor('#eef7ef'));C.setStrokeColor(HexColor('#466d52'));C.setLineWidth(1)
    C.rect(x,y,w*scale,h*scale,fill=1,stroke=1)
    pt=lambda a:(x+a[0]*scale,y+(h-a[1])*scale)
    for lay,col in [('bottom','#6792ce'),('top','#bf534c')]:
        C.setStrokeColor(HexColor(col))
        for t in g['tracks']:
            if t['layer']!=lay:continue
            C.setLineWidth(t['width']*scale);C.line(*pt(t['a']),*pt(t['b']))
    for v in g['vias']:
        xx,yy=pt([v['x'],v['y']]);C.setFillColor(HexColor('#bca671'));C.setStrokeColor(HexColor('#8d7c50'))
        C.circle(xx,yy,v['size']*scale/2,fill=1,stroke=0);C.setFillColor(white);C.circle(xx,yy,.15*scale,fill=1,stroke=0)
    pp=json.loads((OUT/name/'placement.json').read_text())
    C.setStrokeColor(Color(.12,.2,.26,.55));C.setLineWidth(.5)
    for p in pp:
        a,b,c,d=p['courtyard'];xx,yy=pt([a,d]);C.rect(xx,yy,(c-a)*scale,(d-b)*scale,stroke=1,fill=0)
    for p in g['pads']:
        xx,yy=pt([p['x'],p['y']]);C.setFillColor(HexColor('#d4b66e'))
        if p['rect']:C.rect(xx-p['sx']*scale/2,yy-p['sy']*scale/2,p['sx']*scale,p['sy']*scale,stroke=0,fill=1)
        else:C.circle(xx,yy,p['sx']*scale/2,stroke=0,fill=1)
        if p['drill']:
            C.setFillColor(white);C.circle(xx,yy,p['drill']*scale/2,stroke=0,fill=1)
    for p in g['footprints']:
        if p['ref'].startswith('H'):continue
        xx,yy=pt(p['text']);C.setFillColor(white)
        tw=pdfmetrics.stringWidth(p['ref'],'JP',7)+3;C.rect(xx-tw/2,yy-1,tw,9,stroke=0,fill=1)
        text(p['ref'],xx-tw/2+1,yy,7,NAVY)
    text('0,0',x,y+h*scale+9,9);text(str(w)+' mm',x+w*scale/2-12,y-17,10)
    text(str(h)+' mm',x+w*scale+10,y+h*scale/2,10)


external=[
 ('6mm Dカット軸用ノブ',1,'RV1用。ボリュームとジャック本体は主基板の部品表へ移動。'),
 ('USB-C ACアダプター＋短いC-Cケーブル',1,'5Vで1.5A以上。PC汎用ポートは対象外。基板は400mA以下を予算。'),
 ('USB-Cモジュール用2.54mmオスヘッダ',1,'1x7を1本、1x2を2本。同じ高さで直接はんだ固定。'),
 ('1x20 2.54mmメスソケット',2,'Pico 2の着脱用。'),
 ('1x10 2.54mmメスソケット',2,'AE-PCM5102Aの着脱用。'),
 ('1x12 2.54mmメスソケット',4,'AE-LLCNV 2個の着脱用。'),
 ('DIP40 600milソケット',1,'YM2203C。'),
 ('DIP14 300milソケット',5,'HC04/HC00/HC32/HC74/HC08。'),
 ('DIP8 300milソケット',1,'MCP6022。'),
 ('DIP16 300milソケット',1,'CD74HC4053。'),
 ('M3絶縁スペーサー・ねじ',4,'基板の4固定穴。底面のはんだ突出分を確保。'),
 ('データ対応USBケーブル',1,'Pico 2からPCへUSB-MIDI。AMS-22用は別途。'),
 ('3.5mmステレオTRSケーブル',1,'AMS-22のLINE INへ。'),
 ('ZOOM AMS-22',1,'録音・モニター。別途USBでPCへ。'),
 ('ホストMCU・I2C配線',1,'I2C使用時。ホストは別給電、GND/SDA/SCLのみ接続。'),
 ('配線材・リセットスイッチ',1,'基板外端子と必要に応じたRUNスイッチ。')]
with (OUT/'external-bom.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['part','quantity','notes']);w.writerows(external)

begin('YM2203C専用 / 1枚基板 Rev C','160 × 120 mm・2層。I2C＋USB-MIDI入力、FM＋SSGを左右同音のライン出力へ。')
box('I2Cホスト',40,580,205,100,'3.3V SDA/SCL＋GND\n操作用MCUは基板外')
box('PC',40,410,205,100,'USB-MIDI\n音声はAMS-22から録音')
box('Pico 2 ×1',330,400,245,280,'C/C++専用ファームウェア\nI2C0受信・USB-MIDI\n音色・予約・レジスタ管理\nPIO/DMA・PCM変換')
box('YM2203C ×1',675,570,245,110,'4MHz / FM＋SSG\n3.3V⇔5Vレベル変換')
box('AE-PCM5102A',675,400,245,110,'I2S 48kHz / OUTLを使用\nOUTRは未接続')
box('MCP6022 ×1',675,225,245,110,'2.5V基準＋モノラル混合\nFM＋SSG A/B/C')
box('USB-C / POWER',330,225,245,110,'電源専用5V入力\nCC1/CC2各5.1kΩ\nPTC＋ソフトスタート')
arrow(455,335,455,400)
box('ライン出力',990,225,155,110,'ミュート・2連音量\nL/Rは同じ音\nAMS-22 LINE INへ')
arrow(245,630,330,630);arrow(245,460,330,460)
arrow(575,630,675,630);text('並列バス',590,646,10)
arrow(675,590,575,590);text('FMシリアル',585,570,10)
arrow(575,455,675,455);text('I2S',605,470,10)
arrow(795,400,795,335);arrow(920,280,990,280)
C.setStrokeColor(TEAL);C.setLineWidth(2)
C.line(920,625,950,625);C.line(950,625,950,315)
arrow(950,315,920,315);text('SSG',957,440,10)
y=155
y=para('主電源は専用USB-Cからの5V。3.3VはPico 2から供給します。50ピン交換接続・基板ID・MCP23017を省き、音声回路は1段へ統合しました。既製のPico/DAC/レベル変換モジュールを一つの主基板へ載せる構成です。',40,y,W-80,13,21)
para('実機未検証・専用ファームウェア未実装。基板を組み立てるだけで演奏できる段階ではありません。GPIOは2026-10-18に承認済みです。',40,y,W-80,13,21)
end()

begin('GPIOと外部端子','25 GPIOを使用。GP27は予備。番号はGP番号とPico物理端子番号を区別。')
rows=[(p['gpio'],p['pico_pin'],p['signal']) for p in D['gpio']]
y=table(['GP','物理端子','信号'],rows,40,H-115,[55,80,340],rowh=21,size=11)
text('GP27 / 物理32：予備・基板上で未接続',40,y-27,12,TEAL)
x=565;y=H-120
for title,desc in [
 ('JPOWER / USB-C電源専用','秋月113080。D-/D+は未接続。CC1/CC2各5.1kΩ。5V対応の専用USB ACアダプターへ。'),
 ('JHOST / 外部I2C','1=GND、2=SDA、3=SCL、4=GND。3.3V信号のみ。ホストの電源出力は接続しません。'),
 ('RV1 / 基板上2連A10kΩ','1/4=CCW/GND、2/5=左右ワイパー、3/6=CW/音声入力。共通軸で調整。'),
 ('JLINE / 基板上3.5mm TRSジャック','ST-005-G。メーカー端子2=RING、3=SLEEVE、4=TIP（2本）。左右各100Ω。'),
 ('JRUN / リセットスイッチ','1=Pico RUN、2=GND。モーメンタリスイッチで短絡します。'),
 ('Pico 2のUSB端子','PCへ接続するUSB-MIDIデバイス用。DIN MIDI、USBホスト、USB音声出力は含みません。')]:
 text(title,x,y,14,TEAL);y-=25;y=para(desc,x,y,ww:=W-x-40,12,19)-8
para('I2Cアドレス・コマンド、音色プリセット、専用SysEx形式はファームウェア仕様で確定します。I2CとMIDIの同時書き込みは共通キューと制御権の規則で管理します。',40,100,W-80,12,19)
end()

begin('電源・バス・音声の設計方針','安全ゲートを維持。USB-MIDI追加のためのGPIOは不要。主電源USB-Cなしでの演奏は不可。')
x=40;y=H-120;ww=535
text('電源と投入順序',x,y,17,TEAL);y-=29
for s in [
 'JPOWER→PTC 0.5A hold→TPS22918→+5V。+5V→SS14（A=+5V、K=VSYS）→Pico VSYS。Pico VBUS端子は基板上で未接続です。',
 'YM2203C端子で4.75～5.25Vを確認。全体の初期電流予算400mA以下、3.3V外付け負荷200mA以下。5V・1.5A以上のUSB-C ACアダプターと短いケーブルを使用します。',
 '主電源USB-Cを先に接続してからPico USB-MIDI・I2Cを接続。終了は演奏停止・ARM=L、I2CとPico USBを外してから主電源を外します。',
 'Pico USBだけでも3.3V側は起動します。5V喪失検出やI2Cの無給電時分離はないため、活線抜き差しや片側だけの給電で接続しません。']:
 y=para(s,x,y,ww,12,19)
text('1段のモノラル合成',x,y-2,17,TEAL);y-=32
for s in [
 'FMはPCM5102AのOUTLのみ使用。470Ω/2.2nFでフィルターし、SSG A/B/Cと各4.7µF BP・100kΩを介して合成します。',
 'SSG各出力の1kΩ負荷を維持。MCP6022は基準電圧2.5V用と混合用に各1回路。帰還22kΩ/47pF、各入力利得約-0.22です。',
 'CD74HC4053のXでMIX_MONOとVREFを切り替えて消音。AC結合→2連音量→左右各100Ω→AMS-22 LINE IN。最大音量・歪・バランスは実機確認です。']:
 y=para(s,x,y,ww,12,19)
x=640;ww=W-x-40;y=H-120;text('起動時の状態',x,y,17,TEAL);y-=30
for s in ['RESET_N = ARM AND RESET_RELEASE','DAC_XSMT = ARM AND DAC_ALLOW','LINE_RUN = ARM AND LINE_ALLOW',
 'OE_WRITE_N = NOT(ARM AND RD_N)','OE_READ_N = NOT(ARM AND NOT RD_N)']:
 text(s,x,y,13);y-=27
y=para('ARMと各ALLOW/RELEASEにはプルダウン。ARM=Lでリセット、データバッファ無効、ネイティブCS/WR/RD=H、音声ミュートを保持します。',x,y-8,ww,12,19)
text('読み取りへ切り替える順序',x,y-8,17,TEAL);y-=40
for s in ['1. CS/WR=H、Pico D0～7を入力へ。','2. RD=L、バッファ切替待ち、CS=L。','3. 音源アクセス待ち、データを読む。',
 '4. CS=H、音源バス解放待ち、RD=H。','5. バッファ切替待ち後、Picoを出力へ。']:
 y=para(s,x,y,ww,12,19)
para('YM書き込み後はBUSY確認。FMシリアルはI2Sではないため、PIO受信・整数PCM化・48kHzへのレート変換が必要です。USB/I2Cと同時に実機評価します。',x,y-8,ww,12,19)
end()

begin('基板配線・部品配置 / 160 × 120 mm','上面視。赤=表、青=裏、金=パッド。実装部品はすべて上面。GNDベタは視認性のため省略。')
draw_board(NAME,45,180,4.25)
x=775;y=H-125;ww=W-x-35
for title,s in [
 ('A1 / Pico 2','USBコネクタを上側へ。ホスト接続とファームウェア書き込みに使います。'),
 ('U1 / YM2203C','DIP40、列間15.24mm。ソケット推奨。'),
 ('A3 / A4、U2 / U3','書き込み・制御の上り変換と、読み取り・FMの下り変換。'),
 ('U4 / U5 / U6 / U10','ARM安全ゲートとデータバッファ切り替え。'),
 ('X1 / U7','8MHz発振器＋2分周で4MHz。'),
 ('A2 / DAC','AE-PCM5102A DIP化キット。列間15.24mm。外部電源・チャージポンプ用Cが必要。'),
 ('U8 / U9','MCP6022×1で基準電圧と混合、CD74HC4053でライン消音。'),
 ('JPOWER / RV1 / JLINE','USB-C電源入力、基板上2連音量、基板上TRS。操作口は下辺へ。')]:
 text(title,x,y,13,TEAL);y-=23;y=para(s,x,y,ww,11,18)-3
para('M3穴：左上原点で(5,5)、(155,5)、(5,115)、(155,115)mm。穴径3.2mm。現物寸法・USB挿抜空間・部品の1番端子を発注前に照合してください。',45,115,W-90,12,19)
end()

begin('部品と組み立て・通電手順','部品表CSVは位置・フットプリント・販売元／資料リンクを含みます。')
items=[('Pico 2','1','A1 / メスソケット2列'),('YM2203C','1','U1 / DIP40 600milソケット'),
 ('AE-PCM5102A DIP化キット','1','A2 / 列間15.24mm'),('AE-LLCNV-LVC8T245','2','A3/A4 / 列間15.24mm'),
 ('74LCX245FT','2','U2/U3 / TSSOP20 0.65mm直接実装'),('MCP6022-I/P','1','U8 / 基準電圧＋混合'),
 ('TC74HC04/00/32/74/08AP','各1','DIP14 / ソケット推奨'),('CD74HC4053E / MMBT3904','各1','ミュート / DIP16・SOT23'),
 ('KOA RKC B回路集合抵抗','6','8素子10k×3、4素子10k×2、8素子1k×1'),
 ('RK0971220-F15-C0-A103','1','RV1 / 秋月103604、基板上2連A10kΩ'),
 ('ST-005-G','1','JLINE / 秋月102460、基板上3.5mm TRS'),
 ('AE-USB2.0-TYPE-C / TPS22918DBVR','各1','JPOWER / 秋月113080、U11 / SOT-23-6')]
y=table(['主要部品','数量','実装'],items,40,H-115,[390,90,620],rowh=25,size=12)-27
text('基板外の部品',40,y,16,TEAL);y-=27
y=para('6mm Dカット用ノブ、5V対応USB-C ACアダプター、ソケット、M3スペーサー、USB/TRSケーブル、AMS-22。I2C使用時は外部ホスト。詳細はexternal-bom.csv。',40,y,W-80,12,19)
text('段階的に実装・確認する',40,y-2,16,TEAL);y-=31
for s in ['1. 電源OFFで短絡・極性・ソケットの向きを確認。まずUSB-C電源部のみ実装して5V/3.3V・突入電流を測定。',
 '2. ロジックを実装し、ARM=Lでリセット・バッファ無効・ミュートを確認。',
 '3. YM未実装で無音I2S、DAC単音、2.5V基準、ミュート、音量、出力DCを確認。',
 '4. 全電源OFFでYMを挿し、負荷時電圧、4MHz、BUSY読み取り、SSG単音を確認。',
 '5. FM受信・PCM化を確認し、FM＋SSGをAMS-22で録音。Mac/WindowsのMIDI認識とI2C同時動作へ進む。']:
 y=para(s,40,y,W-80,12,19)
para('R/Cは主に1206。U11はSOT-23-6。4.7µFは無極性品。ラジアル品の径・リードピッチと既製モジュールの実寸を確認します。GNDベタは直接接続なので手はんだの熱容量を確保してください。',40,y,W-80,12,19)
end()

begin('検証結果・製造仕様・一次資料','設計ルール検査と実機の動作確認を区別します。実機未検証・専用ファームウェア未実装。')
r=CHECK
rows=[('ERC エラー / 警告','0 / 0'),('DRC エラー / 警告','0 / 0'),('未配線 / 回路図不一致','0 / 0'),
 ('GPIO / 予備','25 / GP27'),('物理オブジェクト / 電気ネット',f"{r['physical_objects']} / {r['electrical_nets']}"),
 ('配線区間 / ビア',f"{r['track_segments']} / {r['vias']}")]
y=table(['検査項目','結果'],rows,40,H-115,[390,260],rowh=27,size=12)
para('製造仕様：160×120mm、2層FR-4、厚さ1.6mm、銅箔35µm。最小配線0.18mm、最小間隔0.20mm、ビア径0.7mm・穴0.3mm。面付けなし。緑レジスト・白シルク・鉛フリーHASLを初期候補とします。',740,H-125,400,12,19)
y-=30
y=para('照合済み：全回路図ピンとPCBパッド、承認済みGPIO、YM/変換モジュール/DACの端子番号、電源経路・ダイオード極性、ARMゲート、MCP6022×1、左右各100Ω、SOT23の向き、部品干渉・基板端の取付条件、電源端子付近のC配置。',40,y,W-80,12,19)
y=para('残る確認：購入品の寸法・ソケット、負荷時電圧・電流、USB-MIDI/I2Cファームウェア、FM取り込み・レート変換、実ICの過渡タイミング、FM/SSGバランス・ヘッドルーム・ノイズ・ポップ音。',40,y,W-80,12,19)
text('一次資料（リンク）',40,y-5,16,TEAL);y-=34
sources=[('Pico 2','https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf'),
 ('YM2203','https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf'),
 ('AE-LLCNV回路図','https://akizukidenshi.com/goodsaffix/AE-LLCNV-LVC8T245_sch_20210113.pdf'),
 ('PCM5102A','https://www.ti.com/lit/ds/symlink/pcm5102a.pdf'),
 ('MCP6022','https://akizukidenshi.com/goodsaffix/MCP6022.pdf'),
 ('CD74HC4053','https://www.ti.com/lit/ds/symlink/cd74hc4053.pdf'),
 ('74LCX245FT','https://akizukidenshi.com/goodsaffix/74LCX245FT_datasheet_ja_20150130.pdf'),
 ('AMS-22','https://zoomcorp.com/manuals/ams-22-ja/'),
 ('TinyUSB MIDI','https://docs.tinyusb.org/en/latest/examples/device/midi_test.html')]
for label,url in sources:
 text(label,45,y,11,TEAL);text(url,280,y,9);C.linkURL(url,(40,y-3,W-40,y+13),relative=0);y-=23
para('以降は搭載部品の穴位置図とKiCad出力のA0回路図。ZIPはKiCad編集データとライブラリ一式、部品表、GPIO表、検査結果、ガーバー、生成元を含みます。ガーバーのみの入稿ZIPも別途用意しました。',40,y-8,W-80,12,19)
end()

begin('基板搭載ボリューム・LINEジャック',
      '上面視。下辺が操作面。図中の端子番号は各部品の電気端子番号。音声部はRev Bと同じ。電源は次ページ参照。')
text('RV1 / ALPS RK0971220-F15-C0-A103',40,H-125,17,TEAL)
C.linkURL('https://akizukidenshi.com/goodsaffix/RK0971220-F15-C0-A103.pdf',(40,H-130,580,H-105),relative=0)
para('秋月103604。2連A10kΩ、6mm Dカット軸。前面・軸中心=(96,118.5)mm。両連へ同じモノラル信号を入力し、左右のワイパーは分離します。',40,H-153,535,12,19)
text('JLINE / Switronic ST-005-G',650,H-125,17,TEAL)
C.linkURL('https://akizukidenshi.com/goodsaffix/ST-005-G.pdf',(650,H-130,1140,H-105),relative=0)
para('秋月102460。3.5mm TRS。口中心=(145,120)mmで基板端に揃えます。メーカー端子2=RING、3=SLEEVE、4=TIP（2本）。図面の1は樹脂部品です。',650,H-153,490,12,19)

def mech(origin_x,origin_y,kind):
    scale=12
    def point(x,y):return (origin_x+x*scale,origin_y-y*scale)
    def rect(bb):
        x1,y1,x2,y2=bb;xx,yy=point(x1,y2)
        C.setStrokeColor(TEAL);C.setFillColor(LIGHT);C.rect(xx,yy,(x2-x1)*scale,(y2-y1)*scale,fill=1,stroke=1)
    def hole(n,x,y,drill):
        xx,yy=point(x,y);C.setStrokeColor(INK);C.setFillColor(white);C.circle(xx,yy,drill*scale/2,fill=1,stroke=1)
        text(n,xx-3,yy+12,10)
    if kind=='pot':
        rect([-4.75,-9.55,4.75,0]);rect([-3,0,3,15])
        for row,y in enumerate([-5,-7.5]):
            for col,x in enumerate([-2.5,0,2.5]):hole(str(row*3+col+1),x,y,1)
        text('BODY 9.5 x 9.55 mm',origin_x-90,origin_y+145,11)
        text('shaft 15 mm',origin_x+45,origin_y-125,10)
        by=origin_y-1.5*scale
    else:
        rect([-3.25,-14,3.25,0])
        for n,x,y in [('4',-2.9,-3.5),('4',2.9,-3.5),('2',-2.25,-11),('3',2.25,-11)]:hole(n,x,y,1.2)
        for x in [-2.5,2.5]:hole('NPTH',x,-7,1)
        text('BODY 6.5 x 14 mm',origin_x-90,origin_y+195,11)
        by=origin_y
    C.setStrokeColor(INK);C.setDash(4,3);C.line(origin_x-145,by,origin_x+145,by);C.setDash()
    text('PCB edge / Y=120 mm',origin_x-145,by-20,10)
mech(280,405,'pot');mech(900,350,'jack')
table(['RV1 端子','基板座標 X, Y (mm)','接続'],[
 ('1 / 4','93.5,113.5 / 93.5,111','CCW / GND'),
 ('2 / 5','96,113.5 / 96,111','WIPER L / R'),
 ('3 / 6','98.5,113.5 / 98.5,111','CW / OUT_AC')],40,200,[95,290,180],rowh=23,size=10)
table(['JLINE 端子','基板座標 X, Y (mm)','接続'],[
 ('2 / 3','142.75,109 / 147.25,109','RING / SLEEVE'),
 ('4 x2','142.1,116.5 / 147.9,116.5','TIP'),
 ('NPTH x2','142.5,113 / 147.5,113','位置決め穴')],650,200,[100,270,140],rowh=23,size=10)
para('穴径：RV1=1.0mm、JLINE信号=1.2mm・位置決め=1.0mm。軸・ブッシングは基板外へ突出。ケース穴の高さ、板厚、ナットとノブ、プラグ挿抜空間を現物照合してください。2連ボリュームの連動誤差は左右の音量差になります。',40,88,W-80,11,17)
end()

begin('電源専用USB-C / Rev C','JPOWERは電源入力、Pico 2のUSBはMIDI。GPIOは変更なし。5V以外を要求するPD通信は行いません。')
x=40;y=H-125
text('JPOWER / 秋月113080 AE-USB2.0-TYPE-C',x,y,17,TEAL);y-=30
y=para('モジュールは180度回転して上面へ搭載し、挿入口を基板下辺へ向けます。CN2の7ピンと前側VBUS/GND各2ピンを直ピンヘッダではんだ固定。D-/D+は未接続です。',x,y,535,12,19)
y=table(['CN2端子','機能','接続'],[
 ('1','VBUS','F1 → U11 → +5V'),('2 / 3','D- / D+','未接続'),('4 / 7','GND','基板GND'),
 ('5','CC1','R26 5.1kΩ → GND'),('6','CC2','R27 5.1kΩ → GND')],x,y,[100,130,305],rowh=25,size=11)-24
y=para('CC1とCC2は各5.1kΩ・1%で個別にGNDへ接続。両CCを短絡しません。USB-Cから5Vを受け取ります。供給可能電流の自動判定、USB列挙、BC1.2判定はありません。',x,y,535,12,19)
text('供給電源と接続順',x,y-3,17,TEAL);y-=34
for s in [
 '5Vで1.5A以上を供給できるUSB-C ACアダプターと、短く低抵抗のC-Cケーブルを使用。PCやハブの汎用データポートからの給電は対象外です。',
 '主電源USB-C → Pico USB-MIDI・I2Cの順に接続。終了時は停止・ARM=L、I2CとPico USBを外してから主電源を外します。',
 'Pico USBだけでは音源側5Vを供給できません。両USBの同時接続時もD1でPico VSYSから主電源への逆流経路を遮断します。']:
 y=para(s,x,y,535,12,19)

x=650;y=H-125;text('TPS22918で立ち上がりを緩やかにする',x,y,17,TEAL);y-=31
for s in [
 'VBUS → PTC 0.5A hold → USB_FUSED → U11 → +5V。U11はON=VIN、QOD未接続、入力C32=1µF、CTのC33=10nF・25V以上X7R。',
 '5Vでの10～90%立ち上がりは典型約26.6ms。既存の47µF等をスイッチ後段へ置き、充電時の突入電流を抑えます。電流制限・逆流遮断・過電圧保護の機能ではありません。',
 '基板全体400mA以下、3.3V外付け負荷200mA以下を初期予算とします。USBケーブルやPTCの電圧降下を含め、YM端子で4.75～5.25Vを確認します。']:
 y=para(s,x,y,W-x-40,12,19)
text('モジュールの実装穴 / 上面視',x,y-3,17,TEAL);y-=35
for s in [
 'CN2の端子1=(40.62,108.34)mm。端子7へ向かいXを2.54mmずつ減らす。穴径1.02mm。',
 '支持ピン：VBUSはX=40.62、GNDはX=25.38。各2本はY=115.96/118.5mm。CN2の1/7と同じネットです。',
 'モジュール外形20×12.46mm、前端Y=118.9mm。裏面と主基板の隙間・挿抜空間・コネクタ突出量を現物照合。端切れが残る場合はメーカー指示どおり除去します。',
 'CC端子のない2ピンUSB-C部品（秋月116895/117123）は代用できません。']:
 y=para(s,x,y,W-x-40,12,19)
text('一次資料（リンク）',40,140,14,TEAL)
for i,(label,url) in enumerate([
 ('USB-Cモジュール回路図','https://akizukidenshi.com/goodsaffix/AE-USB2.0-TYPE-C_sch.pdf'),
 ('USB-Cモジュール寸法図','https://akizukidenshi.com/goodsaffix/AE-USB2.0-TYPE-C_dimm_20190206.pdf'),
 ('USB-Cから電源を取る','https://akizukidenshi.com/goodsaffix/powered_by_type-c.pdf'),
 ('TPS22918データシート','https://www.ti.com/lit/ds/symlink/tps22918.pdf')]):
 yy=115-i*17;text(label,40,yy,10,TEAL);text(url,285,yy,9);C.linkURL(url,(40,yy-3,W-40,yy+12),relative=0)
end();C.save()

writer=PdfWriter()
for p in [PDFDIR/'guide-body.pdf',BOARD/(NAME+'-schematic.pdf')]:writer.append(str(p))
writer.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
final=PDFDIR/'ym2203-single-board-rev-c.pdf'
with final.open('wb') as f:writer.write(f)
assert len(PdfReader(final).pages)==9
# Normalize diagnostic source paths before packaging; circuit connections do not change.
repo=str(ROOT.parent.parent)
for fn in ['erc.json','drc.json','netlist.xml',NAME+'.dsn']:
 p=BOARD/fn;s=p.read_text().replace(str(ROOT),'${DESIGN_ROOT}').replace(repo,'${REPOSITORY}');p.write_text(s)

gerbers=sorted(p for p in (BOARD/'gerbers').iterdir() if p.is_file())
required={NAME+'-F_Cu.gtl',NAME+'-B_Cu.gbl',NAME+'-F_Mask.gts',NAME+'-B_Mask.gbs',NAME+'-F_Silkscreen.gto',NAME+'-B_Silkscreen.gbo',NAME+'-Edge_Cuts.gm1',NAME+'-PTH.drl',NAME+'-NPTH.drl'}
assert required<={p.name for p in gerbers}
fab=ROOT/'output/ym2203-single-board-rev-c-gerbers.zip'
with zipfile.ZipFile(fab,'w',zipfile.ZIP_DEFLATED) as z:
 for p in gerbers:z.write(p,p.name)
files=[ROOT/f for f in ['README.md','cad.py','generate.py','build_pcb.py','finish_pcb.py','verify.py','make_docs.py']]
files += [p for p in OUT.rglob('*') if p.is_file() and not p.name.endswith(('.kicad_prl','.DS_Store','-schematic.pdf')) and '-backups' not in str(p)]
files += [final,fab]
archive=ROOT/'output/ym2203-single-board-rev-c.zip';manifest=[]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):
  rel=str(p.relative_to(ROOT));z.write(p,rel);manifest.append(dict(path=rel,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
 z.writestr('SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
for p in [fab,archive]:
 with zipfile.ZipFile(p) as z:assert z.testzip() is None
print(json.dumps(dict(pdf=str(final),pages=9,gerbers=str(fab),zip=str(archive),files=len(manifest)),ensure_ascii=False))
