#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check reserved functional rectangles; deliberately not PCB placement/DRC."""
import argparse
import hashlib
import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent.parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_blocks(blocks, size):
    ids = [block['id'] for block in blocks]
    require(len(set(ids)) == len(ids), 'Duplicate reserved area')
    for block in blocks:
        x, y = block['xy']
        w, h = block['size']
        require(w > 0 and h > 0, 'Nonpositive reserved area')
        require(x >= 0 and y >= 0 and x + w <= size[0] and y + h <= size[1],
                'Area outside proposed outline: ' + block['id'])
    for index, first in enumerate(blocks):
        for second in blocks[index + 1:]:
            x1, y1 = first['xy']
            w1, h1 = first['size']
            x2, y2 = second['xy']
            w2, h2 = second['size']
            overlap = x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1
            require(not overlap, f"Reserved areas overlap: {first['id']} / {second['id']}")


def generate():
    plan_bytes = (ROOT / 'architecture.json').read_bytes()
    plan = json.loads(plan_bytes)
    study = plan['layout_study']
    baseline_bytes = (PROJECT / plan['baseline_design']).read_bytes()
    baseline = json.loads(baseline_bytes)['boards'][study['baseline_board']]['size_mm']
    baseline_area = baseline[0] * baseline[1]
    blocks = study['blocks']
    roomy_blocks = []
    for block in blocks:
        x, y = block['xy']
        if x >= study['roomy_shift_from_x_mm']:
            x += study['roomy_shift_mm']
        roomy_blocks.append({**block, 'xy': [x, y]})
    variants = []
    for name, key, regions in [('compact_target', 'compact_target_mm', blocks),
                               ('roomy_comparison', 'roomy_comparison_mm', roomy_blocks)]:
        size = study[key]
        check_blocks(regions, size)
        reserved = sum(block['size'][0] * block['size'][1] for block in regions)
        area = size[0] * size[1]
        variants.append({
            'name': name, 'outline_mm': size, 'board_area_mm2': area,
            'area_reduction_target_percent': round(100 * (1 - area / baseline_area), 3),
            'reserved_functional_area_mm2': reserved,
            'unreserved_area_mm2_not_routing_capacity': area - reserved,
            'blocks': regions,
        })
    report = {
        'schema_version': 1, 'date': plan['date'], 'status': study['status'],
        'architecture_sha256': hashlib.sha256(plan_bytes).hexdigest(),
        'analysis_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'baseline_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
        'baseline_outline_mm': baseline, 'baseline_area_mm2': baseline_area,
        'variants': variants, 'not_modelled': study['not_modelled'],
        'actual_footprints_placed': False, 'routed': False, 'cost_quoted': False,
        'area_reduction_proven': False,
    }
    colors = {'retained': '#e0ecfa', 'power': '#fff0d0', 'digital': '#dff3e9', 'analog': '#f6e4f0'}
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 560" width="1120" height="560" role="img" aria-labelledby="title desc">',
        '<title id="title">Rev D assembly and size study</title>',
        '<desc id="desc">Rev C outline compared at the same scale with 100 by 100 and 120 by 100 millimetre targets. Colored rectangles reserve functional areas, not verified PCB footprints.</desc>',
        '<rect width="1120" height="560" fill="#fff"/>',
        '<g font-family="sans-serif" fill="#182c3c">',
        '<text x="24" y="28" font-size="21">Pico 2 retained / other ICs direct-mounted / single-side SMT proposal</text>',
        '<text x="24" y="54" font-size="15" fill="#9b301f">AREA RESERVATIONS ONLY - not routed, not manufacturing data, not a cost quote</text>',
    ]
    scale = 2.5

    def text(x, y, value, size=12, anchor='start'):
        svg.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">{escape(str(value))}</text>')

    for x0, label, size, regions in [
        (24, 'Rev C baseline', baseline, []),
        (464, 'Compact target', variants[0]['outline_mm'], blocks),
        (764, 'Roomy comparison', variants[1]['outline_mm'], roomy_blocks),
    ]:
        y0 = 110
        w, h = [value * scale for value in size]
        text(x0, 87, label, 18)
        svg.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" stroke="#263d50" stroke-width="2"/>')
        text(x0, y0 + h + 25, f'{size[0]} x {size[1]} mm / {size[0] * size[1]:,} mm2', 14)
        if not regions:
            text(x0 + w / 2, y0 + h / 2 - 10, '160 x 120 mm', 25, 'middle')
            text(x0 + w / 2, y0 + h / 2 + 18, 'Baseline outline only', 16, 'middle')
        else:
            for block in regions:
                x, y = block['xy']
                bw, bh = block['size']
                px, py = x0 + x * scale, y0 + y * scale
                svg.append(f'<rect x="{px}" y="{py}" width="{bw * scale}" height="{bh * scale}" rx="2" fill="{colors[block["kind"]]}" stroke="#738596" stroke-width="0.8"/>')
                text(px + bw * scale / 2, py + bh * scale / 2 - 1, block['label'], 8.5, 'middle')
                text(px + bw * scale / 2, py + bh * scale / 2 + 10, f'{bw} x {bh}', 8, 'middle')
            reduction = 100 * (1 - size[0] * size[1] / baseline_area)
            text(x0, y0 + h + 47, f'Area reduction target: {reduction:.1f}%', 13)
    text(464, 458, 'Same scale for all outlines; dimensions are mm.', 14)
    text(24, 518, 'Unreserved space must still accommodate routing, mounting holes and any underestimated circuit area.', 14)
    text(24, 542, 'No pin assignment, package substitution approval, electrical clearance or thermal validation is implied.', 14)
    svg.extend(['</g>', '</svg>'])
    return json.dumps(report, ensure_ascii=False, indent=2) + '\n', '\n'.join(svg) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report, svg = generate()
    outputs = [(ROOT / 'verification/layout-check.json', report), (ROOT / 'layout-study.svg', svg)]
    for path, content in outputs:
        if args.write:
            path.write_text(content, encoding='utf-8')
        else:
            require(path.read_text() == content, f'Stale {path.name}; use --write')
    print('PASS: reserved rectangles inside outlines, no overlaps; generated outputs match')
    for variant in json.loads(report)['variants']:
        print(variant['name'], variant['outline_mm'], 'target area reduction', variant['area_reduction_target_percent'], '%')
    print('NOT footprint placement, routing, DRC, mechanical approval or cost validation')


if __name__ == '__main__':
    main()
