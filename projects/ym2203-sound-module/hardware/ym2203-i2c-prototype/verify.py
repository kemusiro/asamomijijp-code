"""Verify the exported KiCad connectivity, publish a local review page, bundle files."""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
import csv
import hashlib
import html
import json
import xml.etree.ElementTree as ET
import zipfile
import importlib.util
import sys
import subprocess

ROOT = Path(__file__).resolve().parent
design = json.loads((ROOT/'design.json').read_text())
parts = design['parts']
expected = defaultdict(set)
for part in parts:
    for number, function, net, typ in part['pins']:
        if net is not None: expected[net].add((part['ref'],number))
tree = ET.parse(ROOT/'netlist.xml')
actual = {net.attrib['name'].removeprefix('/'): {(n.attrib['ref'],n.attrib['pin']) for n in net.findall('node')}
          for net in tree.findall('./nets/net')}
assert len(tree.findall('./components/comp')) == len(parts)
for name,pins in expected.items(): assert actual[name] == pins, (name,pins,actual.get(name))
for name,pins in actual.items():
    if name not in expected: assert name.startswith('unconnected-') and len(pins)==1, name

def net(ref, number):
    p = next(p for p in parts if p['ref']==ref)
    return next(pin[2] for pin in p['pins'] if pin[0]==str(number))

assert net('U5',1)=='+5VA' and net('U5',12)=='GND'
assert net('U5',14)=='DAC_RB' and net('U5',16)=='VREF'
assert net('U5',7)==net('U1',23) and net('U5',4)==net('U1',22) and net('U5',10)==net('U1',39)
assert all(net('U5',n) is None for n in (3,5,6,8,9,11,13,15))
assert net('U3',20)=='+3V3' and net('U2',20)==net('U4',20)=='+5V'
assert net('U3',1)=='+3V3'
assert net('U6',3)=='DAC_RB' and net('U6',1)==net('U6',2)==net('U5',16)
assert net('U6',5)=='DAC_RAW' and net('U6',6)==net('U6',7)=='FM_BUF'
assert net('J3',3)=='GND' and net('J4',1)=='SPK_P' and net('J4',2)=='SPK_N'
assert net('J4',1)!='GND' and net('J4',2)!='GND'
assert net('U7',8)=='+5VA' and net('U7',7)=='VREF' and net('U7',5)=='MIX_OUT'
assert all(0<=int(g)<=48 for g in design['mcu_gpio'])
assert not {0,3,19,20,35,36,37,45,46,48} & {int(g) for g in design['mcu_gpio']}

erc=json.loads((ROOT/'erc.json').read_text())
violations=[v for s in erc['sheets'] for v in s['violations']]
assert not violations,Counter(v['type'] for v in violations)
# The virtual bus separates writeto_mem from writeto, but real I2C does not.
# Check the hardware adapter removes that ambiguity and preserves mixer bookkeeping.
project=next(parent for parent in ROOT.parents if (parent/'reference/weblab/web_lab_ym2203_v1.py').is_file())
base_spec=importlib.util.spec_from_file_location('web_lab_ym2203_v1',project/'reference/weblab/web_lab_ym2203_v1.py')
base=importlib.util.module_from_spec(base_spec);base_spec.loader.exec_module(base);sys.modules['web_lab_ym2203_v1']=base
adapter_spec=importlib.util.spec_from_file_location('host_driver_adapter',ROOT/'host_driver_adapter.py')
adapter=importlib.util.module_from_spec(adapter_spec);adapter_spec.loader.exec_module(adapter)
class Bus:
    def __init__(self):self.packets=[]
    def readfrom(self,address,count):return bytes((1,0,0,20,0,0))
    def writeto(self,address,data):assert address==0x44;self.packets.append(bytes(data))
bus=Bus();sound=adapter.YM2203I2CHardware(bus)
sound.write_register(4,20);sound.volume(20);sound.write_register(7,0x3f)
assert bus.packets==[b'\x00\x04\x14',b'\x04\x14',b'\x00\x07\x3f'] and sound._mixer==0x3f
for reg,val in [(True,0),(-1,0),(0,256)]:
    before=len(bus.packets)
    try:sound.write_register(reg,val);raise AssertionError('invalid register/value accepted')
    except ValueError:pass
    assert len(bus.packets)==before
report={'verified_at':datetime.now(timezone.utc).isoformat(),'kicad_version':erc['kicad_version'],
    'components':len(parts),'connected_nets':len(expected),'pin_netlist_comparison':'passed',
    'dac_sop16_pin_mapping':'passed','power_and_bus_domains':'passed',
    'headphone_and_btl_nets_separate':'passed','mcu_reserved_pins_avoided':'passed',
    'erc_errors':0,'erc_warnings':0,
    'host_adapter_register4_vs_volume_packet':'passed in desktop Python; real bus still untested',
    'not_performed':['SPICE simulation','PCB layout / footprint verification','firmware implementation/build',
                     'power-on measurements','audio playback measurements','headphone/speaker listening','long-duration playback']}
(ROOT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
# Remove machine-specific export metadata before these artifacts can enter Git.
source=tree.find('./design/source')
if source is not None:source.text='ym2203-i2c-prototype.kicad_sch'
for uri in tree.findall('./libraries/library/uri'):
    if uri.text and str(ROOT) in uri.text:uri.text=uri.text.replace(str(ROOT),'${KIPRJMOD}')
tree.write(ROOT/'netlist.xml',encoding='utf-8',xml_declaration=True)
erc['source']='ym2203-i2c-prototype.kicad_sch'
(ROOT/'erc.json').write_text(json.dumps(erc,ensure_ascii=False,indent=2)+'\n')

# A readable signal-flow overview, distinct from the pin-level connection schematic.
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">',
 '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6" fill="none" stroke="#296f67" stroke-width="1.4"/></marker></defs>',
 '<rect width="1200" height="640" fill="#f4f6ef"/>',
 '<style>text{font-family:Arial,sans-serif;fill:#173e3a} .h{font-size:24px;font-weight:bold}.s{font-size:17px}.n{font-size:14px} .wire{fill:none;stroke:#296f67;stroke-width:3;marker-end:url(#a)}</style>',
 '<text x="25" y="42" class="h">YM2203C + YM3014B-F | I2C audio module</text>',
 '<text x="25" y="72" class="s">Rev A - circuit proposal / not hardware tested / firmware required</text>']
def box(x,y,w,h,title,sub):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="white" stroke="#87aaa0" stroke-width="2"/>')
    svg.append(f'<text x="{x+w/2}" y="{y+30}" text-anchor="middle" class="s" font-weight="bold">{html.escape(title)}</text>')
    svg.append(f'<text x="{x+w/2}" y="{y+56}" text-anchor="middle" class="n">{html.escape(sub)}</text>')
def line(path):svg.append(f'<path class="wire" d="{path}"/>')
box(25,125,170,80,'I2C host','Pico / 3.3 V bus')
box(245,125,205,80,'ESP32-S3 + PSRAM','0x44 / queue / timing')
box(500,125,190,80,'5 V bus interface','AHCT541 / LVC245A')
box(750,125,220,80,'YM2203C','4 MHz / FM 3 + SSG 3')
line('M195 165 H245');line('M450 165 H500');line('M690 165 H750')
box(750,260,220,80,'YM3014B-F','SOP-16 / FM DAC')
line('M860 205 V260');svg.append('<text x="872" y="237" class="n">FM digital</text>')
box(420,385,300,85,'Mix + master volume','OPA4192 / MCP41010')
line('M750 300 H700 V360 H650 V385')
svg.append('<text x="620" y="338" class="n">FM analog</text>')
line('M970 165 H1050 V428 H720')
svg.append('<text x="1063" y="310" class="s">SSG A/B/C</text>')
line('M348 205 V300 H550 V385')
svg.append('<text x="365" y="286" class="n">SPI volume + mute controls</text>')
box(30,325,270,80,'Headphone amplifier','TPA6110A2 / TRS L=R')
box(30,485,270,80,'Speaker amplifier','PAM8302A / 8 ohm BTL')
line('M420 428 H350 V365 H300');line('M350 428 V525 H300')
svg.append('<circle cx="350" cy="428" r="5" fill="#296f67"/>')
svg.append('<text x="25" y="609" class="s">USB 5 V / 2 A supply | Separate headphone and speaker outputs | Speaker switch S1</text></svg>')
(ROOT/'overview.svg').write_text(''.join(svg))
subprocess.run(['rsvg-convert','-w','1200','-o',str(ROOT/'overview.png'),str(ROOT/'overview.svg')],check=True)

rows=[]
for part in parts:
    if part['kind']=='flag':continue
    connections='; '.join(f'{n} {name} → {net if net is not None else "NC"}' for n,name,net,typ in part['pins'])
    rows.append('<tr><td>'+html.escape(part['ref'])+'</td><td>'+html.escape(part['value'])+'</td><td>'+html.escape(connections)+'</td></tr>')
page='''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YM2203 I2C音源モジュール 回路案 Rev A</title><style>
body{font:16px/1.8 system-ui,sans-serif;background:#f4f6ef;color:#173e3a;margin:0}main{max-width:1120px;margin:auto;padding:28px}
h1{line-height:1.4}a{color:#075f86}img{width:100%;height:auto}section{background:white;padding:24px;border-radius:14px;margin:20px 0}
.notice{border-left:5px solid #a76b12;background:#fff5df;padding:16px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid #d7e0d7;text-align:left;vertical-align:top}td:last-child{overflow-wrap:anywhere}input{font:inherit;padding:10px;width:90%;margin:10px 0}.table{overflow:auto}
</style><main><h1>YM2203C＋YM3014B-F<br>I2C音源モジュール 回路案 Rev A</h1>
<p class="notice">USB 5 V・3.5 mmイヤホン・8 Ωスピーカー。未組み立ての設計案です。実機発音・アナログ特性は未検証で、制御ファームウェアも別途必要です。</p>
<img src="overview.svg" alt="I2Cホストから制御用マイコンを経てYM2203を駆動し、FMとSSGを混合してイヤホンとスピーカーへ分岐する構成図">
<section><h2>図面と接続情報</h2><p><a href="ym2203-i2c-prototype.kicad_pro">KiCadプロジェクト</a> · <a href="ym2203-i2c-prototype.kicad_sch">回路図ソース</a> · <a href="rendered/ym2203-i2c-prototype.svg">端子番号付き回路図（SVG）</a> · <a href="connections.csv">接続表CSV</a> · <a href="bom.csv">部品表CSV</a> · <a href="README.md">設計説明・一次資料・組み立て後の検証</a></p>
<p>同じネット名は接続されています。左右のイヤホン出力は独立したアンプで同じモノラル音を出します。スピーカーのBTL出力はGNDへ接続しません。</p>
<p>KiCad ERC：エラー0・警告0。全83ネットの端子接続をKiCad出力と照合済み。PCB配線・SPICE・実機検証は未実施です。</p></section>
<section><h2>部品・端子の検索</h2><label>部品番号、型番、ネット名 <input id="search" placeholder="例：U5 / DAC_SD / HP_SHUTDOWN"></label><div class="table"><table><thead><tr><th>部品</th><th>型番・値</th><th>端子番号／機能 → ネット</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div></section>
<p>2026-10-14 / 独自の試作モジュール。ヤマハ公式製品ではありません。</p></main><script>
document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();for(const r of document.querySelectorAll('tbody tr'))r.hidden=!r.textContent.toLowerCase().includes(q)});
</script></html>'''
(ROOT/'index.html').write_text(page)
names=['README.md','index.html','overview.svg','overview.png','ym2203-i2c-prototype.kicad_pro','ym2203-i2c-prototype.kicad_sch',
       'YM2203_HW.kicad_sym','sym-lib-table','rendered/ym2203-i2c-prototype.svg','design.json','connections.csv','bom.csv',
       'netlist.xml','calculations.json','verification.json','erc.json','generate.py','verify.py','host_driver_adapter.py','.gitignore']
with zipfile.ZipFile(ROOT/'ym2203-i2c-prototype-rev-a.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in names:z.write(ROOT/name,name)
with zipfile.ZipFile(ROOT/'ym2203-i2c-prototype-rev-a.zip') as z:
    assert z.testzip() is None and z.namelist()==names
    for name in names:assert z.read(name)==(ROOT/name).read_bytes()
print(json.dumps(report,ensure_ascii=False,indent=2))
print('ZIP SHA-256:',hashlib.sha256((ROOT/'ym2203-i2c-prototype-rev-a.zip').read_bytes()).hexdigest())
