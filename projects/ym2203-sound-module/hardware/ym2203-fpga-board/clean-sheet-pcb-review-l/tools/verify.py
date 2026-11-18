#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the L USB correction against J, native reports and retained K/B interfaces."""
import argparse
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import copy
import zipfile
import pcbnew as P

HERE = Path(__file__).resolve().parents[1]
MM = lambda v: [round(P.ToMM(v.x), 6), round(P.ToMM(v.y), 6)]
SHA = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()


def usb_rows(fp):
    return [{'pin': d.GetNumber(), 'xy': MM(d.GetFPRelativePosition()),
             'size': MM(d.GetSize()), 'drill': MM(d.GetDrillSize()),
             'net': d.GetNetname(), 'shape': int(d.GetShape())} for d in fp.Pads()]


def usb_contract(rows, position, angle):
    assert position == [133, 5.79] and angle == 180, 'USB board-edge datum'
    holes = sorted(r['xy'] + r['drill'] for r in rows if not r['pin'])
    assert holes == [[-2.89, 0, .6, .6], [2.89, 0, .6, .6]], 'USB positioning holes'
    shell = sorted(r['xy'] + r['size'] + r['drill'] for r in rows if r['pin'] == 'SH')
    assert shell == [[x, y, .9, size, .6, drill] for x in [-4.325, 4.325]
                     for y, size, drill in [(-.5, 2, 1.7), (3.68, 1.7, 1.4)]], 'USB shell'
    x = {'A1': -3.2, 'A4': -2.4, 'A5': -1.25, 'A6': -.25, 'A7': .25,
         'A8': 1.25, 'A9': 2.4, 'A12': 3.2, 'B1': 3.2, 'B4': 2.4,
         'B5': 1.75, 'B6': .75, 'B7': -.75, 'B8': -1.75, 'B9': -2.4, 'B12': -3.2}
    nets = {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND',
            'A4': 'USB_VBUS_RAW', 'A9': 'USB_VBUS_RAW', 'B4': 'USB_VBUS_RAW', 'B9': 'USB_VBUS_RAW',
            'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DM', 'B7': 'USB_DM'}
    sig = {r['pin']: r for r in rows if r['pin'] and r['pin'] != 'SH'}
    assert set(sig) == set(x), 'USB sixteen contact set'
    for pin, r in sig.items():
        assert r['xy'] == [x[pin], -1.07], ('USB contact coordinate', pin)
        assert r['size'] == [.6 if pin in ['A1', 'A4', 'A9', 'A12', 'B1', 'B4', 'B9', 'B12'] else .3, 1.14]
        if pin in nets:
            assert r['net'] == nets[pin], ('USB contact net', pin)
        else:
            assert r['net'].startswith('unconnected-'), 'SBU must remain unconnected'
        assert r['shape'] == int(P.PAD_SHAPE_OVAL if pin in ['A1', 'A12', 'B1', 'B12'] else P.PAD_SHAPE_ROUNDRECT)


def outside_segments(t):
    """Clip only centreline portions outside the USB work rectangle, in mm."""
    lo, hi = [127, 0], [140, 12.5]
    if isinstance(t, P.PCB_VIA):
        a = MM(t.GetPosition())
        return [] if all(lo[i] <= a[i] <= hi[i] for i in [0, 1]) else [
            ('via', *a, t.GetWidth(P.F_Cu), t.GetDrillValue(), t.GetNetname())]
    a, b = MM(t.GetStart()), MM(t.GetEnd())
    d = [b[i] - a[i] for i in [0, 1]]
    enter, leave = 0., 1.
    for i in [0, 1]:
        if abs(d[i]) < 1e-12:
            if not lo[i] <= a[i] <= hi[i]:
                enter, leave = 1., 0.
                break
        else:
            u, v = sorted([(lo[i] - a[i]) / d[i], (hi[i] - a[i]) / d[i]])
            enter, leave = max(enter, u), min(leave, v)
    intervals = [(0., 1.)] if enter > leave else [(0., enter), (leave, 1.)]
    result = []
    for u, v in intervals:
        if v - u < 1e-9:
            continue
        ends = sorted(tuple(round(a[i] + z * d[i], 5) for i in [0, 1]) for z in [u, v])
        result.append(('track', *ends[0], *ends[1], t.GetLayer(), t.GetWidth(), t.GetNetname()))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hardware-root', type=Path, default=HERE.parent)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--outputs', type=Path)
    args = ap.parse_args()
    hw, base = args.hardware_root, HERE / 'base'
    j = P.LoadBoard(str(hw / 'clean-sheet-pcb-review-j/base/p2-base-j.kicad_pcb'))
    l = P.LoadBoard(str(base / 'p2-base-l.kicad_pcb'))
    old = {f.GetReference(): f for f in j.GetFootprints()}
    new = {f.GetReference(): f for f in l.GetFootprints()}
    assert set(old) == set(new) and len(new) == 164
    read = lambda f: json.loads(f.read_text())
    c0 = read(hw / 'clean-sheet-pcb-review-j/base/circuit.json')
    c1 = read(base / 'circuit.json')
    assert len(c1['parts']) == 152
    for a, b in zip(c0['parts'], c1['parts']):
        if a['ref'] == 'JUSB':
            assert {k: v for k, v in a.items() if k not in ['footprint', 'source']} == {
                k: v for k, v in b.items() if k not in ['footprint', 'source']}
        else:
            assert a == b
    pads = 0
    for ref, f in new.items():
        of = old[ref]
        assert [(p.GetNumber(), p.GetNetname()) for p in f.Pads()] == [(p.GetNumber(), p.GetNetname()) for p in of.Pads()]
        pads += sum(bool(p.GetNumber()) for p in f.Pads())
        if ref != 'JUSB':
            assert MM(f.GetPosition()) == MM(of.GetPosition()) and f.GetOrientationDegrees() == of.GetOrientationDegrees()
            assert f.GetLayer() == of.GetLayer() and (str(f.GetFPID().GetLibNickname()), str(f.GetFPID().GetLibItemName())) == (str(of.GetFPID().GetLibNickname()), str(of.GetFPID().GetLibItemName())) and f.GetValue() == of.GetValue()
            assert usb_rows(f) == usb_rows(of), 'Non-USB pad geometry changed: ' + ref
    assert pads == 571
    rows = usb_rows(new['JUSB'])
    usb_contract(rows, MM(new['JUSB'].GetPosition()), new['JUSB'].GetOrientationDegrees())
    rejection = []
    try:
        usb_contract(usb_rows(old['JUSB']), MM(old['JUSB'].GetPosition()), old['JUSB'].GetOrientationDegrees())
    except AssertionError:
        rejection.append('old J land pattern')
    else:
        raise AssertionError('Old footprint unexpectedly accepted')
    for label in ['positioning hole 0.65', 'rear slot 1.20', 'D+/D- swapped', 'missing contact']:
        q = copy.deepcopy(rows)
        if label == 'positioning hole 0.65':
            next(x for x in q if not x['pin'])['drill'] = [.65, .65]
        elif label == 'rear slot 1.20':
            next(x for x in q if x['pin'] == 'SH' and x['xy'][1] > 0)['drill'] = [.6, 1.2]
        elif label == 'D+/D- swapped':
            next(x for x in q if x['pin'] == 'A6')['net'] = 'USB_DM'
        else:
            q = [x for x in q if x['pin'] != 'B6']
        try:
            usb_contract(q, [133, 5.79], 180)
        except AssertionError:
            rejection.append(label)
        else:
            raise AssertionError('Mutation accepted: ' + label)
    assert Counter(q for t in j.GetTracks() for q in outside_segments(t)) == Counter(
        q for t in l.GetTracks() for q in outside_segments(t)), 'Copper outside USB region changed'
    assert read(base / 'p2-base-l.kicad_pro') == read(hw / 'clean-sheet-pcb-review-j/base/p2-base-j.kicad_pro'), 'Design rules changed'
    assert not read(base / 'p2-base-l.kicad_pro')['board']['design_settings']['drc_exclusions']
    zones = lambda b: sorted((z.GetNetname(), z.GetLayerSet().FmtHex(), z.Outline().Format()) for z in b.Zones())
    assert zones(j) == zones(l), 'Zone outlines changed'
    assert l.GetCopperLayerCount() == 4 and not any(
        not isinstance(t, P.PCB_VIA) and t.GetLayer() == P.In1_Cu for t in l.GetTracks())
    drc, erc = read(base / 'drc.json'), read(base / 'erc.json')
    assert not any(drc[k] for k in ['violations', 'unconnected_items', 'schematic_parity'])
    assert not any(s['violations'] for s in erc['sheets'])
    card = P.LoadBoard(str(hw / 'clean-sheet-pcb-review-k/module/p2-ym2203-k.kicad_pcb'))
    cf = next(f for f in card.GetFootprints() if f.GetReference() == 'JMOD')
    cp = {p.GetNumber(): MM(p.GetPosition()) for p in cf.Pads()}
    g40 = max(math.dist(MM(p.GetPosition()), [cp[p.GetNumber()][0] + 90, cp[p.GetNumber()][1] + 38]) for p in new['JMOD'].Pads())
    assert g40 < 1e-6
    shield = P.LoadBoard(str(hw / 'editor-shield-review-b/pcb-review-b/p2-editor-b.kicad_pcb'))
    sf = {f.GetReference(): f for f in shield.GetFootprints()}
    errors = []
    for sr, br in [('J1', 'JUNO_D0'), ('J2', 'JUNO_D8'), ('J3', 'JUNO_A'), ('J4', 'JUNO_PWR')]:
        want = {p.GetNumber(): MM(p.GetPosition()) for p in new[br].Pads()}
        errors.extend(math.dist(MM(p.GetPosition()), want[p.GetNumber()]) for p in sf[sr].Pads())
    assert len(errors) == 32 and max(errors) < 1e-6
    solder = []
    for via in l.GetTracks():
        if not isinstance(via, P.PCB_VIA):
            continue
        hole = P.SHAPE_CIRCLE(via.GetPosition(), via.GetDrillValue() // 2 + P.FromMM(.05))
        for ref, fp in new.items():
            for pad in fp.Pads():
                if pad.GetDrillSize().x or pad.GetNetname() != via.GetNetname():
                    continue
                if any(pad.IsOnLayer(layer) and pad.GetEffectiveShape(layer).Collide(hole, 0)
                       for layer in [P.F_Cu, P.B_Cu]):
                    solder.append({'board': 'base', 'ref': ref, 'pin': pad.GetNumber(),
                                   'net': via.GetNetname(), 'via_mm': MM(via.GetPosition()),
                                   'drill_mm': P.ToMM(via.GetDrillValue())})
    expected_solder = read(hw / 'primary-order-5pcb-1set/assembly-vias.json')['sites_by_board']['base-j4']
    assert sorted(solder, key=str) == sorted(expected_solder, key=str), 'SMT prefill sites changed'
    for rel, digest in read(HERE / 'preservation.json').items():
        assert SHA(hw / rel) == digest, 'Historical source changed: ' + rel
    result = {'revision': '3.8-pcb-review-l', 'toolchain': P.GetBuildVersion(),
              'components': 152, 'pcb_only_holes': 12, 'physical_pad_checks': pads,
              'segments': sum(not isinstance(t, P.PCB_VIA) for t in l.GetTracks()),
              'vias': sum(isinstance(t, P.PCB_VIA) for t in l.GetTracks()),
              'erc': 0, 'drc': 0, 'unconnected': 0, 'parity': 0,
              'rules_unchanged': True, 'per_violation_exclusions': 0,
              'usb_work_region_mm': [127, 0, 140, 12.5], 'outside_track_via_geometry_unchanged': True,
              'non_usb_footprints_unchanged': 163, 'g40_positions': len(cp), 'g40_error_mm': round(g40, 6),
              'shield_mates': len(errors), 'shield_error_mm': round(max(errors), 6), 'rejected_regressions': rejection,
              'base_prefill_sites': solder,
              'usb_pads': rows, 'hardware_accepted': False, 'firmware_changed': False,
              'native_sha256': {str(f.relative_to(HERE)): SHA(f) for f in sorted(base.iterdir())
                                if f.suffix in ['.kicad_pcb', '.kicad_pro', '.kicad_sch'] or f.name in ['erc.json', 'drc.json', 'circuit.json']}}
    f = HERE / 'verification.json'
    if args.write:
        f.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    else:
        assert read(f) == result, 'Recorded verification differs'
        for name, sha in read(HERE / 'manifest.json')['files'].items():
            assert SHA(HERE / name) == sha, 'Delivered file changed: ' + name
        binding = read(HERE / 'manufacturing/input-binding.json')
        assert binding['source_board_sha256'] == SHA(base / 'p2-base-l.kicad_pcb')
        assert binding['source_board_sha256'] == binding['cam_work_board_sha256']
        cam = read(HERE / 'manufacturing/cam-verification.json')['boards']['base-l4']
        assert cam['cam_matches_native'] and cam['copper_layers'] == 4 and cam['outline_mm'] == [220, 142]
        assert cam['drills']['PTH']['holes_and_slots'] == 431 and cam['drills']['NPTH']['holes_and_slots'] == 14
        if args.outputs:
            archive = args.outputs / 'p2-base-l4-gerber.zip'
            assert SHA(archive) == read(HERE / 'local-outputs.json')['files'][archive.name]
            with zipfile.ZipFile(archive) as z:
                assert z.testzip() is None
                assert {n: z.read(n) for n in z.namelist()} == {
                    p.name: p.read_bytes() for p in (HERE / 'manufacturing/gerbers').iterdir() if p.is_file()}
    print('PASS: USB land bounds/holes/edge/pin nets, 571 pads, 40 G40 and 32 shield mates; '
          'rules and copper outside local region unchanged; 5 bad patterns rejected; no bench claim')


if __name__ == '__main__':
    main()
