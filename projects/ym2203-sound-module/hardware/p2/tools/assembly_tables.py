#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Derive assembly tables from electrical BOMs, net contracts and preserved geometry."""
import collections
import csv
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
out = root / 'assembly'
out.mkdir(exist_ok=True)

def write(name, columns, rows):
    with (out / name).open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(columns)
        w.writerows(rows)

rows = []
groups = collections.defaultdict(list)
circuits = {}
for board in ('base', 'module', 'panel'):
    circuits[board] = json.loads((root / 'cad' / board / 'circuit.json').read_text())
    with (root / 'cad' / board / 'bom.csv').open() as f:
        bom = list(csv.DictReader(f))
    assert len(bom) == {'base': 155, 'module': 96, 'panel': 51}[board]
    assert len({p['Reference'] for p in bom}) == len(bom)
    for p in bom:
        rows.append([board, p['Reference'], p['Value'], p['Footprint'], 1, p['Datasheet'], p['Note']])
        groups[p['Value'], p['Footprint']].append((board + ':' + p['Reference'], p['Datasheet']))
assert len(rows) == 302 and len(groups) == 99
write('design-bom-1set.csv', ['board','ref','value','footprint','used_per_set','source','note'], rows)
write('grouped-design-bom.csv', ['value','footprint','used_for_1set','references','datasheets'],
      [[v,fp,len(ps),';'.join(p[0] for p in ps),';'.join(sorted({p[1] for p in ps if p[1]}))]
       for (v,fp),ps in sorted(groups.items())])

wires = []
for board, ref in [('base','UBASE'), ('module','USOURCE')]:
    part = next(p for p in circuits[board]['parts'] if p['ref'] == ref)
    swd = next(p for p in circuits[board]['parts'] if p['ref'] == 'JSWD')
    geometry = json.loads((root / 'cad' / board / 'electrical-geometry-before.json').read_text())
    fp = next(p for p in geometry['footprints'] if p['ref'] == ref)
    for number in ('JP1.1','JP1.2','JP1.3','SW1.S'):
        pin = next(p for p in part['pins'] if p['num'] == number)
        pad = next(p for p in fp['pads'] if p['number'] == number)
        if number == 'SW1.S':
            connection = 'module SW1 non-GND contact'
        else:
            connection = 'JSWD.' + next(p['num'] for p in swd['pins'] if p['net'] == pin['net'])
        wires.append([board,ref+'.'+number,pin['name'],pin['net'],*pad['pos'],connection,
                      'insulated wire; fit before mounting module'])
write('module-wire-map.csv', ['board','carrier_land','module_signal','net','carrier_x_mm','carrier_y_mm','connection','note'], wires)

links = {}
for board in ('base','module'):
    # The common connector is identified by its 40 numbered pins and KEY contact.
    parts = [p for p in circuits[board]['parts'] if len(p['pins']) == 40 and any(x['name']=='KEY' for x in p['pins'])]
    assert len(parts) == 1
    links[board] = {int(p['num']):p for p in parts[0]['pins']}
write('g40-pinout.csv', ['pin','base_function','base_net','module_function','module_net'],
      [[i,links['base'][i]['name'],links['base'][i]['net'],links['module'][i]['name'],links['module'][i]['net']] for i in range(1,41)])
print('Assembly tables: 302 references, 99 groups, 8 MCU wires, 40 connector pins')
