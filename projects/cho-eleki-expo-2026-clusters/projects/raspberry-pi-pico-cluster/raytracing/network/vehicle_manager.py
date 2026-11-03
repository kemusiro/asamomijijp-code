#!/usr/bin/env python3
"""One immutable vehicle job on Pico workers running vehicle_raytracer as core."""
from __future__ import annotations

import argparse
import binascii
import copy
import json
import os
from pathlib import Path
import re
import sys
import uuid

HOST = Path(__file__).resolve().parents[1] / 'host'
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
from vehicle_scene import DEFAULT_SNAPSHOT, PRESETS, core, load_snapshot, make_job, model_id
import ray_manager


class VehicleResultAssembler(ray_manager.RayResultAssembler):
    def __init__(self, job, tiles, job_id, output_path, expected_crc32=None):
        super().__init__(job, tiles, job_id, output_path)
        self.expected_crc32 = expected_crc32

    def finish(self):
        checksum = '%08x' % (binascii.crc32(self.image) & 0xffffffff)
        if self.expected_crc32 is not None and checksum != self.expected_crc32:
            raise ray_manager.protocol.ProtocolError('vehicle reference CRC mismatch: got ' + checksum)
        result = super().finish()
        # Tile CRC + completeness do not prove the image matches a reference.
        result.update({'accepted_checksum32': [self.expected_crc32] if self.expected_crc32 else None,
                       'checksum_matches': checksum == self.expected_crc32 if self.expected_crc32 else None,
                       'checksum_profile': 'explicit-reference' if self.expected_crc32 else None,
                       'known_pixels_match': None,
                       'validation': 'tile CRC + completeness' + (' + explicit image CRC' if self.expected_crc32 else '; image reference not verified')})
        return result


class VehicleWorkload(ray_manager.RayTracingWorkload):
    algorithm_version = core.ALGORITHM_VERSION

    def __init__(self, output_path, job, expected_crc32=None):
        super().__init__(output_path)
        core.validate_job(job)
        self.job = copy.deepcopy(job)
        if expected_crc32 is not None and re.fullmatch('[0-9a-f]{8}', expected_crc32) is None:
            raise ValueError('expected_crc32 must contain 8 lowercase hex characters')
        self.expected_crc32 = expected_crc32

    def create_assembler(self, job, tiles, job_id):
        if job != self.job:
            raise ValueError('vehicle job changed after snapshot')
        return VehicleResultAssembler(job, tiles, job_id, self.output_path, self.expected_crc32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vehicle', default=str(DEFAULT_SNAPSHOT))
    parser.add_argument('--preset', choices=PRESETS, default='preview')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--tile-size', type=int, default=8)
    parser.add_argument('--request-window', type=int, default=1)
    parser.add_argument('--worker-timeout', type=float, default=7.0)
    parser.add_argument('--timeout', type=float, default=180.0)
    parser.add_argument('--job-id', default='vehicle-' + uuid.uuid4().hex[:12])
    parser.add_argument('--expected-crc32', help='previously verified CRC for this exact job and worker float implementation')
    parser.add_argument('--output', required=True)
    parser.add_argument('--record-trace')
    args = parser.parse_args()
    try:
        if not 1 <= args.tile_size <= 16:
            raise ValueError('tile-size must be between 1 and 16; begin with 8 on Pico')
        snapshot = load_snapshot(args.vehicle)
        job = make_job(snapshot, args.preset)
        output = Path(args.output)
        # A failed/mistyped run must not destroy the previous good image.
        summary_path = output.with_suffix('.json')
        snapshot_path = output.with_suffix('.vehicle.json')
        paths = [output, summary_path, snapshot_path] + ([Path(args.record_trace)] if args.record_trace else [])
        if len(set(p.resolve() for p in paths)) != len(paths) or any(p.exists() for p in paths):
            raise ValueError('output/summary/snapshot/trace must be distinct new paths')
        workload = VehicleWorkload(output, job, args.expected_crc32)
        summary = ray_manager.cluster_manager.run_tcp_server(
            job, args.tile_size, args.host, args.port, args.timeout, args.job_id,
            request_window=args.request_window, worker_count=args.workers,
            worker_timeout=args.worker_timeout, record_path=args.record_trace,
            workload=workload,
            ready_callback=lambda address: print("READY " + json.dumps({"address": address, "jobId": args.job_id, "pid": os.getpid()}), flush=True))
        summary.update({'modelId': model_id(snapshot), 'source': snapshot['source'], 'jobSpec': job,
                        'note': 'image reference is unverified unless --expected-crc32 is supplied for this exact job/float implementation'})
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'type': 'summary', 'data': summary}, ensure_ascii=False))
    except (ValueError, OSError, TimeoutError, ray_manager.protocol.ProtocolError) as exc:
        parser.exit(1, '車体描画に失敗: %s\nworkerの描画コア版・接続台数・入力車体・未使用の出力先を確認してください。\n' % exc)
    except KeyboardInterrupt:
        parser.exit(130, '車体描画を中断しました。workerは再接続待ちへ戻ります。\n')


if __name__ == '__main__':
    main()
