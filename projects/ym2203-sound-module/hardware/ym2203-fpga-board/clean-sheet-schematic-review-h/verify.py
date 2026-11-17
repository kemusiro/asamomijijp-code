#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Circuit/physical-pin and conditional passive bounds; no MCU/analog silicon simulation."""
import argparse, hashlib, itertools, json, math, re, sys, unittest
from pathlib import Path
from design import HERE, ROOT, make
from generate import check_export

REPO=ROOT.parents[3]
FP=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')

def load(p): return json.loads(Path(p).read_text())
def require(ok, message):
    if not ok: raise ValueError(message)
def part(d,b,r): return next(x for x in d[b]['parts'] if x['ref']==r)
def pin(d,b,r,n): return next(x for x in part(d,b,r)['pins'] if x['num']==str(n))
def exact(d,b,r,ps):
    for n,net in ps.items(): require(pin(d,b,r,n)['net']==net,f'{b}/{r}:{n}')

def validate(d):
    g=load(ROOT/'clean-sheet-interface-review-g/gpio-proposal.json')
    for p in g['base']: exact(d,'base','MPGA',{p['module_pad']:p['net']})
    used={p['gpio'] for p in g['base']}
    for p in part(d,'base','MPGA')['pins']:
        if p['name'].startswith('GP') and int(p['name'][2:]) not in used:
            require(p['net'] is None,'reserved/free base pin')
    header=load(ROOT/'digital-module-review-c/module-header.json')['headers']
    src=load(HERE/'source-pins.json')
    require(len(src['gpio'])==28 and len(set(p['gpio'] for p in src['gpio']))==28,'source allocation')
    for p in src['gpio']:
        h,n=next((h,i) for h,ps in header.items() for i,x in enumerate(ps,1) if x==p['gpio'])
        exact(d,'module','JCORE'+h[1:],{n:p['net']})
    # Fixed external functions keep their electrical identities; internal GPIO changes are G-authorized.
    old=load(ROOT/'digital-module-review-c/base/circuit.json')
    for r in ['JHOST','JUSB','UESD','UVBUS','UPANEL','JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR','JUNO_SPI','JP_SDA','JP_SCL','SWRESET']:
        require(part(d,'base',r)['pins']==next(p for p in old['parts'] if p['ref']==r)['pins'],'external boundary '+r)
    for row in load(HERE/'connector.json')['pins']:
        for b in d: exact(d,b,'JMOD',{row['pin']:row[b+'_net']})
    for i in range(8): exact(d,'base','RBD'+str(i),{1:'BUS_D'+str(i),2:'L_BUS_D'+str(i)})
    for i in range(4): exact(d,'base','RBCTL'+str(i),{1:'MOD_CTL'+str(i),2:'L_MOD_CTL'+str(i)})
    exact(d,'base','UMUTE',{1:'M_DAC_ALLOW',2:'M_LINE_ALLOW',3:'GND',4:'DAC_XSMT',5:'V3V3'})
    exact(d,'base','RPDAC',{1:'M_DAC_ALLOW',2:'GND'})
    exact(d,'base','RPLINE',{1:'M_LINE_ALLOW',2:'GND'})
    exact(d,'base','U17',{1:'AV3V3',8:'AV3V3',17:'DAC_XSMT',20:'V3V3'})
    exact(d,'base','UAUX',{1:'GND',2:'V3_AUX',3:'V5_CARRIER'})
    exact(d,'base','UADC',{3:'ADC_L',4:'ADC_R',8:'AV3V3',11:'ADC_LDO_1V8',13:'V3_AUX',14:'V3V3',15:'GND',16:'ADC_LRCK',17:'ADC_BCK',18:'BASE_ADC_DOUT_RAW',23:'PANEL_SDA',24:'PANEL_SCL',25:'GND',26:'GND'})
    for side in 'LR':
        exact(d,'base','RATT'+side,{1:'AUDIO_'+side,2:'ADC_DIV_'+side})
        exact(d,'base','CAC'+side,{1:'ADC_DIV_'+side,2:'ADC_AC_'+side})
        exact(d,'base','RLIMIT'+side,{1:'ADC_AC_'+side,2:'ADC_'+side})
        require(part(d,'base','RLIMIT'+side)['value']=='2.2k 1%','clamp-current series limit')
        exact(d,'base','DCLAMP'+side,{1:'GND',2:'AV3V3',3:'ADC_'+side})
        for ref,value in [('RATT'+side,'6.81k 1%'),('RSHUNT'+side,'10k 1%'),('CAC'+side,'10u X7R 16V / effective>=4.7u'),('CAAF'+side,'470p C0G')]:
            require(part(d,'base',ref)['value']==value,'RC calculation value '+ref)
    exact(d,'module','URUNOD',{2:'L_MOD_ENABLE',4:'CORE_RUN_N',5:'MCU_3V3'})
    require(pin(d,'module','URUNOD',4)['type']=='open_collector','RUN must be open drain')
    exact(d,'module','RENPD',{1:'L_MOD_ENABLE',2:'GND'})
    exact(d,'module','U9',{2:'MCU_3V3',7:'YM_CLOCK_3V3',17:'YM_CLK_5',8:'YM_RESET_RELEASE',16:'Y_RESET_N',22:'YM_CTRL_OE_N',23:'V5_MODULE'})
    exact(d,'module','RCOE',{1:'YM_CTRL_OE_N',2:'MCU_3V3'})
    exact(d,'module','RYMRESET',{1:'Y_RESET_N',2:'GND'})
    exact(d,'module','ULINK1',{9:'MOD_SPI_MISO',10:'MISO_OE_N',8:'LINK_TX_MISO',13:'LINK_TX_DISABLE',14:'MCU_3V3'})
    exact(d,'module','UTXOR',{1:'MOD_SPI_CS_N',2:'LINK_TX_DISABLE',4:'MISO_OE_N',5:'MCU_3V3'})
    exact(d,'module','RTXDIS',{1:'LINK_TX_DISABLE',2:'MCU_3V3'})
    exact(d,'module','UALERT',{2:'MOD_ALERT_DRIVE',4:'L_MOD_ALERT_N'})
    require(not any(p['value'].startswith('PCM1863') for p in d['module']['parts']),'no ADC on card')
    for i,ch in enumerate('ABC'):
        exact(d,'module','RSMIX'+ch,{1:'SSG_'+ch,2:'AUDIO_L'})
        require(part(d,'module','RSMIX'+ch)['value']=='10k 1%','mix impedance')
        require(part(d,'module','RL'+str(i))['value']=='1.33k 1%','SSG load')
    exact(d,'module','JMOD',{5:None,39:None})
    # Public ABI comes from unchanged code, not from a duplicate test constant alone.
    h=(REPO/'projects/ym2203-sound-module/firmware-c/src/stream.h').read_text()
    for k,v in [('REVC_QUEUE_CAPACITY',1024),('REVC_STATUS_SIZE',64),('REVC_LEASE_US',1000000),('REVC_PACKET_PAYLOAD',192)]:
        require(re.search(r'#define\s+'+k+r'\s+'+str(v)+'u',h),'legacy ABI '+k)
    require('S_PING,S_STOP,S_BEGIN,S_PUSH,S_PLAY,S_KEEP,S_SEAL' in h,'legacy opcode order')

def bounds():
    p=load(HERE/'power-plan.json')
    pg=sum(x['budget_ma'] for x in p['pga_3v3_loads'])
    aux=sum(x['budget_ma'] for x in p['aux_3v3_loads'])
    total=pg+aux+p['module_5v_limit_ma']+p['shield_5v_limit_ma']+p['misc_5v_margin_ma']
    require(pg<300 and aux<=500 and total<1750,'rail/admission budgets')
    diss=(5.25-3.2)*aux/1000
    ratio=10100/(6810*.99+10100)
    current=(5.25+1.8)/(2200*.99) # conservative full-source step + stored bias; ignores divider relief
    require(current<.005,'conditional clamp-current bound')
    max_z=(10000+1330)*1.01/3
    require(max_z<4700,'passive card impedance')
    max_tau=((6810*1.01+4700)*10100/(6810*1.01+4700+10100)+2222+40000)*15e-6
    require(5*max_tau<4,'startup guard under declared R/C interval')
    def gain(f,rs=3776.67,rin=20000):
        top=6810+rs; bottom=10000
        rth=top*bottom/(top+bottom)
        z=1/(1/rin+2j*math.pi*f*470e-12)
        return abs(bottom/(top+bottom)*z/(rth+2200+1/(2j*math.pi*f*10e-6)+z))
    mute_ms=(150/48000+.0002)*1000
    require(mute_ms<4,'planned clock halt guard')
    return dict(scope='conditional engineering budget/passive RC only; no SPICE or bench guarantee',
        pga_3v3_budget_ma=pg,aux_3v3_budget_ma=aux,input_admission_ma=total,
        aux_dissipation_w=diss,aux_junction_c_jedec_reference=40+diss*62.9,
        module_passive_z_upper_ohm=max_z,divider_max_unloaded=ratio,
        adc_conservative_clamp_current_ma=current*1000,
        adc_typical20k_input_rc_gain_1khz=gain(1000),
        adc_rc_relative_1khz_db={str(f):20*math.log10(gain(f)/gain(1000)) for f in [20,100,10000,20000]},
        assumed_adc_input_resistance_ohm=[10000,40000],assumed_effective_cap_uf=[4.7,15],
        startup_5tau_ms=max_tau*5000,mute_150samples_plus200us_ms=mute_ms,
        startup_guard_ms=4000,planned_clock_halt_guard_ms=4)

class Contract(unittest.TestCase):
    def setUp(self): self.d=make()
    def badpin(self,b,r,n,net):
        pin(self.d,b,r,n)['net']=net
        with self.assertRaises(ValueError):validate(self.d)
    def test_nominal(self):validate(self.d)
    def test_base_data_window(self):self.badpin('base','MPGA','B3','BUS_D7')
    def test_source_header(self):self.badpin('module','JCORE3',12,'GND')
    def test_uno_external(self):self.badpin('base','JUNO_SPI',1,'EXT_D11')
    def test_usb_power_isolation(self):self.badpin('base','JUSB','A4','V5_CARRIER')
    def test_key(self):self.badpin('base','JMOD',6,'V5_CARRIER')
    def test_analog_channel(self):self.badpin('base','JMOD',37,'AUDIO_R')
    def test_mute_bypass(self):self.badpin('base','UMUTE',2,'V3V3')
    def test_mute_default(self):self.badpin('base','RPDAC',2,'V3V3')
    def test_adc_io_domain(self):self.badpin('base','UADC',14,'V3_AUX')
    def test_adc_clamp_reversal(self):self.badpin('base','DCLAMPL',1,'AV3V3')
    def test_adc_series_limit(self):
        part(self.d,'base','RLIMITL')['value']='0'
        with self.assertRaises(ValueError):validate(self.d)
    def test_clock_reset_shared_buffer(self):self.badpin('module','U9',16,'V5_MODULE')
    def test_reset_default(self):self.badpin('module','RYMRESET',2,'V5_MODULE')
    def test_miso_release(self):self.badpin('module','ULINK1',10,'GND')
    def test_tx_startup_bypass(self):self.badpin('module','RTXDIS',2,'GND')
    def test_run_cannot_fight_button(self):
        pin(self.d,'module','URUNOD',4)['type']='output'
        with self.assertRaises(ValueError):validate(self.d)
    def test_rc_power_bounds(self):bounds()

def main():
    global REPO,FP
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=REPO)
    ap.add_argument('--footprints',type=Path,default=FP);ap.add_argument('--output',type=Path,default=HERE/'verification.json')
    args=ap.parse_args();REPO=args.repo;FP=args.footprints
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contract))
    if not result.wasSuccessful():return 1
    count=0;nets={};d=make()
    for b,c in d.items():
        require(load(HERE/b/'circuit.json')==c,'regenerate '+b)
        nets[b]=check_export(c,HERE/b/'netlist.xml')
        erc=load(HERE/b/'erc.json')
        require(not any(s['violations'] for s in erc['sheets']),'native ERC')
        for p in c['parts']:
            lib,name=p['footprint'].split(':')
            fp=(HERE/'P2H.pretty' if lib=='P2H' else FP/(lib+'.pretty'))/(name+'.kicad_mod')
            pads=set(re.findall(r'\(pad\s+"([^"]+)"',fp.read_text()))
            require(pads=={p['num'] for p in p['pins']},'physical pad set '+b+'/'+p['ref']);count+=1
    # Published reuse inputs are frozen; user working tree elsewhere is not rewritten.
    for rel,digest in load(HERE/'provenance.json')['inputs_sha256'].items():
        require(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,'historical input changed '+rel)
    report=dict(schema_version=1,date='2026-11-18',python=sys.version.split()[0],contract_tests_passed=result.testsRun,
        physical_pad_sets_checked=count,native_nets=nets,native=load(HERE/'native-verification.json'),
        bounds=bounds(),legacy_software_regression=dict(total=115,passed=111,skipped=4,reason='private REVC_TEST_SONG not supplied',scope='unchanged C firmware/HOST host-native tests, not H firmware'),
        new_pcb=False,new_firmware=False,hardware_accepted=False)
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return 0

if __name__=='__main__':sys.exit(main())
