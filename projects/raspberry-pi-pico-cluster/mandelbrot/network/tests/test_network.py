"""Host-only tests for the multi-Pico network prototype."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import binascii
from pathlib import Path
import queue
import select
import socket
import sys
import threading
import time
import unittest

NETWORK_DIR = Path(__file__).resolve().parents[1]
MANDELBROT_DIR = NETWORK_DIR.parent
HOST_DIR = MANDELBROT_DIR / "host"
for directory in (str(NETWORK_DIR), str(HOST_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import manager  # noqa: E402
import mock_worker  # noqa: E402
import network_protocol as protocol  # noqa: E402
from mandelbrot_reference import (  # noqa: E402
    EXHIBITION_JOB,
    SMALL_JOB,
    render_reference_float32,
)


def tile_payload(image, job, tile):
    output = bytearray(tile["width"] * tile["height"])
    offset = 0
    for local_y in range(tile["height"]):
        source = (tile["y0"] + local_y) * job["width"] + tile["x0"]
        output[offset : offset + tile["width"]] = image[
            source : source + tile["width"]
        ]
        offset += tile["width"]
    return output


def result_message(job_id, tile, payload):
    message = dict(tile)
    message.update(
        {
            "type": "tile_result",
            "job_id": job_id,
            "payload_crc32": "%08x" % (binascii.crc32(payload) & 0xFFFFFFFF),
            "compute_ms": 1,
            "mem_free_min_sampled": 12345,
        }
    )
    return message


class ProtocolTests(unittest.TestCase):
    def test_frame_round_trip_with_binary_payload(self):
        left, right = socket.socketpair()
        try:
            expected = bytes(range(256))
            protocol.send_frame(left, {"type": "tile_result", "tile_id": 7}, expected)
            message, payload = protocol.recv_frame(right)
            self.assertEqual(message["type"], "tile_result")
            self.assertEqual(message["tile_id"], 7)
            self.assertEqual(bytes(payload), expected)
        finally:
            left.close()
            right.close()

    def test_fragmented_frame_is_reassembled(self):
        left, right = socket.socketpair()
        frame = protocol.encode_frame({"type": "ready", "job_id": "j-1"})

        def send_fragments():
            for value in frame:
                left.send(bytes((value,)))
            left.close()

        thread = threading.Thread(target=send_fragments)
        thread.start()
        try:
            message, payload = protocol.recv_frame(right)
            self.assertEqual(message["job_id"], "j-1")
            self.assertEqual(payload, b"")
        finally:
            right.close()
            thread.join()

    def test_start_datagram_rejects_other_job(self):
        data = protocol.make_start_datagram("job-a")
        self.assertEqual(protocol.parse_start_datagram(data, "job-a")["type"], "start")
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_start_datagram(data, "job-b")

    def test_incompatible_worker_is_rejected(self):
        hello = {
            "type": "hello",
            "protocol_version": "mandelbrot-wire-v1",
            "algorithm_version": protocol.ALGORITHM_VERSION,
            "output_version": protocol.OUTPUT_VERSION,
            "checksum_version": protocol.CHECKSUM_VERSION,
            "node_id": "pico-1",
            "udp_port": 40000,
        }
        with self.assertRaises(protocol.ProtocolError):
            protocol.validate_hello(hello)


class AssemblyTests(unittest.TestCase):
    def test_upper_half_tiles_cover_half_the_small_job(self):
        tiles = manager.build_upper_half_tiles(SMALL_JOB, 4)
        self.assertEqual(len(tiles), 2)
        self.assertEqual(sum(t["width"] * t["height"] for t in tiles), 32)

    def test_exhibition_results_are_mirrored_and_verified(self):
        image = render_reference_float32(EXHIBITION_JOB)
        tiles = manager.build_upper_half_tiles(EXHIBITION_JOB, 16)
        assembler = manager.ResultAssembler(EXHIBITION_JOB, tiles, "full-job")
        for tile in tiles:
            payload = tile_payload(image, EXHIBITION_JOB, tile)
            assembler.accept(result_message("full-job", tile, payload), payload)
        summary = assembler.finish()
        self.assertEqual(summary["checksum32"], "1a26b685")
        self.assertEqual(summary["tiles_completed"], 320)
        self.assertEqual(summary["payload_bytes_received"], 81920)
        self.assertTrue(summary["known_pixels_match"])

    def test_bad_crc_and_duplicate_are_rejected(self):
        image = render_reference_float32(SMALL_JOB)
        tiles = manager.build_upper_half_tiles(SMALL_JOB, 4)
        tile = tiles[0]
        payload = tile_payload(image, SMALL_JOB, tile)
        bad = result_message("small", tile, payload)
        bad["payload_crc32"] = "00000000"
        assembler = manager.ResultAssembler(SMALL_JOB, tiles, "small")
        with self.assertRaises(protocol.ProtocolError):
            assembler.accept(bad, payload)

        message = result_message("small", tile, payload)
        assembler.accept(message, payload)
        with self.assertRaises(protocol.ProtocolError):
            assembler.accept(message, payload)


class SessionTests(unittest.TestCase):
    def test_request_window_must_be_a_bounded_integer(self):
        for invalid in (0, manager.MAX_REQUEST_WINDOW + 1, 1.5, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                manager.ManagerSession(SMALL_JOB, request_window=invalid)

    def test_worker_timeout_must_be_in_documented_range(self):
        for invalid in (
            manager.MIN_WORKER_TIMEOUT_SECONDS - 0.01,
            manager.MAX_WORKER_TIMEOUT_SECONDS + 0.01,
            True,
            "5",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                manager.ManagerSession(SMALL_JOB, worker_timeout=invalid)

    def test_start_notification_waits_for_every_worker_ready(self):
        manager_one, worker_one = socket.socketpair()
        manager_two, worker_two = socket.socketpair()
        start_event = threading.Event()
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=4,
            job_id="socketpair-ready-barrier",
            timeout=5,
            request_window=1,
        )

        def hello(node_id):
            return {
                "type": "hello",
                "protocol_version": protocol.PROTOCOL_VERSION,
                "algorithm_version": protocol.ALGORITHM_VERSION,
                "output_version": protocol.OUTPUT_VERSION,
                "checksum_version": protocol.CHECKSUM_VERSION,
                "node_id": node_id,
                "udp_port": 40001,
            }

        notifier = lambda _hello, _job_id: start_event.set()
        with ThreadPoolExecutor(max_workers=1) as pool:
            manager_future = pool.submit(
                session.run_workers,
                [(manager_one, notifier), (manager_two, notifier)],
            )
            try:
                protocol.send_frame(worker_one, hello("mock-pico-ready-1"))
                first_job, _payload = protocol.recv_frame(worker_one)
                protocol.send_frame(
                    worker_one,
                    {"type": "ready", "job_id": first_job["job_id"]},
                )
                self.assertFalse(start_event.wait(0.05))

                protocol.send_frame(worker_two, hello("mock-pico-ready-2"))
                second_job, _payload = protocol.recv_frame(worker_two)
                self.assertFalse(start_event.is_set())
                protocol.send_frame(
                    worker_two,
                    {"type": "ready", "job_id": second_job["job_id"]},
                )
                self.assertTrue(start_event.wait(2))
                worker_one.close()
                worker_two.close()
                with self.assertRaises(protocol.ProtocolError):
                    manager_future.result(timeout=5)
            finally:
                worker_one.close()
                worker_two.close()
                manager_one.close()
                manager_two.close()

    def test_manager_prefills_bounded_window_and_accepts_reordered_results(self):
        manager_socket, worker_socket = socket.socketpair()
        worker_socket.settimeout(2)
        start_event = threading.Event()
        request_window = 3
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=2,
            job_id="socketpair-windowed",
            timeout=5,
            request_window=request_window,
        )

        def notify(_hello, _job_id):
            start_event.set()

        with ThreadPoolExecutor(max_workers=1) as pool:
            manager_future = pool.submit(session.run, manager_socket, notify)
            try:
                protocol.send_frame(
                    worker_socket,
                    {
                        "type": "hello",
                        "protocol_version": protocol.PROTOCOL_VERSION,
                        "algorithm_version": protocol.ALGORITHM_VERSION,
                        "output_version": protocol.OUTPUT_VERSION,
                        "checksum_version": protocol.CHECKSUM_VERSION,
                        "node_id": "mock-pico-windowed",
                        "udp_port": 40001,
                    },
                )
                job_message, payload = protocol.recv_frame(worker_socket)
                self.assertEqual(payload, b"")
                protocol.send_frame(
                    worker_socket,
                    {"type": "ready", "job_id": job_message["job_id"]},
                )
                self.assertTrue(start_event.wait(2))

                remaining = job_message["tile_count"]
                first_batch = True
                while remaining:
                    batch_size = min(request_window, remaining)
                    batch = []
                    for _index in range(batch_size):
                        tile, payload = protocol.recv_frame(worker_socket)
                        protocol.require_message_type(tile, "tile")
                        self.assertEqual(payload, b"")
                        batch.append(tile)

                    if first_batch:
                        readable, _writable, _exceptional = select.select(
                            [worker_socket], [], [], 0.05
                        )
                        self.assertEqual(readable, [])
                        first_batch = False

                    for tile in reversed(batch):
                        result = mock_worker.compute_reference_tile(SMALL_JOB, tile)
                        protocol.send_frame(
                            worker_socket,
                            result_message(job_message["job_id"], tile, result),
                            result,
                        )
                    remaining -= batch_size

                complete, payload = protocol.recv_frame(worker_socket)
                protocol.require_message_type(complete, "complete")
                self.assertEqual(payload, b"")
                manager_result = manager_future.result(timeout=5)
            finally:
                manager_socket.close()
                worker_socket.close()

        self.assertEqual(manager_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["tiles_completed"], 8)
        self.assertEqual(manager_result["request_window"], request_window)

    def test_duplicate_result_is_ignored_without_double_completion(self):
        manager_socket, worker_socket = socket.socketpair()
        start_event = threading.Event()
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=4,
            job_id="socketpair-duplicate",
            timeout=5,
            request_window=1,
        )

        with ThreadPoolExecutor(max_workers=1) as pool:
            manager_future = pool.submit(
                session.run,
                manager_socket,
                lambda _hello, _job_id: start_event.set(),
            )
            try:
                protocol.send_frame(
                    worker_socket,
                    {
                        "type": "hello",
                        "protocol_version": protocol.PROTOCOL_VERSION,
                        "algorithm_version": protocol.ALGORITHM_VERSION,
                        "output_version": protocol.OUTPUT_VERSION,
                        "checksum_version": protocol.CHECKSUM_VERSION,
                        "node_id": "mock-pico-duplicate",
                        "udp_port": 40001,
                    },
                )
                job_message, _payload = protocol.recv_frame(worker_socket)
                protocol.send_frame(
                    worker_socket,
                    {"type": "ready", "job_id": job_message["job_id"]},
                )
                self.assertTrue(start_event.wait(2))

                first_tile, _payload = protocol.recv_frame(worker_socket)
                first_result = mock_worker.compute_reference_tile(SMALL_JOB, first_tile)
                first_message = result_message(
                    job_message["job_id"], first_tile, first_result
                )
                protocol.send_frame(worker_socket, first_message, first_result)
                protocol.send_frame(worker_socket, first_message, first_result)
                stale_message = dict(first_message)
                stale_message["job_id"] = "previous-job"
                protocol.send_frame(worker_socket, stale_message, first_result)

                second_tile, _payload = protocol.recv_frame(worker_socket)
                second_result = mock_worker.compute_reference_tile(
                    SMALL_JOB, second_tile
                )
                protocol.send_frame(
                    worker_socket,
                    result_message(
                        job_message["job_id"], second_tile, second_result
                    ),
                    second_result,
                )
                complete, _payload = protocol.recv_frame(worker_socket)
                protocol.require_message_type(complete, "complete")
                manager_result = manager_future.result(timeout=5)
            finally:
                manager_socket.close()
                worker_socket.close()

        self.assertEqual(manager_result["tiles_completed"], 2)
        self.assertEqual(manager_result["ignored_tile_results"], 2)

    def test_small_job_over_socket_pair(self):
        manager_socket, worker_socket = socket.socketpair()
        start_event = threading.Event()
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=4,
            job_id="socketpair-small",
            timeout=5,
            request_window=1,
        )

        def notify(_hello, _job_id):
            start_event.set()

        def await_start(_job_id):
            if not start_event.wait(2):
                raise RuntimeError("start notification timed out")

        with ThreadPoolExecutor(max_workers=1) as pool:
            manager_future = pool.submit(session.run, manager_socket, notify)
            try:
                worker_result = mock_worker.run_worker_session(
                    worker_socket,
                    await_start,
                    node_id="mock-pico-test",
                    udp_port=40001,
                )
                manager_result = manager_future.result(timeout=5)
            finally:
                manager_socket.close()
                worker_socket.close()

        self.assertEqual(worker_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["tiles_completed"], 2)
        self.assertEqual(manager_result["payload_bytes_received"], 32)
        self.assertEqual(manager_result["request_window"], 1)

    def test_small_job_over_tcp_and_udp_loopback(self):
        addresses = queue.Queue()

        def run_manager():
            return manager.run_tcp_server(
                SMALL_JOB,
                tile_size=4,
                host="127.0.0.1",
                port=0,
                timeout=5,
                job_id="loopback-small",
                ready_callback=addresses.put,
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            manager_future = pool.submit(run_manager)
            _host, port = addresses.get(timeout=2)
            worker_result = mock_worker.run_tcp_client(
                "127.0.0.1", port, 5, "mock-pico-loopback", 0
            )
            manager_result = manager_future.result(timeout=5)

        self.assertEqual(worker_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["checksum32"], "9bcd4fd2")
        self.assertLess(manager_result["e2e_ms"], 1000)

    def test_exhibition_job_over_tcp_and_udp_loopback(self):
        addresses = queue.Queue()

        def run_manager():
            return manager.run_tcp_server(
                EXHIBITION_JOB,
                tile_size=16,
                host="127.0.0.1",
                port=0,
                timeout=10,
                job_id="loopback-exhibition",
                ready_callback=addresses.put,
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            manager_future = pool.submit(run_manager)
            _host, port = addresses.get(timeout=2)
            worker_result = mock_worker.run_tcp_client(
                "127.0.0.1", port, 10, "mock-pico-exhibition", 0
            )
            manager_result = manager_future.result(timeout=10)

        self.assertEqual(worker_result["checksum32"], "1a26b685")
        self.assertEqual(manager_result["checksum32"], "1a26b685")
        self.assertEqual(manager_result["tiles_completed"], 320)
        self.assertEqual(manager_result["payload_bytes_received"], 81920)
        self.assertLess(manager_result["e2e_ms"], 5000)

    def test_two_workers_share_exhibition_job_after_ready_barrier(self):
        addresses = queue.Queue()

        def run_manager():
            return manager.run_tcp_server(
                EXHIBITION_JOB,
                tile_size=16,
                host="127.0.0.1",
                port=0,
                timeout=10,
                job_id="loopback-two-workers",
                ready_callback=addresses.put,
                worker_count=2,
            )

        with ThreadPoolExecutor(max_workers=3) as pool:
            manager_future = pool.submit(run_manager)
            _host, port = addresses.get(timeout=2)
            worker_futures = [
                pool.submit(
                    mock_worker.run_tcp_client,
                    "127.0.0.1",
                    port,
                    10,
                    "mock-pico-%d" % index,
                    0,
                )
                for index in (1, 2)
            ]
            worker_results = [future.result(timeout=10) for future in worker_futures]
            manager_result = manager_future.result(timeout=10)

        self.assertEqual(manager_result["checksum32"], "1a26b685")
        self.assertEqual(manager_result["worker_count_started"], 2)
        self.assertEqual(manager_result["worker_count_active_at_completion"], 2)
        self.assertEqual(manager_result["worker_timeouts"], [])
        self.assertEqual(
            sum(item["tiles_completed"] for item in manager_result["workers"]),
            320,
        )
        self.assertTrue(
            all(item["tiles_completed"] > 0 for item in manager_result["workers"])
        )
        self.assertEqual(sum(item["tiles_completed"] for item in worker_results), 320)

    def test_stalled_worker_times_out_while_other_worker_keeps_progressing(self):
        manager_stalled, worker_stalled = socket.socketpair()
        manager_survivor, worker_survivor = socket.socketpair()
        start_event = threading.Event()
        timeout_observed = threading.Event()
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=1,
            job_id="socketpair-worker-timeout",
            timeout=2,
            request_window=2,
            worker_timeout=0.15,
        )

        def hello(node_id):
            return {
                "type": "hello",
                "protocol_version": protocol.PROTOCOL_VERSION,
                "algorithm_version": protocol.ALGORITHM_VERSION,
                "output_version": protocol.OUTPUT_VERSION,
                "checksum_version": protocol.CHECKSUM_VERSION,
                "node_id": node_id,
                "udp_port": 40001,
            }

        def prepare(conn, node_id):
            protocol.send_frame(conn, hello(node_id))
            job_message, payload = protocol.recv_frame(conn)
            self.assertEqual(payload, b"")
            protocol.send_frame(
                conn, {"type": "ready", "job_id": job_message["job_id"]}
            )
            self.assertTrue(start_event.wait(1))
            return job_message

        def stalled_worker():
            job_message = prepare(worker_stalled, "mock-pico-stalled")
            assigned = []
            for _index in range(2):
                tile, payload = protocol.recv_frame(worker_stalled)
                self.assertEqual(payload, b"")
                assigned.append(tile)
            time.sleep(0.18)
            payload = mock_worker.compute_reference_tile(SMALL_JOB, assigned[0])
            try:
                protocol.send_frame(
                    worker_stalled,
                    result_message(job_message["job_id"], assigned[0], payload),
                    payload,
                )
            except OSError:
                pass
            finally:
                timeout_observed.set()

        def survivor_worker():
            job_message = prepare(worker_survivor, "mock-pico-survivor")
            duplicated = False
            completed = 0
            while True:
                message, payload = protocol.recv_frame(worker_survivor)
                if message.get("type") == "complete":
                    return {"completed": completed, "checksum32": message["checksum32"]}
                protocol.require_message_type(message, "tile")
                self.assertEqual(payload, b"")
                time.sleep(0.03)
                result = mock_worker.compute_reference_tile(SMALL_JOB, message)
                response = result_message(job_message["job_id"], message, result)
                protocol.send_frame(worker_survivor, response, result)
                completed += 1
                if timeout_observed.is_set() and not duplicated:
                    protocol.send_frame(worker_survivor, response, result)
                    duplicated = True

        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                manager_future = pool.submit(
                    session.run_workers,
                    [
                        (manager_stalled, lambda _hello, _job_id: start_event.set()),
                        (manager_survivor, lambda _hello, _job_id: start_event.set()),
                    ],
                )
                stalled_future = pool.submit(stalled_worker)
                survivor_future = pool.submit(survivor_worker)
                stalled_future.result(timeout=2)
                survivor_result = survivor_future.result(timeout=3)
                manager_result = manager_future.result(timeout=3)
        finally:
            for conn in (
                manager_stalled,
                worker_stalled,
                manager_survivor,
                worker_survivor,
            ):
                conn.close()

        self.assertEqual(survivor_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["requeued_tiles"], 2)
        self.assertEqual(manager_result["worker_count_active_at_completion"], 1)
        self.assertGreaterEqual(manager_result["ignored_tile_results"], 1)
        self.assertEqual(len(manager_result["worker_timeouts"]), 1)
        timeout_record = manager_result["worker_timeouts"][0]
        self.assertEqual(timeout_record["node_id"], "mock-pico-stalled")
        self.assertEqual(timeout_record["requeued_tiles"], 2)
        self.assertEqual(timeout_record["active_workers_remaining"], 1)

    def test_all_stalled_workers_fail_with_recovery_guidance(self):
        manager_one, worker_one = socket.socketpair()
        manager_two, worker_two = socket.socketpair()
        start_event = threading.Event()
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=2,
            job_id="socketpair-all-workers-timeout",
            timeout=1,
            request_window=2,
            worker_timeout=0.1,
        )

        def stall(conn, node_id):
            protocol.send_frame(
                conn,
                {
                    "type": "hello",
                    "protocol_version": protocol.PROTOCOL_VERSION,
                    "algorithm_version": protocol.ALGORITHM_VERSION,
                    "output_version": protocol.OUTPUT_VERSION,
                    "checksum_version": protocol.CHECKSUM_VERSION,
                    "node_id": node_id,
                    "udp_port": 40001,
                },
            )
            job_message, _payload = protocol.recv_frame(conn)
            protocol.send_frame(
                conn, {"type": "ready", "job_id": job_message["job_id"]}
            )
            self.assertTrue(start_event.wait(1))
            for _index in range(2):
                protocol.recv_frame(conn)
            time.sleep(0.2)

        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                manager_future = pool.submit(
                    session.run_workers,
                    [
                        (manager_one, lambda _hello, _job_id: start_event.set()),
                        (manager_two, lambda _hello, _job_id: start_event.set()),
                    ],
                )
                worker_futures = [
                    pool.submit(stall, worker_one, "mock-pico-stall-1"),
                    pool.submit(stall, worker_two, "mock-pico-stall-2"),
                ]
                with self.assertRaisesRegex(
                    protocol.ProtocolError,
                    "all workers unavailable.*restart workers.*new job_id",
                ):
                    manager_future.result(timeout=2)
                for future in worker_futures:
                    future.result(timeout=1)
        finally:
            for conn in (manager_one, worker_one, manager_two, worker_two):
                conn.close()

    def test_timeout_reassignment_supplies_worker_that_was_idle(self):
        manager_stalled, worker_stalled = socket.socketpair()
        manager_idle, worker_idle = socket.socketpair()
        start_event = threading.Event()
        session = manager.ManagerSession(
            SMALL_JOB,
            tile_size=4,
            job_id="socketpair-timeout-to-idle-worker",
            timeout=1,
            request_window=2,
            worker_timeout=0.1,
        )

        def stall_with_every_tile():
            protocol.send_frame(
                worker_stalled,
                {
                    "type": "hello",
                    "protocol_version": protocol.PROTOCOL_VERSION,
                    "algorithm_version": protocol.ALGORITHM_VERSION,
                    "output_version": protocol.OUTPUT_VERSION,
                    "checksum_version": protocol.CHECKSUM_VERSION,
                    "node_id": "mock-pico-holds-all",
                    "udp_port": 40001,
                },
            )
            job_message, _payload = protocol.recv_frame(worker_stalled)
            protocol.send_frame(
                worker_stalled,
                {"type": "ready", "job_id": job_message["job_id"]},
            )
            self.assertTrue(start_event.wait(1))
            for _index in range(2):
                protocol.recv_frame(worker_stalled)
            time.sleep(0.2)

        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                manager_future = pool.submit(
                    session.run_workers,
                    [
                        (manager_stalled, lambda _hello, _job_id: start_event.set()),
                        (manager_idle, lambda _hello, _job_id: start_event.set()),
                    ],
                )
                stalled_future = pool.submit(stall_with_every_tile)
                idle_future = pool.submit(
                    mock_worker.run_worker_session,
                    worker_idle,
                    lambda _job_id: start_event.wait(1),
                    "mock-pico-initially-idle",
                    40001,
                )
                idle_result = idle_future.result(timeout=2)
                manager_result = manager_future.result(timeout=2)
                stalled_future.result(timeout=1)
        finally:
            for conn in (
                manager_stalled,
                worker_stalled,
                manager_idle,
                worker_idle,
            ):
                conn.close()

        self.assertEqual(idle_result["checksum32"], "9bcd4fd2")
        self.assertEqual(idle_result["tiles_completed"], 2)
        self.assertEqual(manager_result["requeued_tiles"], 2)
        self.assertEqual(manager_result["worker_count_active_at_completion"], 1)

    def test_disconnected_worker_tiles_are_reassigned(self):
        addresses = queue.Queue()

        def run_manager():
            return manager.run_tcp_server(
                SMALL_JOB,
                tile_size=2,
                host="127.0.0.1",
                port=0,
                timeout=5,
                job_id="loopback-reassign",
                ready_callback=addresses.put,
                request_window=2,
                worker_count=2,
            )

        def disconnect_after_assignment(port):
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(("127.0.0.1", 0))
            udp.settimeout(5)
            conn = socket.create_connection(("127.0.0.1", port), timeout=5)
            conn.settimeout(5)
            try:
                protocol.send_frame(
                    conn,
                    {
                        "type": "hello",
                        "protocol_version": protocol.PROTOCOL_VERSION,
                        "algorithm_version": protocol.ALGORITHM_VERSION,
                        "output_version": protocol.OUTPUT_VERSION,
                        "checksum_version": protocol.CHECKSUM_VERSION,
                        "node_id": "mock-pico-drop",
                        "udp_port": udp.getsockname()[1],
                    },
                )
                job_message, _payload = protocol.recv_frame(conn)
                protocol.send_frame(
                    conn,
                    {"type": "ready", "job_id": job_message["job_id"]},
                )
                data, _address = udp.recvfrom(2048)
                protocol.parse_start_datagram(data, job_message["job_id"])
                tile, _payload = protocol.recv_frame(conn)
                protocol.require_message_type(tile, "tile")
            finally:
                conn.close()
                udp.close()

        with ThreadPoolExecutor(max_workers=3) as pool:
            manager_future = pool.submit(run_manager)
            _host, port = addresses.get(timeout=2)
            drop_future = pool.submit(disconnect_after_assignment, port)
            survivor_future = pool.submit(
                mock_worker.run_tcp_client,
                "127.0.0.1",
                port,
                5,
                "mock-pico-survivor",
                0,
            )
            drop_future.result(timeout=5)
            survivor_result = survivor_future.result(timeout=5)
            manager_result = manager_future.result(timeout=5)

        self.assertEqual(survivor_result["checksum32"], "9bcd4fd2")
        self.assertEqual(manager_result["checksum32"], "9bcd4fd2")
        self.assertGreaterEqual(manager_result["requeued_tiles"], 1)
        self.assertEqual(manager_result["worker_count_active_at_completion"], 1)
        dropped = [
            item for item in manager_result["workers"] if item["disconnected"]
        ]
        self.assertEqual(len(dropped), 1)


if __name__ == "__main__":
    unittest.main()
