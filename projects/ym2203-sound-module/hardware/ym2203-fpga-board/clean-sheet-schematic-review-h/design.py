# SPDX-License-Identifier: MIT
"""Original review H design data, using historical part/pad identities as read-only inputs."""
from copy import deepcopy
from pathlib import Path
import json
import os

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('P2_REFERENCE_HARDWARE',HERE.parent))
V3='V3V3';V5='V5_CARRIER';G='GND'
REV='3.5-schematic-review-h'
SOURCES={'adc':'https://www.ti.com/lit/ds/symlink/pcm1863.pdf',
         'dac':'https://www.ti.com/lit/ds/symlink/pcm5102a.pdf',
         'ldo':'https://www.ti.com/lit/ds/symlink/tlv1117lv.pdf',
         'and':'https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf',
         'od':'https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf',
         'clamp':'https://assets.nexperia.com/documents/data-sheet/BAT54S.pdf'}


def read(p):return json.loads(p.read_text())


def part(ref,value,sheet,pins,footprint,source='',note=''):
    return dict(ref=ref,value=value,sheet=sheet,
                pins=[dict(num=str(n),name=name,net=net,type=typ) for n,(name,net,typ) in sorted(pins.items())],
                footprint=footprint,source=SOURCES.get(source,source),note=note)


def r(ref,value,a,b,sheet):
    return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Resistor_SMD:R_0805_2012Metric')


def cap(ref,value,a,b,sheet):
    return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Capacitor_SMD:C_0805_2012Metric')


def ppin(p,n):return next(x for x in p['pins'] if x['num']==str(n))


def setnet(p,n,net):ppin(p,n)['net']=net


def buf4(ref,channels,rail,sheet):
    p={7:('GND',G,'power_in'),14:('VCC',rail,'power_in')}
    for i,(a,y,oe) in enumerate(channels):
        en,an,yn=[(1,2,3),(4,5,6),(10,9,8),(13,12,11)][i]
        p.update({en:(str(i+1)+'OE_N',oe,'input'),an:(str(i+1)+'A',a,'input'),
                  yn:(str(i+1)+'Y',y,'output')})
    return part(ref,'SN74LV4T125PWR',sheet,p,'Package_SO:TSSOP-14_4.4x5mm_P0.65mm',
                'https://www.ti.com/lit/ds/symlink/sn74lv4t125.pdf','Ioff receiving-domain buffer, 5V-tolerant inputs; unused channels disabled.')


def rename(parts,mapping):
    for p in parts:
        for n in p['pins']:n['net']=mapping.get(n['net'],n['net'])


def connector(side,spec):
    pins={}
    for p in spec['pins']:
        net=p[side+'_net'];typ='passive'
        if net and p['kind']=='digital':
            if p['direction']=='base_to_module':typ='input' if side=='base' else 'output'
            elif p['direction']=='module_to_base':typ='output' if side=='base' else 'input'
            else:typ='bidirectional'
            if p['signal']=='MOD_ALERT_N':typ='open_collector' if side=='base' else 'bidirectional'
        if side=='module' and p['pin'] in [1,2]:typ='power_out'
        pins[p['pin']]=(p['signal'],net,typ)
    return part('JMOD','P2 G40 / KEY6 / NO LEGACY MATE','10-link' if side=='base' else '01-link',pins,
                'Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical' if side=='base' else
                'Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical',
                'https://www.samtec.com/products/ssw-120-02-g-d' if side=='base' else 'https://www.samtec.com/products/tsw-120-07-g-d',
                'Symbol types model the remote board for standalone ERC; connector is passive. Female6 blocked/male6 removed. Mechanical fit pending.')


def make():
    old={s:read(ROOT/'digital-module-review-c'/s/'circuit.json')['parts'] for s in ['base','module']}
    g=read(ROOT/'clean-sheet-interface-review-g/gpio-proposal.json')
    spec=read(HERE/'connector.json')
    # Start from proven identities, then replace entire audio/control/link sections.
    dropbase={'JMOD','UPERMIT','UDACRUN','ULINERUN','CUPERMIT','CUDACRUN','CULINERUN',
              'UDACBUF','CUDACBUF','RDACIN','URXBUF','CURXBUF','RLKSCK','RLKMOSI','RLKCS','RLKEN','RLKBCK','RLKLR',
              'RBCS','RBEN','RBI0','RBI1','RBMISO','RBSD','RBALERT','RALERT','UAUX','CAUXIN','CAUXOUT'}
    keepout={'R53','C38','R53R','C38R','JPOT','R59','R60','JLINE'}
    base=[deepcopy(p) for p in old['base'] if p['ref'] not in dropbase
          and (p['sheet']!='07-analog' or p['ref'] in keepout)]
    b={p['ref']:p for p in base}
    rename(base,{'M_I2S_DIN':'DAC_I2S_DATA','M_I2S_BCK':'AUDIO_BCK','M_I2S_LRCK':'AUDIO_LRCK',
                 'BUF_M_I2S_DIN':'DAC_I2S_DATA','BUF_M_I2S_BCK':'AUDIO_BCK','BUF_M_I2S_LRCK':'AUDIO_LRCK'})
    bygp={p['gpio']:p for p in g['base']}
    for p in b['MPGA']['pins']:
        if p['name'].startswith('GP'):
            n=int(p['name'][2:]);p['net']=bygp[n]['net'] if n in bygp else None
            p['type']='bidirectional'
            if n in [12,14,15,16,38,39]:p['type']='output'
            elif n in [13,17,18,46]:p['type']='input'
    b['MPGA'].update(footprint='P2H:PGA2350_Socket_64',
                     note='New G base GPIO0..7 data,8..11 control,14..18 audio. GP47 reserved. Fixed USB/RUN/SWD identity retained; no old-net compatibility.')
    for p in base:
        if p['ref'].startswith('JUNO'):p['footprint']='P2H:'+p['ref']
    b['F1']['value']='MF-MSMF200/16X-2 / 2A hold@23C'
    b['JPOWER']['note']='Regulated5.1V/2A input; verify4.75..5.25V at YM under load. USB VBUS remains isolated; no module/shield external supply.'
    base += [part('UAUX','TLV1117LV33DCYR','02-power-usb',
                  {1:('GND',G,'power_in'),2:('OUT','V3_AUX','power_out'),3:('IN',V5,'power_in')},
                  'Package_TO_SOT_SMD:SOT-223-3_TabPin2','ldo','Always-on shared analog/aux supply. Ceramic stable; copper/thermal measurement pending.'),
             cap('CAUXIN','10u X7R 10V',V5,G,'02-power-usb'),cap('CAUXOUT','10u X7R 10V','V3_AUX',G,'02-power-usb')]
    # DAC digital IO/core tracks the PGA rail; analog and charge pump remain on filtered AUX.
    setnet(b['U17'],20,V3);setnet(b['C33'],1,V3);setnet(b['C35'],1,V3)
    b['U17']['note']='Digital DVDD=PGA3V3; AVDD/CPVDD=AV3V3. Ground-centred line output, BCK PLL. XSMT is common final mute; no analog bypass.'
    b['U17']['source']=SOURCES['dac']
    b['R53']['sheet']=b['C38']['sheet']=b['R53R']['sheet']=b['C38R']['sheet']='07-lineout'
    setnet(b['R53'],2,'LINE_FILTER_L');setnet(b['C38'],1,'LINE_FILTER_L')
    setnet(b['R53R'],2,'LINE_FILTER_R');setnet(b['C38R'],1,'LINE_FILTER_R')
    for ref in ['JPOT','R59','R60','JLINE']:b[ref]['sheet']='07-lineout'
    setnet(b['JPOT'],3,'LINE_FILTER_L');setnet(b['JPOT'],6,'LINE_FILTER_R')
    b['JPOT']['value']='External dual10k log volume / 6pin'
    b['JPOT']['note']='Direct capless DAC line signal via470R/2.2n LPF. Wipers feed100R line outputs; load>=10k preferred, not headphone drive.'
    # Minimal common mute permission: retain two GPIO semantics without duplicate analog gates.
    base += [part('UMUTE','SN74LVC1G08DBVR','03-default-stop',
                  {1:('A','M_DAC_ALLOW','input'),2:('B','M_LINE_ALLOW','input'),3:('GND',G,'power_in'),
                   4:('Y','DAC_XSMT','output'),5:('VCC',V3,'power_in')},
                  'Package_TO_SOT_SMD:SOT-23-5','and','XSMT high only when both permissions high; default low. Not an independent analog disconnect.'),
             cap('CUMUTE','100n X7R 10V',V3,G,'03-default-stop')]
    # Common ADC: IO rail follows PGA, so I2C/BCK/DOUT do not cross a switched rail.
    adc=deepcopy(next(p for p in old['module'] if p['ref']=='UADC'))
    ppin(adc,19)['name']='GPIO3';adc['sheet']='11-common-adc';adc['note']='Base common stereo ADC; VINL1/VINR1 only. AVDD=AV3V3,DVDD=V3_AUX,IOVDD=PGA3V3. AD=0 ->0x4A. No external reset pin; always powered on STOP.'
    for pin in adc['pins']:pin['net']=None
    adcn={3:'ADC_L',4:'ADC_R',6:'ADC_VREF',7:G,8:'AV3V3',10:G,11:'ADC_LDO_1V8',12:G,13:'V3_AUX',14:V3,
          15:G,16:'ADC_LRCK',17:'ADC_BCK',18:'BASE_ADC_DOUT_RAW',21:'ADC_DMIN_PD',23:'PANEL_SDA',24:'PANEL_SCL',25:G,26:G}
    for n,net in adcn.items():setnet(adc,n,net)
    base.append(adc)
    for tag,rail in [('AV','AV3V3'),('DV','V3_AUX'),('IO',V3),('LDO','ADC_LDO_1V8')]:
        base += [cap('CADC'+tag+'0','100n X7R 10V',rail,G,'11-common-adc'),
                 cap('CADC'+tag+'1','10u X7R 10V',rail,G,'11-common-adc')]
    base += [cap('CADCVREF','1u X7R 10V','ADC_VREF',G,'11-common-adc'),
             r('RDMINPD','100k','ADC_DMIN_PD',G,'11-common-adc'),
             r('RADCBCK','33','AUDIO_BCK','ADC_BCK','11-common-adc'),
             r('RADCLR','33','AUDIO_LRCK','ADC_LRCK','11-common-adc'),
             r('RADCDATA','33','BASE_ADC_DOUT_RAW','BASE_ADC_DOUT','11-common-adc'),
             r('RADCDATAPD','100k','BASE_ADC_DOUT',G,'11-common-adc')]
    for side in ['L','R']:
        sh='12-analog-input'
        base += [r('RATT'+side,'6.81k 1%','AUDIO_'+side,'ADC_DIV_'+side,sh),
                 r('RSHUNT'+side,'10k 1%','ADC_DIV_'+side,G,sh),
                 cap('CAC'+side,'10u X7R 16V / effective>=4.7u','ADC_DIV_'+side,'ADC_AC_'+side,sh),
                 r('RLIMIT'+side,'2.2k 1%','ADC_AC_'+side,'ADC_'+side,sh),
                 cap('CAAF'+side,'470p C0G','ADC_'+side,G,sh),
                 part('DCLAMP'+side,'BAT54S,215',sh,{1:('A1',G,'passive'),2:('K2','AV3V3','passive'),3:('K1_A2','ADC_'+side,'passive')},
                      'Package_TO_SOT_SMD:SOT-23','clamp','Limited-current transient rail clamp after AC coupling. Attenuation preserves normal line headroom; no TMUX/ADC power switching.')]
    # All12 generic bus pins route bidirectionally, no receive-only MISO buffer in the shared bus.
    for n in range(8):base.append(r('RBD'+str(n),'33','BUS_D'+str(n),'L_BUS_D'+str(n),'10-link'))
    for n in range(4):base.append(r('RBCTL'+str(n),'33','MOD_CTL'+str(n),'L_MOD_CTL'+str(n),'10-link'))
    for ref,src,dst in [('RLKEN','MOD_ENABLE','L_MOD_ENABLE'),('RLKBCK','AUDIO_BCK','L_MOD_I2S_BCK'),
                         ('RLKLR','AUDIO_LRCK','L_MOD_I2S_LRCK')]:base.append(r(ref,'33',src,dst,'10-link'))
    base += [r('RBEN','10k','MOD_ENABLE',G,'10-link'),r('RBCS','10k','BUS_D1',V3,'10-link'),
             r('RBMISO','100k','BUS_D0',G,'10-link'),r('RBSCK','100k','BUS_D2',G,'10-link'),
             r('RBMOSI','100k','BUS_D3',G,'10-link'),r('RBALERT','10k','MOD_ALERT_N',V3,'10-link'),
             r('RALERT','0','L_MOD_ALERT_N','MOD_ALERT_N','10-link'),
             r('RBI1','100k','L_MOD_I2S_DATA',G,'10-link'),r('RBSD','100k','MOD_I2S_DATA',G,'10-link')]
    old_rx=deepcopy(next(p for p in old['module'] if p['ref']=='UADCDATA'))
    old_rx.update(ref='URXDATA',sheet='10-link',note='PGA-powered Ioff receiver for optional source I2S data. Shared bidirectional bus has no inline receive-only buffer.')
    setnet(old_rx,2,'L_MOD_I2S_DATA');setnet(old_rx,4,'MOD_I2S_DATA');setnet(old_rx,5,V3)
    base += [old_rx,cap('CURXDATA','100n X7R 10V',V3,G,'10-link'),connector('base',spec)]
    # Source: keep only YM bus+FM identities, and redesign the Core/link/reset/SSG sections.
    keep_sheets={'02-level-bus','04-ym-fm-clock','05-ssg'}
    removed={'U14','C23','C24'}
    module=[deepcopy(p) for p in old['module'] if p['sheet'] in keep_sheets and p['ref'] not in removed]
    m={p['ref']:p for p in module}
    m['U8']['note']='Bidirectional YM data translation: VCCA=Core3V3,VCCB=5V. DIR and OE controlled locally; default disabled.'
    # Consolidate clock and reset up-translation into unused U9 channels.
    setnet(m['U9'],7,'YM_CLOCK_3V3');setnet(m['U9'],17,'YM_CLK_5')
    setnet(m['U9'],8,'YM_RESET_RELEASE');setnet(m['U9'],16,'Y_RESET_N')
    m['U9']['note']='Fixed A->B: A0/CS/WR/RD plus clock and RESET on two formerly spare channels. OE_N default high disables clock and holds RESET via10k pull-down.'
    module += [r('RYMRESET','10k','Y_RESET_N',G,'03-reset'),r('RRELDEFAULT','100k','YM_RESET_RELEASE',G,'03-reset'),
               cap('CMOD5','22u X7R 10V','V5_MODULE',G,'04-ym-fm-clock')]
    for n,ch in enumerate('ABC'):
        module.append(r('RSMIX'+ch,'10k 1%','SSG_'+ch,'AUDIO_L','05-ssg'))
    # Local Core allocation is fresh and distinct from base GPIO numbers.
    src=read(HERE/'source-pins.json');bygp={p['gpio']:p for p in src['gpio']}
    hdr=read(ROOT/'digital-module-review-c/module-header.json')['headers']
    for name,identities in hdr.items():
        ps={}
        for n,identity in enumerate(identities,1):
            net=None;typ='bidirectional';label='GPIO'+str(identity) if isinstance(identity,int) else identity
            if isinstance(identity,int) and identity in bygp:
                q=bygp[identity];net=q['net'];typ=q['electrical_type']
            elif identity=='GND':net=G;typ='power_in'
            elif identity=='VBUS':net='V5_MODULE';typ='power_in'
            elif identity=='3V3':net='MCU_3V3';typ='power_out'
            elif identity in ['RUN','SWD','SWCLK']:
                net={'RUN':'CORE_RUN_N','BOOTSEL':'CORE_BOOT_N','SWD':'CORE_SWD','SWCLK':'CORE_SWCLK'}[identity]
                typ='bidirectional' if identity=='SWD' else 'input'
            ps[n]=(label,net,typ)
        module.append(part('JCORE'+name[1:],'Core2350B0 '+name+' / individual receptacles','02-core',ps,
                           'P2H:Core2350B0_'+name+'_IndividualSockets','https://files.waveshare.com/wiki/Core2350B0/Core2350B.pdf',
                           '16logical contacts, physically16 individual sockets, not rectangular2x8 socket. Source module assembly item separately required.'))
    module += [cap('CCORE','100n X7R 10V','MCU_3V3',G,'02-core'),cap('CCOREB','4.7u X7R 10V','MCU_3V3',G,'02-core'),
               part('JSWD','Core SWD / VREF sense only','02-core',
                    {1:('VREF','MCU_3V3','passive'),2:('SWD','CORE_SWD','passive'),3:('SWCLK','CORE_SWCLK','passive'),4:('GND',G,'passive'),5:('RUN','CORE_RUN_N','passive')},
                    'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical',note='External probe must not supply power; Core onboard BOOT/RESET buttons used.'),
               part('URUNOD','SN74LVC1G07DBVR','03-reset',
                    {1:('NC',None,'no_connect'),2:('A','L_MOD_ENABLE','input'),3:('GND',G,'power_in'),4:('Y','CORE_RUN_N','open_collector'),5:('VCC','MCU_3V3','power_in')},
                    'Package_TO_SOT_SMD:SOT-23-5','od','ENABLE low sinks Core RUN; no Schmitt/AND/latch chain. Defaults plus YM reset pull-down; not independent watchdog.'),
               cap('CURUNOD','100n X7R 10V','MCU_3V3',G,'03-reset'),
               r('RENPD','10k','L_MOD_ENABLE',G,'03-reset'),r('RRUNUP','10k','CORE_RUN_N','MCU_3V3','03-reset')]
    module += [buf4('ULINK0',[('L_BUS_D2','MOD_SPI_SCK',G),('L_BUS_D3','MOD_SPI_MOSI',G),
                             ('L_BUS_D1','MOD_SPI_CS_N',G),('L_SOUND_CLK0','YM_CLOCK_3V3',G)],'MCU_3V3','01-link'),
               buf4('ULINK1',[('L_MOD_I2S_BCK','MOD_I2S_BCK',G),('L_MOD_I2S_LRCK','MOD_I2S_LRCK',G),
                             ('MOD_SPI_MISO','LINK_TX_MISO','MISO_OE_N'),('MOD_I2S_DATA','LINK_TX_DATA','LINK_TX_DISABLE')],'MCU_3V3','01-link')]
    module += [part('UTXOR','SN74LVC1G32DBVR','01-link',
                    {1:('A','MOD_SPI_CS_N','input'),2:('B','LINK_TX_DISABLE','input'),3:('GND',G,'power_in'),
                     4:('Y','MISO_OE_N','output'),5:('VCC','MCU_3V3','power_in')},
                    'Package_TO_SOT_SMD:SOT-23-5','https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf',
                    'MISO disabled when unselected OR Core output permission not initialized. Default GPIO27 HiZ -> pull-up disables both return channels.'),
               cap('CUTXOR','100n X7R 10V','MCU_3V3',G,'01-link'),
               r('RTXDIS','10k','LINK_TX_DISABLE','MCU_3V3','01-link')]
    for ref in ['ULINK0','ULINK1']:module.append(cap('C'+ref,'100n X7R 10V','MCU_3V3',G,'01-link'))
    for ref,net,rail,value in [('RMSCK','L_BUS_D2',G,'100k'),('RMMOSI','L_BUS_D3',G,'100k'),
                              ('RMCS','L_BUS_D1','MCU_3V3','10k'),('RMBCK','L_MOD_I2S_BCK',G,'100k'),
                              ('RMLR','L_MOD_I2S_LRCK',G,'100k'),('RMCLK','L_SOUND_CLK0',G,'100k'),
                              ('RMADR','MOD_ALERT_DRIVE',G,'100k')]:module.append(r(ref,value,net,rail,'01-link'))
    module += [r('RMTXMISO','33','LINK_TX_MISO','L_BUS_D0','01-link'),r('RMTXDATA','33','LINK_TX_DATA','L_MOD_I2S_DATA','01-link'),
               part('UALERT','SN74LVC1G07DBVR','01-link',
                    {1:('NC',None,'no_connect'),2:('A','MOD_ALERT_DRIVE','input'),3:('GND',G,'power_in'),4:('Y','L_MOD_ALERT_N','open_collector'),5:('VCC','MCU_3V3','power_in')},
                    'Package_TO_SOT_SMD:SOT-23-5','od','Core sets HIGH when ready -> open drain released; LOW/reset reports not-ready/fault.'),
               cap('CUALERT','100n X7R 10V','MCU_3V3',G,'01-link'),connector('module',spec)]
    for side,parts in [('base',base),('module',module)]:
        assert len({p['ref'] for p in parts})==len(parts),side+' duplicate ref'
        for p in parts:assert len({n['num'] for n in p['pins']})==len(p['pins']),p['ref']
    meta=dict(schema_version=1,revision=REV,date='2026-11-18',status='connected schematic review; NOT FOR FABRICATION',
              gpio_approval='G clean-sheet scope authorized; base G allocation unchanged; new source allocation',
              firmware_implemented=False,pcb_created=False,hardware_accepted=False)
    return {side:dict(meta,board=side,parts=parts) for side,parts in [('base',base),('module',module)]}
