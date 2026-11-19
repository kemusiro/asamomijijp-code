# SPDX-License-Identifier: MIT
"""LC-B adopted GPIO schematic C; historical circuit JSON is read-only."""
from copy import deepcopy
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
V3='V3V3'; V5='V5_CARRIER'; G='GND'

def read(p): return json.loads(p.read_text())
def part(ref,value,sheet,pins,footprint='',source='',note=''):
    return dict(ref=ref,value=value,sheet=sheet,pins=[dict(num=str(n),name=name,net=net,type=t) for n,(name,net,t) in pins.items()],footprint=footprint,source=source,note=note)
def two(ref,value,a,b,sheet='03-controls',footprint=None):
    fp=footprint or ('Capacitor_SMD:C_0805_2012Metric' if ref.startswith('C') else 'Resistor_SMD:R_0805_2012Metric')
    return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},fp)
def pin(p,n): return next(q for q in p['pins'] if q['num']==str(n))
def rename(parts,m):
    for p in parts:
        for q in p['pins']: q['net']=m.get(q['net'],q['net'])
def grove(ref,rail,sda,scl,sheet,remote=False):
    return part(ref,'110990037 Grove I2C 3V3 ONLY',sheet,{1:('SCL',scl,'input' if remote else 'passive'),2:('SDA',sda,'bidirectional' if remote else 'passive'),3:('3V3',rail,'passive'),4:('GND',G,'passive')},'','https://akizukidenshi.com/catalog/g/g112634/','150mm cable116938;no5V;power off for insertion;pin1SCL/2SDA/3VCC/4GND. Footprint deferred: RA drawing lacks unambiguous drill/top-view numbering;verify actual2mm part before PCB.')

def base_mcu(gpio):
    role={x['gpio']:x['net'] for x in gpio}
    pins={}
    for gp in range(30):
        net=role.get(gp)
        typ='output' if gp in [12,14,15,16,19,22] else 'input' if gp in [13,17,18,23,28] else 'bidirectional'
        pins[f'J1.{gp+2}' if gp<16 else f'J2.{gp-13}']=(f'GP{gp}',net,typ)
    pins.update({'J1.1':('3V3_OUT',V3,'power_out'),'J1.18':('RESET','RUN_N','input'),'J1.19':('GND',G,'power_in'),'J1.20':('SWCLK','SWCLK','input'),
                 'J2.1':('SWDIO','SWDIO','bidirectional'),'J2.2':('GND',G,'power_in'),'J2.17':('USB_DM','USB_DM','bidirectional'),
                 'J2.18':('USB_DP','USB_DP','bidirectional'),'J2.19':('REG_IN_5V',V5,'power_in'),'J2.20':('3V3_OUT',V3,'passive')})
    return part('UBASE','Picossci 2 RP2350A SSCI-097956','01-mcu',pins,'','https://www.switch-science.com/products/9795','40edgecontacts,1.27mm direct solder. GPIO approved2026-11-19. GP25onboardLED NC externally;GP24/29spare. RESET exposedJ1.18. Custom landing awaits PCB geometry verification; NOT socketed.')

def source_mcu(src):
    role={x['gpio']:x for x in src}
    identities={}
    for gp in range(17):identities[f'J1.{gp+4}']=gp
    for gp in range(31,48):identities[f'J2.{gp-30+(1 if gp>=40 else 0)}']=gp
    for gp in range(17,24):identities[f'JP6.{gp-16}']=gp
    for gp in range(24,31):identities[f'JP7.{gp-22}']=gp
    pins={}
    for pad,gp in identities.items():
        q=role.get(gp);pins[pad]=(f'GP{gp}',q['net'] if q else None,q['electrical_type'] if q else 'bidirectional')
    pins.update({'J1.1':('3V3_OUT','MCU_3V3','power_out'),'J1.2':('USB_DM',None,'bidirectional'),'J1.3':('USB_DP',None,'bidirectional'),
                 'J2.10':('GND',G,'power_in'),'J2.19':('REG_IN_5V','V5_MODULE','power_in'),'J2.20':('3V3_OUT','MCU_3V3','passive'),
                 'JP6.8':('GND',G,'power_in'),'JP7.1':('GND',G,'power_in'),
                 'JP1.1':('SWCLK','CORE_SWCLK','input'),'JP1.2':('GND',G,'power_in'),'JP1.3':('SWDIO','CORE_SWD','bidirectional'),
                 'SW1.S':('RESET_EXTRA_WIRE','CORE_RUN_N','input')})
    return part('USOURCE','Picossci 2B RP2350B SSCI-105071','02-source-mcu',pins,'','https://www.switch-science.com/products/10507','56edgecontacts plus3debugpads andSW1RESETwire. MUST remove onboardR5/R6 loadsGP24/25;MUST wire SW1nonGND to CORE_RUN_N. FlashJEDEC pending. Custom landing not PCB-verified.')

def panel_mcu(roles):
    mapping={1:0,2:1,4:2,5:3,6:4,7:5,9:6,10:7,11:8,12:9,14:10,15:11,16:12,17:13,19:14,20:15,21:16,22:17,24:18,25:19,26:20,27:21,29:22,31:26,32:27,34:28}
    role={x['gpio']:x['net'] for x in roles}; pins={}
    for n,gp in mapping.items():
        typ='input' if gp in list(range(9,18))+[26] else 'output' if gp in [4,5,6,7,8,18,19] else 'bidirectional'
        pins[n]=(f'GP{gp}',role.get(gp),typ)
    for n in [3,8,13,18,23,28,33,38]:pins[n]=('GND',G,'power_in')
    pins.update({30:('RUN','PANEL_RUN_N','input'),35:('ADC_VREF',None,'passive'),36:('3V3_OUT','PANEL_3V3','power_out'),37:('3V3_EN',None,'input'),39:('VSYS','PANEL_VSYS','power_in'),40:('USB_VBUS',None,'passive')})
    return part('UPICO','Raspberry Pi Pico SC0915 RP2040','01-panel-mcu',pins,'Module:RaspberryPi_Pico_Common_THT','https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf','VSYS from3V3 Grove throughDPOWER. GPIO29VSYS/25LED/24VBUS/23SMPS internal,not externalADC. USB service only withGrove unplugged. Two20pin2.54mm sockets.')

def make():
    g=read(ROOT/'low-cost-review-b/gpio-proposal.json')
    base=deepcopy(read(ROOT/'clean-sheet-pcb-review-l/base/circuit.json')['parts'])
    base=[p for p in base if p['ref'] not in ['MPGA','SWBOOT','JUSB','RCC1','RCC2'] and not p['sheet']=='09-uno']
    rename(base,{'PANEL_SDA':'SERVICE_SDA','PANEL_SCL':'SERVICE_SCL','STOP_N':'BASE_STOP_N'})
    # No UNO jumpers remain between MCU and its internal bus.
    base.append(base_mcu(g['base_compact']))
    b={p['ref']:p for p in base}
    pin(b['UPANEL'],25)['net']=None
    b['UPANEL']['note']='I2C0x20;DIP/TEST/RX+6voice LEDs only. STOP moved toUBASEGP23;noSTOPdependence onI2C.'
    b['SWSTOP']['note']='GPIO23direct;external10k;globalmute priority,not I2C expander.'
    b['UVBUS']['note']='Ioff Schmitt;RAWVBUS47k/68k -> GP28. No USB-to-external5V supply path.'
    base.append(part('JUSB','5075BR-04-WH USB2 TypeB DEVICE','02-power-usb',
        {1:('VBUS','USB_VBUS_RAW','passive'),2:('D-','USB_DM','passive'),3:('D+','USB_DP','passive'),4:('GND',G,'passive'),'SH':('SHIELD',G,'passive')},
        '', 'https://akizukidenshi.com/catalog/g/g100161/',
        'Common50JPY THT USB-B replaces importedUSB-C toavoidshipping/stockrestriction. SameUSB2FS CDC/MIDI,VBUSsenseonly. NoCCresistors. ExactpadholespendingPCB drawingmatch.'))
    b['U17']['note']=b['U17']['note'].replace('PGA3V3','BASE3V3')
    # 1% divider retains Schmitt threshold margin; ordinary thick-film parts.
    b['RVB1']['value']='47k 1%'; b['RVB2']['value']='68k 1%'
    for ref in ['R37','R38']:b[ref]['value']='4.7k 1%'
    base.append(grove('JEDIT','V3_AUX','SERVICE_SDA','SERVICE_SCL','13-i2c-panel'))
    base.append(two('CPANELPORT','10u X7R 10V','V3_AUX',G,'13-i2c-panel'))
    for p in base:
        if p['ref']=='JMOD':
            p['value']='G40 2x20 ordinary female / KEY6';p['source']='https://akizukidenshi.com/catalog/g/g100085/'
            p['note']='40pin2.54mm female;blockpin6,removeopposingmale6. Hconnector electrical order unchanged. Fit not yet measured.'
        if p['ref'] in ['RATTL','RATTR']:p['value']='6.8k 1%'
        if p['ref']=='URXDATA':
            p['value']='TC7SZ125F,LJ(CT';p['source']='https://toshiba.semicon-storage.com/info/TC7SZ125F_datasheet_en_20171221.pdf?did=20049&prodName=TC7SZ125F'
            p['note']='CommonSOT25 buffer alternative to out-of-stockTI1G125. Pin1OE2A3GND4Y5VCC;Ioff/5.5Vinputs maintained. F(SMV)ONLY,notFU(SC70).'
        if p['ref'].startswith('DCLAMP'):
            p['value']='BAT54S-QR';p['source']='https://assets.nexperia.com/documents/data-sheet/BAT54S-Q.pdf'
        if p['ref'] in ['CACL','CACR']:
            p['value']='10u 50V NP +/-20% 50NXA10MEFC5X11'
            p['footprint']='Capacitor_THT:CP_Radial_D5.0mm_P2.00mm'
            p['source']='https://akizukidenshi.com/catalog/g/g130142/'
            p['note']='NON-POLAR NXA coupling,minimum8uF at20percent tolerance,avoidsMLCCbiasrareMPN;electricalpolaritynotrequired despitegenericCPfootprint. BodyD5xH11mm;outsideoverlapofsourcecard. Ripple/leakage/bias/THD bench pending.'
        if p['ref']=='SWCLOCK':
            p['value']='EDS104SZ 4-bit DIP ON=0 SW1=LSB';p['source']='https://akizukidenshi.com/catalog/g/g100586/'

    module=deepcopy(read(ROOT/'clean-sheet-schematic-review-h/module/circuit.json')['parts'])
    module=[p for p in module if not p['ref'].startswith('JCORE')]
    module.append(source_mcu(read(ROOT/'clean-sheet-schematic-review-h/source-pins.json')['gpio']))
    for p in module:
        if p['ref']=='JMOD':
            p['value']='G40 2x20 ordinary male / KEY6';p['source']='https://akizukidenshi.com/catalog/g/g100080/'
        if p['ref']=='URUNOD':p['note']='ENABLE low -> sink CORE_RUN_N -> SW1RESET wire onPicossci2B. Do not omit wire. Ioff/defaultLOW independent ofSPIcleanup.'
        if p['ref']=='CMOD5':
            p['value']='22u X7R 16V C3225X7R1C226K250AC';p['footprint']='Capacitor_SMD:C_1210_3225Metric'
            p['source']='https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no=C3225X7R1C226K250AC'
            p['note']='Larger1210commonX7R supplybulk,notrare0805high-density. No GPIOorresetpathchange.'

    # Preserve the panel electrical controls and record schema, replace UNO by MCU.
    panel=deepcopy(read(ROOT/'editor-shield-review-b/circuit.json')['parts'])
    panel=[p for p in panel if not p.get('design_id','').startswith('JUNO')]
    rename(panel,{'IOREF_3V3':'PANEL_3V3','AUX_3V3':'PANEL_3V3','SDA':'EEPROM_SDA','SCL':'EEPROM_SCL','STOP_N':'PANEL_STOP_N'})
    for p in panel:
        p.pop('supplier_code',None);p.pop('supplier_url',None)
        if p['ref'].startswith('R') and not p['ref'].startswith('RV'):p['footprint']='Resistor_SMD:R_0805_2012Metric'
        if p['ref'].startswith('C'):p['footprint']='Capacitor_SMD:C_0805_2012Metric'
        if p['ref']=='ENC1':p['footprint']='P2LC:RE111F_4S1_ReviewB'
        if p['ref'].startswith('RV'):p['pins']=[q for q in p['pins'] if q['num']!='MP']
        if p.get('design_id')=='JLCD':p['note']='M154 module via8pin harness;3.3Vlocal. Pin1GND2VCC3SCK4MOSI5RST6DC7CS8BLK;unchanged20261020 order.'
    panel.append(panel_mcu(g['panel']))
    panel += [grove('JUPLINK','UPLINK_3V3','UPLINK_SDA','UPLINK_SCL','01-panel-mcu',True),
              part('DPOWER','1N5819','01-panel-mcu',{1:('K','PANEL_VSYS','passive'),2:('A','UPLINK_3V3','passive')},'Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal','https://www.vishay.com/docs/88525/1n5817.pdf','CommonSchottky reverseblock;USBserviceONLYGroveunplugged,avoidSDAbackfeed.'),
              two('CPIN','10u X7R 10V','PANEL_VSYS',G,'01-panel-mcu'),
              two('RPANELRUN','10k','PANEL_RUN_N','PANEL_3V3','01-panel-mcu'),
              two('REEPSDA','4.7k','EEPROM_SDA','PANEL_3V3','02-eeprom'),two('REEPSCL','4.7k','EEPROM_SCL','PANEL_3V3','02-eeprom'),
              two('CMUX','100nF','PANEL_3V3',G,'03-mux'),
              part('UMUX','CD74HC4051E','03-mux',{
                  1:('CH4',G,'passive'),2:('CH6',G,'passive'),3:('COM','KNOB_ADC','passive'),4:('CH7',G,'passive'),
                  5:('CH5',G,'passive'),6:('INH',G,'input'),7:('VEE',G,'power_in'),8:('GND',G,'power_in'),
                  9:('C',G,'input'),10:('B','MUX_B','input'),11:('A','MUX_A','input'),12:('CH3','KNOB4_ADC','passive'),
                  13:('CH0','KNOB1_ADC','passive'),14:('CH1','KNOB2_ADC','passive'),15:('CH2','KNOB3_ADC','passive'),16:('VCC','PANEL_3V3','power_in')},
                   'Package_DIP:DIP-16_W7.62mm','https://www.ti.com/lit/ds/symlink/cd74hc4051.pdf','HC2..6V;notHCT. CH0..3=knob1..4;C/INH/VEE=GND. 250ussettle then discardfirstADCsample;no audio goes throughthismux.')]
    meta=dict(schema_version=1,revision='LC-B-schematic-C',date='2026-11-19',status='connected_schematic_not_pcb_or_hardware_acceptance',gpio_approval='user accepted LC-B recommended configuration and presented GPIO in this task',firmware_implemented=False,pcb_created=False,hardware_accepted=False)
    return {side:dict(meta,board=side,parts=parts) for side,parts in [('base',base),('module',module),('panel',panel)]}
