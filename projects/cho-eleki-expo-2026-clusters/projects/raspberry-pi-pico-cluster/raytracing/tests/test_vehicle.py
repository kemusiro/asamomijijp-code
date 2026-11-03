"""Geometry, rendering and multi-worker protocol tests for evolved vehicles."""
from __future__ import annotations

import binascii
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock
import io

ROOT = Path(__file__).resolve().parents[1]
for directory in ('host', 'pico', 'network'):
    sys.path.insert(0, str(ROOT / directory))
import vehicle_scene as scene
import render_vehicle
import vehicle_manager
import ray_manager
import network_protocol as protocol
core = scene.core


class VehicleTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = scene.load_snapshot(scene.DEFAULT_SNAPSHOT)
        self.job = scene.make_job(self.snapshot)

    def test_snapshot_is_the_best_physical_trial(self):
        artifact = ROOT.parents[1] / 'raspberry-pi-4-cluster/vehicle-evolution' / self.snapshot['source']['comparisonFile']
        data = json.loads(artifact.read_text())
        champion = max(data['results'], key=lambda r: r['champion']['distance'])['champion']
        self.assertEqual(self.snapshot['genome'], champion['genome'])
        self.assertEqual(self.snapshot['source']['distanceM'], champion['distance'])
        self.assertEqual(self.snapshot['source']['generation'], 69)
        self.assertEqual(self.snapshot['source']['comparisonSha256'], hashlib.sha256(artifact.read_bytes()).hexdigest())
        self.assertEqual(scene.from_comparison(artifact), self.snapshot)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'api-state.json'
            path.write_text(json.dumps({'comparison': {'results': data['results']}}))
            self.assertEqual(scene.from_comparison(path)['genome'], champion['genome'])

    def test_geometry_preserves_side_view_and_constant_width(self):
        genome = self.snapshot['genome']
        parts, wheels = core.geometry(genome)
        lift = wheels[0][1] - genome[11]
        for i, (x, y) in enumerate(parts[0][0]):
            self.assertAlmostEqual(x, genome[i] * math.cos(i * math.pi / 4))
            self.assertAlmostEqual(y - lift, genome[i] * math.sin(i * math.pi / 4))
        self.assertEqual(parts[0][1:3], (-.48, .48))
        self.assertEqual(len(wheels), 4)
        self.assertEqual([w[2] for w in wheels], [genome[8], genome[8], genome[9], genome[9]])
        self.assertEqual([w[0] for w in wheels], [-genome[10]]*2 + [genome[10]]*2)
        self.assertGreaterEqual(min(w[1]-w[2] for w in wheels), core.FLOOR - 1e-10)

    def test_cap_side_and_cylinder_intersections(self):
        core._prepare(self.snapshot['genome'])
        x, y = 0, core._wheels[0][1] - self.snapshot['genome'][11] + .15
        hit = core._nearest_hit(x, y, -4, 0, 0, 1)
        self.assertEqual(hit[1], 1)
        self.assertAlmostEqual(hit[0], 4 - core.HALF_WIDTH)
        self.assertEqual(hit[2:], (0, 0, -1))
        cx, cy, radius, z0, z1 = core._wheels[0]
        hit = core._nearest_hit(cx, cy, -4, 0, 0, 1)
        self.assertEqual(hit[1], 10)
        self.assertAlmostEqual(hit[0], 4 + z0)
        hit = core._nearest_hit(cx, cy, (z0+z1)/2, 1, 0, 0)
        self.assertEqual(hit[1], 10)
        self.assertAlmostEqual(hit[0], radius)
        self.assertAlmostEqual(hit[2], 1)
        # A vertical ray above chassis must hit the upper side with a unit normal.
        hit = core._nearest_hit(0, y+4, 0, 0, -1, 0)
        self.assertEqual(hit[1], 1)
        self.assertAlmostEqual(sum(n*n for n in hit[2:]), 1)
        self.assertFalse(core._box(4, 4, 4, 0, 1, 0, -1, 1, -1, 1, -1, 1, 100))

    def test_rejects_invalid_models_genes_and_quality(self):
        for genome in ([], [True]*13, [float('nan')]*13, [float('inf')]*13, [0]*13):
            job = dict(self.job, vehicle=genome)
            with self.assertRaises(ValueError):
                core.validate_job(job)
        for change in ({'model_version':'unknown'}, {'width':True}, {'height':641}, {'samples':3}, {'shadow_samples':False}, {'max_bounces':0}):
            with self.assertRaises(ValueError):
                core.validate_job(dict(self.job, **change))
        with self.assertRaises(ValueError):
            core.compute_tile(self.job, 159, 89, 2, 2)
        with self.assertRaises(ValueError):
            core.compute_tile_into(self.job, 0, 0, 8, 8, bytearray(2))

    def test_render_does_not_replace_input_with_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'car.json'
            source.write_text(json.dumps(self.snapshot))
            before=source.read_bytes()
            argv=['render_vehicle',str(source.with_suffix('.png')),'--vehicle',str(source)]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(sys,'stderr',io.StringIO()):
                with self.assertRaises(SystemExit) as result: render_vehicle.main()
            self.assertEqual(result.exception.code,1)
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse(source.with_suffix('.png').exists())

    def test_tiles_match_whole_image_and_different_models_do_not_leak(self):
        image, summary = render_vehicle.render(self.job, 8)
        other, _ = render_vehicle.render(self.job, 16)
        self.assertEqual(image, other)
        self.assertEqual(summary['crc32'], 'b051a116')
        changed = copy.deepcopy(self.snapshot)
        changed['genome'][8] = .25
        self.assertNotEqual(scene.model_id(changed), scene.model_id(self.snapshot))
        different, _ = render_vehicle.render(scene.make_job(changed), 16)
        self.assertNotEqual(image, different)
        restored, _ = render_vehicle.render(self.job, 16)
        self.assertEqual(image, restored)
        with self.assertRaises(ValueError):
            render_vehicle.render(self.job, 0)

    def test_obj_is_closed_with_consistent_face_winding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vehicle.obj'
            render_vehicle.export_obj(self.snapshot, path)
            rows = path.read_text().splitlines()
            self.assertTrue(path.with_suffix('.mtl').exists())
        vertices = [row for row in rows if row.startswith('v ')]
        faces = [[int(v) for v in row.split()[1:]] for row in rows if row.startswith('f ')]
        self.assertEqual(len(faces), 448)
        self.assertTrue(all(1 <= v <= len(vertices) for f in faces for v in f))
        directions = Counter((f[i], f[(i+1)%3]) for f in faces for i in range(3))
        self.assertTrue(all(directions[(b,a)] == count for (a,b), count in directions.items()))
        self.assertEqual(sum(row.startswith('o wheel_') for row in rows), 4)

    def test_job_is_snapshotted_and_unknown_reference_is_not_claimed_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            workload = vehicle_manager.VehicleWorkload(Path(directory)/'car.png', self.job)
            changed = copy.deepcopy(self.job)
            changed['vehicle'][0] += .1
            with self.assertRaises(ValueError):
                workload.create_assembler(changed, [], 'changed')
            for crc in ('XYZ', '000000000', True):
                with self.assertRaises((ValueError, TypeError)):
                    vehicle_manager.VehicleWorkload('unused.png', self.job, crc)
        self.assertNotEqual(core.ALGORITHM_VERSION, ray_manager.core.ALGORITHM_VERSION)
        with self.assertRaises(protocol.ProtocolError):
            protocol.validate_hello({'type':'hello','protocol_version':protocol.PROTOCOL_VERSION,
                                    'algorithm_version':ray_manager.core.ALGORITHM_VERSION,
                                    'output_version':core.OUTPUT_VERSION,'checksum_version':core.CHECKSUM_VERSION,
                                    'node_id':'old-worker','udp_port':40000}, algorithm_version=core.ALGORITHM_VERSION,
                                    output_version=core.OUTPUT_VERSION,checksum_version=core.CHECKSUM_VERSION)

    def test_three_workers_receive_same_model_and_assemble_exact_image(self):
        job = scene.make_job(self.snapshot, 'recovery')
        reference, summary = render_vehicle.render(job)
        pairs = [socket.socketpair() for _ in range(3)]
        received = []
        barrier = threading.Barrier(3)

        def worker(sock, index):
            try:
                protocol.send_frame(sock, {'type':'hello','protocol_version':protocol.PROTOCOL_VERSION,
                    'algorithm_version':core.ALGORITHM_VERSION, 'output_version':core.OUTPUT_VERSION,
                    'checksum_version':core.CHECKSUM_VERSION,'node_id':'vehicle-%d'%index,
                    'udp_port':40000+index,'start_transport':'tcp'})
                message, _ = protocol.recv_frame(sock)
                core.validate_job(message['job'])
                received.append(copy.deepcopy(message['job']))
                protocol.send_frame(sock, {'type':'ready','job_id':message['job_id']})
                start, _ = protocol.recv_frame(sock)
                self.assertEqual(start['type'], 'start')
                barrier.wait(timeout=5)
                while True:
                    tile, _ = protocol.recv_frame(sock)
                    if tile['type'] == 'complete':
                        return tile['checksum32']
                    payload = core.compute_tile(message['job'], tile['x0'],tile['y0'],tile['width'],tile['height'])
                    result = dict(tile, type='tile_result', payload_crc32='%08x'%(binascii.crc32(payload)&0xffffffff),compute_ms=1)
                    protocol.send_frame(sock, result, payload)
            finally:
                sock.close()

        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'network.png'
                workload = vehicle_manager.VehicleWorkload(path, job, summary['crc32'])
                session = ray_manager.cluster_manager.ManagerSession(job, tile_size=8, job_id='vehicle-network',
                    timeout=10, request_window=1, workload=workload)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = [pool.submit(worker, pair[1], i) for i,pair in enumerate(pairs)]
                    result = session.run_workers([(pair[0],lambda *_:None) for pair in pairs])
                    self.assertEqual([f.result(timeout=10) for f in futures], [summary['crc32']]*3)
                self.assertTrue(path.exists())
                self.assertEqual(result['checksum32'], summary['crc32'])
                self.assertTrue(result['checksum_matches'])
                self.assertEqual(result['tiles_completed'], 40)
                self.assertEqual(received, [job]*3)
                # Transport-only validation must not appear as image reference verification.
                tiles = ray_manager.build_full_frame_tiles(job, 64)
                a = vehicle_manager.VehicleResultAssembler(job, tiles, 'unverified', Path(directory)/'unknown.png')
                a.image[:] = reference
                a.completed = set(a.tiles)
                self.assertIsNone(a.finish()['checksum_matches'])
                b = vehicle_manager.VehicleResultAssembler(job, tiles, 'bad-crc', Path(directory)/'bad.png', '00000000')
                b.image[:] = reference; b.completed = set(b.tiles)
                with self.assertRaises(protocol.ProtocolError): b.finish()
                self.assertFalse((Path(directory)/'bad.png').exists())
        finally:
            for pair in pairs:
                for sock in pair:
                    sock.close()


if __name__ == '__main__':
    unittest.main()
