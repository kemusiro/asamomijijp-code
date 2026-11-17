# SPDX-License-Identifier: MIT
"""Generate managed review CSV/SVG artifacts from the design JSON files."""
import argparse
import csv
import io
import json
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(p):
    return json.loads(p.read_text())


def csv_text(rows, columns):
    output = io.StringIO()
    writer = csv.DictWriter(output, columns, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def pin_svg(conn):
    colors = {'power':'#ffe0b2','ground':'#e2e8f0','key':'#fee2e2','analog':'#bbf7d0','digital':'#dbeafe'}
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="1160" viewBox="0 0 1040 1160">',
             '<rect width="1040" height="1160" fill="#f8fafc"/>',
             '<g font-family="Arial, sans-serif" fill="#0f172a">',
             '<text x="36" y="42" font-size="26" font-weight="bold">P2 review G - 40-position clean-sheet interface</text>',
             '<text x="36" y="72" font-size="17">Base mating face | A: odd / B: even | 2 x 20, 2.54 mm | KEY = 6</text>',
             '<text x="36" y="98" font-size="16">Design proposal only. Incompatible with older cards. Source solder view is mirrored.</text>']
    for p in conn['pins']:
        x = 36 if p['column']=='A' else 535
        y = 120+(p['row']-1)*47
        name = p['signal']
        aliases = ' / '.join(v for k,v in p['aliases'].items() if k=='SPI' and v!='aux_optional')
        subtitle = ('GP'+str(p['base_gpio']) if p['base_gpio'] is not None else p['kind'].upper())
        if aliases:
            subtitle += ' | SPI: '+aliases
        if name.startswith('SOUND_CLK'):
            subtitle = 'Si5351A -> source'
        parts += [f'<rect x="{x}" y="{y}" width="468" height="40" rx="5" fill="{colors[p["kind"]]}" stroke="#64748b"/>',
                  f'<text x="{x+9}" y="{y+26}" font-size="20" font-weight="bold">{p["pin"]:02}</text>',
                  f'<text x="{x+52}" y="{y+18}" font-size="16" font-weight="bold">{escape(name)}</text>',
                  f'<text x="{x+52}" y="{y+34}" font-size="12">{escape(subtitle)}</text>']
    parts += ['<text x="36" y="1092" font-size="17">GPIO0..7 = data | GPIO8..11 = control | GPIO14..18 = audio</text>',
              '<text x="36" y="1120" font-size="16">Green: analog | Blue: 3.3V digital | Gray: common GND | Orange: power | Red: key</text>',
              '</g></svg>']
    return '\n'.join(parts)+'\n'


def outputs(hardware_root):
    c, g = read(HERE/'connector.json'), read(HERE/'gpio-proposal.json')
    rows=[]
    for p in c['pins']:
        item=dict(p)
        item['aliases']=';'.join(k+'='+v for k,v in p['aliases'].items())
        rows.append(item)
    old=read(hardware_root/'parallel-module-interface-review-f/gpio-proposal.json')
    old_roles={p['net']:p['gpio'] for p in old['preserved_base']+old['additions']}
    old_roles.update({'BUS_D'+str(i):gp for i,gp in enumerate(old['parallel_data_gpio_lsb_first'])})
    # Logical identity of existing audio clocks/data, despite naming cleanup.
    old_roles.update({'DAC_I2S_DATA':26,'AUDIO_BCK':27,'AUDIO_LRCK':28})
    delta=[{'net':p['net'],'F_gpio':old_roles.get(p['net'],''),'G_gpio':p['gpio'],
            'changed':old_roles.get(p['net'])!=p['gpio']} for p in g['base']]
    return {'connector.csv':csv_text(rows,['pin','row','column','signal','kind','direction','voltage_v','base_gpio','aliases','note']),
            'gpio.csv':csv_text(g['base'],['gpio','module_pad','net','function','group','adc_channel']),
            'gpio-delta.csv':csv_text(delta,['net','F_gpio','G_gpio','changed']),
            'pinout.svg':pin_svg(c)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hardware-root',type=Path,default=HERE.parent)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for name,text in outputs(args.hardware_root).items():
        path=HERE/name
        if args.check:
            if not path.exists() or path.read_text()!=text:
                raise SystemExit('FAIL: stale generated artifact '+name)
        else:
            path.write_text(text)
    print('PASS:4 CSV/SVG artifacts '+('match source JSON' if args.check else 'generated from source JSON'))
