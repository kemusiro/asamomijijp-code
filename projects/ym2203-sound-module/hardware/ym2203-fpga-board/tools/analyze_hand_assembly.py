#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check H1 area/I/O budgets and reproduce its conceptual drawing, not a PCB."""
import argparse
import hashlib
import json
from html import escape
from pathlib import Path

from analyze_layout import check_blocks, require


ROOT = Path(__file__).resolve().parents[1]


def generate():
    raw = (ROOT / 'hand-assembly-plan.json').read_bytes()
    plan = json.loads(raw)
    baseline_raw = (ROOT / plan['baseline_design']).read_bytes()
    baseline = json.loads(baseline_raw)['boards'][plan['baseline_board']]
    refs = {part['ref']: part for part in baseline['parts']}
    for ref in ('U2', 'U3'):
        require(refs[ref]['value'].startswith('74LCX245FT'), 'Rev C IC changed')
        require(refs[ref]['footprint']['pitch'] == 0.65, 'Rev C pitch changed')
    require(refs['R1']['footprint']['body'] == [3.2, 1.6], 'Rev C passive changed')
    blocks, size = plan['blocks'], plan['board_mm']
    check_blocks(blocks, size)
    holes = plan['holes_reserved']
    radius = holes['radius_mm']
    for cx, cy in holes['centres_mm']:
        require(radius <= cx <= size[0] - radius and radius <= cy <= size[1] - radius,
                'Mounting reservation outside outline')
        for block in blocks:
            x, y = block['xy']
            w, h = block['size']
            dx, dy = cx - min(max(cx, x), x + w), cy - min(max(cy, y), y + h)
            require(dx * dx + dy * dy >= radius * radius,
                    'Mounting reservation intersects ' + block['id'])
    for i, first in enumerate(blocks):
        for second in blocks[i + 1:]:
            x1, y1 = first['xy']
            w1, h1 = first['size']
            x2, y2 = second['xy']
            w2, h2 = second['size']
            dx = max(0, x1 - x2 - w2, x2 - x1 - w1)
            dy = max(0, y1 - y2 - h2, y2 - y1 - h1)
            require(dx * dx + dy * dy >= plan['minimum_region_gap_mm'] ** 2,
                    'Insufficient functional-area gap')
    io = plan['io_budget']
    used = sum(signal['count'] for signal in io['runtime_signals'])
    removed = sum(signal['count'] for signal in io['removed_from_direct_mount_34'])
    available = io['manufacturer_gpio'] - io['reserved_oscillator_gpio']
    require(used == 34 - removed and used <= available, 'I/O budget mismatch')
    require(not io['flash_spi_shared_with_runtime'] and not io['rgb_used'],
            'Budget assumes Flash/RGB independence')
    solder = plan['user_soldering']
    require(solder['minimum_direct_ic_pitch_mm'] >= 1.27 and not solder['bare_qfn_by_iron'],
            'Fine-pitch hand assembly introduced')
    area, baseline_area = size[0] * size[1], baseline['size_mm'][0] * baseline['size_mm'][1]
    report = {
        'schema_version': 1, 'date': plan['date'], 'status': plan['status'],
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'analysis_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'baseline_sha256': hashlib.sha256(baseline_raw).hexdigest(),
        'board_mm': size, 'area_mm2': area, 'baseline_area_mm2': baseline_area,
        'area_increase_percent': round(100 * (area / baseline_area - 1), 3),
        'reserved_area_mm2': sum(b['size'][0] * b['size'][1] for b in blocks),
        'regions': len(blocks), 'mounting_reservations': len(holes['centres_mm']),
        'io_required': used, 'io_conservative_capacity': available,
        'io_spare': available - used, 'io_removed_from_34': removed,
        'actual_footprints_placed': False, 'routed': False,
        'module_revision_pinout_verified': io['actual_board_revision_pinout_verified'],
        'not_modelled': plan['not_modelled'],
    }
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="950" viewBox="0 0 1280 950" role="img" aria-labelledby="title desc">',
        '<title id="title">H1 hand-soldered carrier concept, 180 by 140 mm</title>',
        '<desc id="desc">Preassembled UP5K, Pico 2 and clock modules; DIP and SOIC 1.27 mm ICs; 1206 passives. Rectangles are reserved functional areas, not footprints or wiring.</desc>',
        '<rect width="1280" height="950" fill="#ffffff"/>',
        '<g font-family="sans-serif" fill="#183047">',
        '<text x="35" y="35" font-size="25">H1 / Hand-soldered carrier / Pico 2 + iCE40UP5K</text>',
        '<text x="35" y="65" font-size="17" fill="#a02d24">CONCEPT ONLY: module dimensions, full BOM, pads and routing are not verified</text>',
        '<text x="35" y="93" font-size="16">Top view / USB access at top / analog output at bottom-right / dimensions in mm</text>',
    ]
    colors = {'power': '#fff0cd', 'module': '#e1edff', 'digital': '#def1e7', 'analog': '#f5e3f0'}
    scale, x0, y0 = 5, 35, 115
    svg.append(f'<rect x="{x0}" y="{y0}" width="{size[0] * scale}" height="{size[1] * scale}" rx="5" fill="#f7f9fc" stroke="#324c63" stroke-width="2"/>')
    for cx, cy in holes['centres_mm']:
        svg.append(f'<circle cx="{x0 + cx * scale}" cy="{y0 + cy * scale}" r="{radius * scale}" fill="#fff" stroke="#8191a4" stroke-dasharray="3 3"/>')
    for block in blocks:
        x, y = block['xy']
        w, h = block['size']
        px, py, bw, bh = x0 + x * scale, y0 + y * scale, w * scale, h * scale
        svg.append(f'<rect x="{px}" y="{py}" width="{bw}" height="{bh}" rx="5" fill="{colors[block["kind"]]}" stroke="#70859a"/>')
        for n, label in enumerate(block['labels']):
            svg.append(f'<text x="{px + bw / 2}" y="{py + 24 + n * 21}" font-size="13" text-anchor="middle">{escape(label)}</text>')
    legend = [
        ('PRIORITY', 'Working room over density'),
        ('USER IC SOLDERING', 'DIP: 2.54 mm'),
        ('', 'SOIC: 1.27 mm'),
        ('', 'No bare QFN / MSOP / TSSOP'),
        ('PASSIVES', '1206 first; 0805 optional'),
        ('FPGA MODULE', 'UPduino candidate, socketed'),
        ('', 'Flash boot; USB programming'),
        ('', 'Runtime SPI separate from Flash'),
        ('FPGA I/O BUDGET', f'{used} used / {available} conservative'),
        ('', f'{available - used} spare; revision audit pending'),
        ('CLOCKS', 'Si5351 -> SYS: 49.152 MHz'),
        ('', 'Si5351 -> AHCT74 /2 -> YM'),
        ('RESERVED OUTLINE', '180 x 140 mm / 25,200 mm2'),
        ('', '+31.25% vs Rev C 160 x 120'),
        ('NOT CHECKED', 'Actual footprints / wire routes'),
        ('', 'Power sequence / audio / costs'),
    ]
    for n, (heading, detail) in enumerate(legend):
        y = 145 + n * 38
        if heading:
            svg.append(f'<text x="975" y="{y}" font-size="13" font-weight="bold">{escape(heading)}</text>')
        svg.append(f'<text x="975" y="{y + 17}" font-size="12">{escape(detail)}</text>')
    svg.extend([
        '<text x="35" y="854" font-size="18">Functional area reservations only; blank space is not a proven routing budget.</text>',
        '<text x="35" y="885" font-size="16">Use preassembled modules for fine-pitch ICs. Reserve access for soldering, probes and module removal.</text>',
        '<text x="35" y="915" font-size="14">Source: hand-assembly-plan.json / Generated by tools/analyze_hand_assembly.py / MIT</text>',
        '</g></svg>',
    ])
    return report, '\n'.join(svg) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report, svg = generate()
    outputs = {
        ROOT / 'verification/hand-assembly-check.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        ROOT / 'hand-layout-study.svg': svg,
    }
    for path, content in outputs.items():
        if args.write:
            path.write_text(content)
        else:
            require(path.read_text() == content, 'Stale generated file: ' + path.name)
    print(f"PASS: H1 {report['board_mm']} mm; I/O {report['io_required']}/{report['io_conservative_capacity']}; {report['regions']} reserved areas; not a PCB")


if __name__ == '__main__':
    main()
