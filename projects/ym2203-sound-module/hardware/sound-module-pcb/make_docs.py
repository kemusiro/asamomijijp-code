"""Render the checked PCB package as a Japanese design review PDF and ZIP.

Requires reportlab and pypdf. Read README for the intended prototype scope.
"""
from pathlib import Path
import json, math, os, zipfile, hashlib, csv, shutil
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import A3, landscape
from pypdf import PdfReader, PdfWriter

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'rev-a';PDFDIR=ROOT/'output/pdf';PDFDIR.mkdir(parents=True,exist_ok=True)
D=json.loads((OUT/'design.json').read_text());CHECK=json.loads((OUT/'verification.json').read_text())
assert CHECK['result']=='pass'
refs=ROOT/'reference';refs.mkdir(exist_ok=True)
shutil.copyfile(ROOT.parent/'sound-module-platform/memory.md',refs/'adpcm-memory-notes.md')
external=[
    ('操作用Pico 2',1,'MicroPython。ベース外、別USB給電。'),
    ('1x20 2.54mmメスソケット',2,'音源用Pico 2の着脱用。'),
    ('1x10 2.54mmメスソケット',2,'AE-PCM5102Aの着脱用。'),
    ('1x12 2.54mmメスソケット',4,'AE-LLCNV 2個の着脱用。'),
    ('DIP8 300milソケット',3,'MCP6022 3個。'),
    ('DIP14 300milソケット',5,'HC08/04/00/32/74。'),
    ('DIP16 300milソケット',1,'CD74HC4053。'),
    ('DIP28 300milソケット',1,'MCP23017。'),
    ('DIP40 600milソケット',1,'YM2203C。'),
    ('二連10kΩ Aカーブボリューム',1,'左右独立。JVOLへHIGH/WIPER/LOWを接続。'),
    ('3.5mmステレオジャックモジュール',1,'JLINE L/R/GNDへ。AE-PHONE-JACK-DIP等。'),
    ('JMOD 50番接点の絶縁キー',1,'メス側を塞ぎ、オス50番を抜く。'),
    ('M3 絶縁スペーサー 19mm',4,'基板対向面の間隔を19mmに保持。ワッシャー調整でも可。'),
    ('M3絶縁ねじ・ナット',8,'取り付け方法に合わせて用意。'),
    ('USBケーブル',2,'2台のPico用。'),
    ('ステレオTRSケーブル',1,'ライン出力からAMS-22 LINE INへ。'),
    ('ZOOM AMS-22',1,'PC録音・モニター用。'),
    ('接続用ワイヤー／コネクター',1,'ホストI2C、音量、ジャック接続用の一式。'),
    ('安定化DC 5V電源',1,'主電源として必須。定格1A以上を候補とする。基板はPTC 0.5A hold、初期予算400mA以下。')]
with (OUT/'external-bom.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['part','quantity','notes']);w.writerows(external)
font=os.environ.get('PDF_JAPANESE_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
pdfmetrics.registerFont(TTFont('JP',font))
W,H=landscape(A3);NAVY=HexColor('#15283f');INK=HexColor('#20364a');TEAL=HexColor('#087f83');LIGHT=HexColor('#eaf2f5')
C=canvas.Canvas(str(PDFDIR/'guide-body.pdf'),pagesize=(W,H))
C.setTitle('交換式サウンドモジュール PCB設計 Rev A');C.setAuthor('MicroPython WebLab contributors')
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
    text('SOUND MODULE PLATFORM  /  REV A  /  2026-10-18',35,24,9)
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


begin('共通ベース基板 ＋ 交換式音源基板','最初の製作対象：共通ベース＋YM2203C。専用ファームウェアと実機確認は次工程。')
box('操作用 Pico 2',40,570,220,100,'外部 / MicroPython\nGP0 SDA・GP1 SCL・GND')
box('共通ベース 180 × 160 mm',335,335,450,370,'音源用 Pico 2 / C・C++\nMCP23017・安全制御\nAE-PCM5102A DIP化キット\nMCP6022 × 2・左右ミキサー\nアナログミュート・音量端子')
box('交換基板 130 × 120 mm',870,550,270,155,'YM2203C / 4 MHz / ID=001\nレベル変換・クロック・SSG混合\n基板下面の50ピンで接続')
arrow(260,620,335,620);text('3.3V I2C',266,635,10)
arrow(785,625,870,625);text('50ピン',799,642,10)
box('ZOOM AMS-22',870,355,270,110,'3.5mmステレオ LINE IN\nUSBでPCへ録音')
arrow(785,410,870,410);text('TRS',806,426,10)
box('外部 安定化DC 5V',40,370,220,120,'主電源として必須 / JPOWERへ\n3.3Vは音源用Picoから供給')
arrow(260,425,335,425)
y=265
y=para('ブレッドボードの多数の配線を基板へ置き換え、音源の交換時はコネクタ1組と固定ねじで扱う構成です。音源ICの5V信号は交換基板内で3.3Vへ変換します。',40,y,W-80,14,22)
y=para('既定のDAC・MCP6022・AMS-22を維持し、将来のステレオ音源に備えて左右を独立させました。集合抵抗は合計8個。ピン数の多い部分を優先して配線を減らしています。',40,y,W-80,14,22)
para('本資料は試作Rev Aです。部品の現物寸法とキー加工を照合し、段階的な通電試験を行ってください。ほかの5種類の交換基板は、共通コネクタへの信号収容までです。',40,y,W-80,13,21)
end()

begin('承認済みGPIO ＋ 50ピン共通接点','GPIOは2026-10-18承認済み。番号はPicoのGP番号と物理端子番号を区別。')
rows=[(x['gpio'],x['pico_pin'],x['signal']) for x in D['gpio']]
table(['GP','物理端子','信号'],rows,40,H-115,[58,75,330],rowh=21,size=10)
con={x['pin']:x['signal'] or 'NC' for x in D['connector']}
rows=[(i,con[i],i+1,con[i+1]) for i in range(1,51,2)]
table(['奇数','信号','偶数','信号'],rows,550,H-115,[48,215,48,215],rowh=21,size=9)
y=H-710
para('内部I2C1：MCP23017 @ 0x20。GPA0=RESET_RELEASE、GPA1=LINE_ALLOW、GPA3=DAC_ALLOW、GPA4/5=AUX0/1。GPB0～2=ID、GPB3=PRESENT_N。',40,y,W-80,12,20)
para('GPB4～6はGND固定の入力。GPA7/GPB7は出力設定。外部ホストと内部補助I2Cは接続しません。コネクタ50番はキー用NCです。',40,y-59,W-80,12,20)
end()

begin('電源・バス・ミュートの回路方針','前回のYM2203専用割り当てから共通版へ移行。高速処理は直接GPIO、低速制御はエキスパンダー。')
left=40;right=625;ww=520;y=H-120
text('電源',left,y,18,TEAL);y-=31
for s in [
    '外部安定化DC 5Vが主電源。JPOWER 1=+5V入力、2=GND。電源選択ジャンパーとUSBから主電源への配線は廃止。',
    '外部5V→PTC→+5V→SS14→Pico VSYS。SS14はUSBから主電源への逆流を防止。逆極性・過電圧保護はありません。',
    'YM端子で4.75～5.25Vを確認。PTC 0.5A hold、初期予算400mA以下。\n3.3V外付け負荷は合計200mA以下。',
    'ホストPicoは別USB。接続はGND/SDA/SCLのみ。無給電時のI2C分離回路はないので、片側だけの給電で接続しません。',
    '外部5Vを先に投入し、その後USB・ホストI2Cを接続。終了はARM=L、I2C・USBを外してから外部5Vを切ります。USBのみでも3.3V側は起動しますが演奏不可。5V喪失検出はありません。']:
    y=para(s,left,y,ww,12,19)
text('音声',left,y-4,18,TEAL);y-=35
for s in [
    '左右それぞれ、FMと交換基板アナログ音声を100kΩ入力・22kΩ帰還で合成。MCP6022は5V単電源、基準電圧2.5Vです。',
    'SSG A/B/Cには1kΩのDC負荷を置き、カード上で合成します。負荷値・相対音量・極性は実機で調整します。',
    'CD74HC4053で混合後の出力をVREFへ切り替えて消音。DACのXSMTだけではSSGを消音できません。',
    '音量は外付け二連10kΩ Aカーブ。出力はAMS-22 LINE IN用で、スピーカー電力アンプは載せません。']:
    y=para(s,left,y,ww,12,19)
y=H-120;text('起動時のハードウェアゲート',right,y,18,TEAL);y-=32
for s in ['RESET_N = ARM AND RESET_RELEASE','DAC_XSMT = ARM AND DAC_ALLOW','LINE_RUN = ARM AND LINE_ALLOW',
          'OE_WRITE_N = NOT(ARM AND RD_N)','OE_READ_N = NOT(ARM AND NOT RD_N)']:
    text(s,right,y,13);y-=26
y=para('ARM=Lでバスを無効化、CS/WR/RDをH、リセットをL、音声をミュートに保ちます。Picoリセット中も外付け抵抗でARM=Lになります。',right,y-7,ww,12,19)
text('読み取りへ切り替える順序',right,y-8,18,TEAL);y-=40
for s in ['1. CS/WRをH、PicoのD0～7を入力へ。','2. RD=L、バッファ切替待ち、CS=L。',
          '3. 音源のアクセス時間を待って読み取り。','4. CS=H、音源のバス解放待ち、RD=H。',
          '5. バッファ待ちの後、Picoを出力へ戻す。']:
    y=para(s,right,y,ww,12,19)
para('初期切替待ちは1µs以上から測定。YMの書き込み後はBUSYを確認します。組み合わせ論理の安定状態だけで、過渡時の競合が無いと断定しません。',right,y-8,ww,12,19)
end()

for name,title,scale in [('base','共通ベース基板',3.5),('ym2203','YM2203C交換基板',4.5)]:
    begin(title+' / 配線・部品配置','上面から見た両面配線の重ね表示。赤=表、青=裏、金=パッド。GNDベタは視認性のため省略。')
    draw_board(name,45,130,scale)
    x=735;y=H-130;ww=W-x-35
    if name=='base':
        notes=[('A1','音源用Pico 2。USBコネクタを上側に向けて実装。'),
               ('U1 / U2','MCP23017とハードウェア安全ゲート。'),
               ('JMOD','上面の嵩上げソケット。50番を絶縁キーで塞ぐ。'),
               ('A2','AE-PCM5102A DIP化キット。外部電源・チャージポンプ用Cが必要。'),
               ('U3 / U4 / U5','2.5V基準、左右ミキサー、アナログミュート。'),
               ('JPOWER / F1 / D1','外部安定化5V入力、PTC、VSYSへの逆流防止。Pico VBUS端子は基板上で未接続。'),
               ('JVOL / JLINE','二連ボリュームとTRSジャックは基板外へ。')]
    else:
        notes=[('U1','YM2203C DIP40、列間15.24mm。ソケット推奨。'),
               ('A1 / A2','既製LVC8T245モジュール。データ書き込み／制御の上り変換。'),
               ('U2 / U3','74LCX245FT、0.65mm TSSOP20。読み取り／FMの下り変換。'),
               ('U4 / U5 / U6','3.3V HCロジック。データ方向とCS/WR/RDの無効化。'),
               ('X1 / U7','8MHz発振器と2分周で4MHzを生成。'),
               ('U8 / RN3','SSG合成と1kΩ負荷。FMシリアルはPicoでPCMへ変換。'),
               ('JMOD','基板下面へオスを実装。50番接点を抜く。ID=001。')]
    for heading,s in notes:
        text(heading,x,y,13,TEAL);y-=23;y=para(s,x,y,ww,12,19)
    text('チェック用テストポイント',x,y-2,13,TEAL);y-=27
    targets=[p for p in D['boards'][name]['parts'] if p['ref'].startswith('TP')]
    for p in targets:
        text(p['ref']+'  '+p['value'],x,y,10);y-=18
    end()

begin('組み立てと外部部品','実装前に、発注した現物とフットプリントの列間・端子番号・背丈を照合。')
y=H-120
items=[('Pico 2','ベース ×1','操作用の別Pico 2は基板外'),
       ('AE-PCM5102A','ベース ×1','列間15.24mmのDIP化キット'),
       ('MCP23017-E/SP','ベース ×1','SPDIP28 / 列間7.62mm'),
       ('MCP6022-I/P','ベース ×2、カード ×1','DIP8 / 列間7.62mm'),
       ('AE-LLCNV-LVC8T245','カード ×2','既製24ピン / 列間15.24mm'),
       ('74LCX245FT','カード ×2','TSSOP20 / 0.65mm直接実装'),
       ('YM2203C','カード ×1','DIP40 / 列間15.24mm'),
       ('10kΩ集合抵抗','8素子 ×3、4素子 ×4','KOA RKC B回路、1番共通'),
       ('1kΩ集合抵抗','8素子 ×1','SSG負荷に3素子使用'),
       ('その他','各基板のbom.csv','1206 R/C、HCロジック、クロック、電源部品')]
y=table(['部品','数量','実装・用途'],items,40,y,[300,270,530],rowh=28,size=12)
y-=35
text('コネクタと固定',40,y,17,TEAL);y-=28
y=para('ベース：ESQ-125-58-L-D（高さ16.13mm）。交換基板：TSW-125-07-L-D。対向面間19mmで挿入長5.51mm。メーカーの許容挿入範囲3.68～6.35mm内です。',40,y,W-80,13,21)
y=para('オス50番の接点抜きとメス50番の絶縁キーが必要です。四つの非対称M3穴を19mmスペーサーで固定します。交換基板の下面から見る端子位置は上面視と逆になります。',40,y,W-80,13,21)
text('基板外で別途用意するもの',40,y-8,17,TEAL);y-=39
y=para('操作用Pico 2、安定化DC 5V電源、二連10kΩ Aカーブボリューム、3.5mmステレオジャック、M3スペーサー・ねじ、USBケーブル、AMS-22とステレオTRSケーブル。DIPソケット・Pico用ソケットも必要です。',40,y,W-80,13,21)
para('GNDベタは直接接続です。手はんだ時は、基板を損傷しない範囲で十分な熱容量を使って接合を確認してください。電源を入れたまま交換しないでください。',40,y,W-80,13,21)
end()

begin('実機検証の順番 ＋ 将来の交換基板','設計ルールの検査と実機での動作確認を区別。各段階で電圧・波形を測定。')
y=H-120
steps=[('1','ICを挿す前','電源間の短絡、JMOD全接点、キー方向を導通確認。'),
       ('2','ベース電源','外部5Vの極性、5V/3.3V/2.5V、起動電流を確認。'),
       ('3','起動状態','ARM=L、RESET=L、DAC/ラインミュートを確認。'),
       ('4','DAC単独','無音I2S→左右テスト音→ミュート・音量を確認。'),
       ('5','YMカード','全電源OFFで装着し、電圧・4MHz・ID=001を確認。'),
       ('6','SSG','BUSY/レジスターアクセス、各チャネル単音を確認。'),
       ('7','FM','SD/CLK/SHを観測してPIO/DMAとI2S変換を検証。'),
       ('8','同時再生','FM+SSG、最大音量、左右、停止・リセットを録音。'),
       ('9','連続運転','FIFOエラーを記録し、負荷と長時間再生を評価。')]
y=table(['段階','対象','確認内容'],steps,40,y,[60,210,830],rowh=28,size=12)-32
profiles=[('001','YM2203C','今回の回路図・PCBあり。専用ファームウェアは未実装。'),
          ('010','YM2608','A1/SH2/SSGを収容。ADPCMのDRAMアクセス変換は別設計。'),
          ('011','YM2610','FMステレオを収容。ADPCM-A/B別メモリとローダーが必要。'),
          ('100','SN76489AN','READYとアナログを収容。データのビット順はTI表記を反転。'),
          ('101','YMZ285','PLAYとアナログを収容。任意PCM再生は内蔵OTP条件に依存。'),
          ('110','YMZ294','A0/RESETを収容。クロック・TEST等の5V処理はカード内。')]
table(['ID','音源','現在の範囲と残作業'],profiles,40,y,[60,210,830],rowh=29,size=11)
para('ファームウェアは音源別。PIO受信、PCM変換、48kHzへのレート変換、I2C受信、予約演奏キューを別途実装します。現時点で「基板に実装すれば鳴る」段階ではありません。',40,115,W-80,12,20)
end()

begin('検証結果と一次資料','ネイティブKiCad検査・接点座標照合を実施。実機通電・録音は未実施。')
rows=[]
for name,title in [('base','共通ベース'),('ym2203','YM2203Cカード')]:
    r=CHECK['boards'][name]
    rows.append((title,r['physical_parts'],r['electrical_nets'],r['track_segments'],r['vias'],'0 / 0','0 / 0','0'))
y=table(['基板','部品','ネット','配線区間','ビア','ERC 誤/警','DRC 誤/警','未配線'],rows,40,H-120,
        [205,70,80,110,80,150,150,150],rowh=30,size=12)-25
y=para('全26 GPIO、50接点の嵌合座標、4固定穴の一致、全回路図ピンと全PCBパッドのネット一致、ネイティブ端子番号、ARMの論理、電源端子に対するバイパスCの配置を照合しました。',40,y,W-80,13,21)
y=para('残る確認：購入部品の寸法・キー加工、消費電流と電圧降下、実ICの過渡タイミング、音声受信ファームウェア、相対極性・ヘッドルーム・ノイズ・ポップ音。ADPCM回路とほかの交換基板5種は未設計です。',40,y,W-80,13,21)
text('メーカー資料・メーカー配布資料（リンク）',40,y-4,17,TEAL);y-=33
sources=[('Raspberry Pi Pico 2','https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf'),
         ('Yamaha YM2203','https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf'),
         ('Yamaha YM2149 / SSG負荷条件','https://www.bitsavers.org/components/yamaha/YM2149_199209.pdf'),
         ('TI PCM5102A','https://www.ti.com/lit/ds/symlink/pcm5102a.pdf'),
         ('Microchip MCP23017','https://akizukidenshi.com/goodsaffix/MCP23017-Data-Sheet-DS20001952.pdf'),
         ('Microchip MCP6022','https://akizukidenshi.com/goodsaffix/MCP6022.pdf'),
         ('TI CD74HC4053','https://www.ti.com/lit/ds/symlink/cd74hc4053.pdf'),
         ('Toshiba 74LCX245FT','https://akizukidenshi.com/goodsaffix/74LCX245FT_datasheet_ja_20150130.pdf'),
         ('秋月 LVC8T245モジュール回路図','https://akizukidenshi.com/goodsaffix/AE-LLCNV-LVC8T245_sch_20210113.pdf'),
         ('Samtec ESQ','https://suddendocs.samtec.com/catalog_english/esq_th.pdf'),
         ('Samtec TSW','https://suddendocs.samtec.com/catalog_english/tsw_th.pdf'),
         ('KOA RKC集合抵抗','https://akizukidenshi.com/goodsaffix/rkc.pdf')]
for label,url in sources:
    text(label,45,y,11,TEAL);text(url,365,y,9)
    C.linkURL(url,(40,y-3,W-45,y+13),relative=0);y-=24
para('続く2ページはKiCadから出力したA0判の回路図です。PDFを拡大して端子番号・抵抗値・接続ラベルを確認できます。ネイティブ編集データと検査結果はZIPに収録しています。',40,y-12,W-80,12,20)
end()
C.save()

writer=PdfWriter()
for source in [PDFDIR/'guide-body.pdf',OUT/'base/base-schematic.pdf',OUT/'ym2203/ym2203-schematic.pdf']:
    writer.append(str(source))
writer.compress_identical_objects(remove_duplicates=True,remove_unreferenced=True)
final=PDFDIR/'sound-module-platform-rev-a.pdf'
with final.open('wb') as f:writer.write(f)
assert len(PdfReader(final).pages)==10

# Remove machine-specific source paths from diagnostic artifacts, not connections.
repo=str(ROOT.parent.parent)
for folder in [OUT/'base',OUT/'ym2203']:
    for fn in ['erc.json','drc.json','netlist.xml',folder.name+'.dsn']:
        p=folder/fn
        s=p.read_text();s=s.replace(repo,'${REPOSITORY}')
        s=s.replace(str(ROOT),'${DESIGN_ROOT}')
        p.write_text(s)

archive=ROOT/'output/sound-module-platform-rev-a.zip'
files=[ROOT/'README.md',ROOT/'generate.py',ROOT/'build_pcb.py',ROOT/'finish_pcb.py',ROOT/'verify.py',ROOT/'make_docs.py']
files += [refs/'adpcm-memory-notes.md']
files += [p for p in OUT.rglob('*') if p.is_file() and not p.name.endswith(('.kicad_prl','.DS_Store','-schematic.pdf')) and '-backups' not in str(p)]
files += [final]
manifest=[]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(files):
        rel=str(p.relative_to(ROOT));z.write(p,rel)
        manifest.append(dict(path=rel,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
    z.writestr('SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps(dict(pdf=str(final),pages=len(PdfReader(final).pages),zip=str(archive),files=len(manifest)),ensure_ascii=False))
