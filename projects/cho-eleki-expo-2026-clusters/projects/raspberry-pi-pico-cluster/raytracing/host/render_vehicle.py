#!/usr/bin/env python3
"""Export/render the evolved vehicle with the same core used by Pico workers."""
from __future__ import annotations

import argparse
import binascii
import json
import math
from pathlib import Path
import sys
import time

from vehicle_scene import DEFAULT_SNAPSHOT, PRESETS, core, from_comparison, load_snapshot, make_job, model_id
from render_reference import write_png


def render(job, tile_size=8):
    core.validate_job(job)
    if type(tile_size) is not int or not 1 <= tile_size <= 32:
        raise ValueError('tile_size must be between 1 and 32')
    image = bytearray(job['width'] * job['height'] * 3)
    started = time.perf_counter()
    tiles = 0
    for y in range(0, job['height'], tile_size):
        for x in range(0, job['width'], tile_size):
            w, h = min(tile_size, job['width'] - x), min(tile_size, job['height'] - y)
            payload = core.compute_tile(job, x, y, w, h)
            for row in range(h):
                offset = ((y + row) * job['width'] + x) * 3
                image[offset:offset + w * 3] = payload[row * w * 3:(row+1) * w * 3]
            tiles += 1
    return image, {'elapsedMs': round((time.perf_counter() - started) * 1000, 3), 'tiles': tiles,
                   'crc32': '%08x' % (binascii.crc32(image) & 0xffffffff)}


def export_obj(snapshot, path):
    """32 chassis triangles, extruded support arms and 24-sided tire cylinders."""
    parts, wheels = core.geometry(snapshot['genome'])
    lines = ['# vehicle-extrusion-v1: visual approximation, not a 3D simulation',
             '# model sha256 ' + model_id(snapshot),
             '# source ' + json.dumps(snapshot['source'], ensure_ascii=False),
             'mtllib ' + Path(path).with_suffix('.mtl').name]
    count = 0

    def vertex(x, y, z):
        nonlocal count
        lines.append('v %.9f %.9f %.9f' % (x, y, z))
        count += 1
        return count

    def polygon(vertices, z0, z1, material, name):
        lines.extend(['o ' + name, 'usemtl ' + material])
        front = [vertex(x, y, z0) for x, y in vertices]
        back = [vertex(x, y, z1) for x, y in vertices]
        # Chassis is star-shaped about (0, lift); arms are convex. Fan from
        # centroid works for these radial/rectangular outlines, including concavity.
        cx = sum(x for x, y in vertices) / len(vertices)
        cy = sum(y for x, y in vertices) / len(vertices)
        if name == 'chassis':
            cy = wheels[0][1] - snapshot['genome'][11]
            cx = 0.0
        f, b = vertex(cx, cy, z0), vertex(cx, cy, z1)
        for i in range(len(front)):
            j = (i + 1) % len(front)
            lines.extend(['f %d %d %d' % (f, front[j], front[i]),
                          'f %d %d %d' % (b, back[i], back[j]),
                          'f %d %d %d' % (front[i], front[j], back[j]),
                          'f %d %d %d' % (front[i], back[j], back[i])])

    for i, (outline, z0, z1, material) in enumerate(parts):
        polygon(outline, z0, z1, 'body' if material == 0 else 'metal', 'chassis' if i == 0 else 'arm_%d' % i)
    for i, (cx, cy, radius, z0, z1) in enumerate(wheels):
        outline = [(cx + radius * math.cos(j * math.pi / 12), cy + radius * math.sin(j * math.pi / 12)) for j in range(24)]
        polygon(outline, z0, z1, 'tire', 'wheel_%d' % i)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n')
    path.with_suffix('.mtl').write_text('newmtl body\nKd 0.05 0.78 0.54\nKs 0.5 0.5 0.5\nNs 70\n\nnewmtl metal\nKd 0.58 0.65 0.72\nKs 0.7 0.7 0.7\nNs 88\n\nnewmtl tire\nKd 0.025 0.032 0.04\nKs 0.15 0.15 0.15\nNs 24\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='reference PNG path')
    parser.add_argument('--vehicle', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--preset', choices=PRESETS, default='preview')
    parser.add_argument('--terrain', action='store_true', help='include a scaled approximation of the source course')
    parser.add_argument('--tile-size', type=int, default=8)
    parser.add_argument('--obj', help='also export an OBJ/MTL model')
    parser.add_argument('--export-comparison', help='offline comparison/API JSON to export before rendering')
    args = parser.parse_args()
    try:
        output = Path(args.output)
        outputs = [output, output.with_suffix('.json')]
        if args.obj:
            outputs += [Path(args.obj), Path(args.obj).with_suffix('.mtl')]
        inputs = [Path(args.vehicle)] + ([Path(args.export_comparison)] if args.export_comparison else [])
        if len({p.resolve() for p in outputs}) != len(outputs) or any(p.resolve() in {q.resolve() for q in inputs} for p in outputs):
            raise ValueError('PNG/summary/OBJ/MTL outputs must be distinct from source files')
        if args.export_comparison:
            snapshot = from_comparison(args.export_comparison)
            target = Path(args.vehicle)
            if target.exists():
                raise ValueError('export destination already exists; choose a new --vehicle path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
        snapshot = load_snapshot(args.vehicle)
        job = make_job(snapshot, args.preset, terrain=args.terrain)
        image, summary = render(job, args.tile_size)
        write_png(args.output, image, job['width'], job['height'])
        if args.obj:
            export_obj(snapshot, args.obj)
        summary.update({'platform': 'CPython host reference, not Pico hardware',
                        'modelId': model_id(snapshot), 'source': snapshot['source'], 'job': job})
        Path(args.output).with_suffix('.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(summary, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, '車体の読込/描画に失敗: %s\n入力形式・保存先・--vehicleを確認してください。\n' % exc)


if __name__ == '__main__':
    main()
