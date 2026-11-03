"""Regression tests for stalled and trickling result frames (Issue #38)."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manager
import mock_worker
import network_protocol as protocol
from mandelbrot_reference import SMALL_JOB
from test_network import result_message


class SlowSendSocket:
    """Inject partial writes and EWOULDBLOCK only during nonblocking I/O."""

    def __init__(self, conn):
        self.conn = conn
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def send(self, data):
        if self.conn.gettimeout() == 0:
            self.calls += 1
            if self.calls % 3 == 1:
                raise BlockingIOError()
            data = data[:7]
        return self.conn.send(data)


class FrameReaderTests(unittest.TestCase):
    def test_fragmented_and_consecutive_frames(self):
        left, right = socket.socketpair()
        right.setblocking(False)
        reader = manager.FrameReader()
        frames = [({"type": "first"}, bytes(range(256))), ({"type": "last"}, b"")]
        received = []
        try:
            self.assertIsNone(reader.receive(right))
            for message, payload in frames:
                for byte in protocol.encode_frame(message, payload):
                    left.sendall(bytes([byte]))
                    result = reader.receive(right)
                    if result is not None:
                        received.append(result)
            self.assertEqual([bytes(item[1]) for item in received], [x[1] for x in frames])
            self.assertEqual([item[0]["type"] for item in received], ["first", "last"])
            self.assertIsNone(reader.receive(right))
        finally:
            left.close()
            right.close()

    def test_invalid_sizes_and_headers_are_rejected_before_payload_read(self):
        invalid_frames = [b"\0\0\0\0", (protocol.MAX_HEADER_BYTES + 1).to_bytes(4, "big")]
        headers = [b"{", b"[]", b"\xff"] + [
            json.dumps({"payload_length": size}).encode()
            for size in (-1, True, "1", protocol.MAX_PAYLOAD_BYTES + 1)
        ]
        invalid_frames.extend(len(header).to_bytes(4, "big") + header for header in headers)
        for frame in invalid_frames:
            with self.subTest(frame=frame):
                left, right = socket.socketpair()
                right.setblocking(False)
                try:
                    left.sendall(frame)
                    reader = manager.FrameReader()
                    with self.assertRaises(protocol.ProtocolError):
                        reader.receive(right)
                        reader.receive(right)
                finally:
                    left.close()
                    right.close()


class UnresponsiveWorkerTests(unittest.TestCase):
    def test_nonfinite_global_timeout_is_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                manager.ManagerSession(SMALL_JOB, timeout=value)

    def exercise(self, mode, all_stalled=False, global_timeout=2, slow_send=False):
        pairs = [socket.socketpair(), socket.socketpair()]
        for pair in pairs:
            pair[1].settimeout(3)
        started = threading.Event()
        stop = threading.Event()
        survivor_progress = threading.Event()
        timeout = 0.3
        session = manager.ManagerSession(
            SMALL_JOB, tile_size=2, job_id="partial-frame-test",
            timeout=global_timeout, worker_timeout=timeout, request_window=2,
        )

        def prepare(conn, node):
            protocol.send_frame(conn, {
                "type": "hello", "node_id": node, "udp_port": 40001,
                "protocol_version": protocol.PROTOCOL_VERSION,
                "algorithm_version": protocol.ALGORITHM_VERSION,
                "output_version": protocol.OUTPUT_VERSION,
                "checksum_version": protocol.CHECKSUM_VERSION,
            })
            job, _ = protocol.recv_frame(conn)
            protocol.send_frame(conn, {"type": "ready", "job_id": job["job_id"]})
            self.assertTrue(started.wait(2))
            return job["job_id"]

        def stall(conn, node):
            job_id = prepare(conn, node)
            tile, _ = protocol.recv_frame(conn)
            protocol.recv_frame(conn)  # Drain the initial request window.
            payload = mock_worker.compute_reference_tile(SMALL_JOB, tile)
            message = result_message(job_id, tile, payload)
            frame = protocol.encode_frame(message, payload)
            if mode == "duplicate":
                protocol.send_frame(conn, message, payload)
                protocol.recv_frame(conn)  # Its valid result replenishes the window.
            elif mode == "old-job":
                message["job_id"] = "old-job"
                frame = protocol.encode_frame(message, payload)
            elif mode == "prefix":
                conn.sendall(frame[:1])
            elif mode == "header":
                conn.sendall(frame[:6])
            elif mode == "payload":
                conn.sendall(frame[:-1])

            offset = 0
            while not stop.is_set():
                try:
                    if mode in ("old-job", "duplicate"):
                        conn.sendall(frame)
                    elif mode == "trickle":
                        conn.sendall(frame[offset:offset + 1])
                        offset += 1
                    # Check for manager-initiated closure without closing ourselves.
                    conn.settimeout(0.02)
                    try:
                        data = conn.recv(4096)
                        if not data:
                            return
                    except socket.timeout:
                        pass
                    stop.wait(0.01)
                except OSError:
                    return

        def survivor(conn):
            job_id = prepare(conn, "healthy")
            completed = 0
            while True:
                tile, _ = protocol.recv_frame(conn)
                if tile["type"] == "complete":
                    return tile["checksum32"]
                protocol.require_message_type(tile, "tile")
                # A third request proves that manager accepted a result, even while
                # the stalled peer's partial frame remains incomplete.
                if completed >= 2:
                    survivor_progress.set()
                payload = mock_worker.compute_reference_tile(SMALL_JOB, tile)
                stop.wait(0.02)
                protocol.send_frame(conn, result_message(job_id, tile, payload), payload)
                completed += 1

        with ThreadPoolExecutor(max_workers=3) as pool:
            future = pool.submit(session.run_workers, [
                (SlowSendSocket(pair[0]) if slow_send else pair[0],
                 lambda _hello, _job_id: started.set()) for pair in pairs
            ])
            bad = pool.submit(stall, pairs[0][1], "stalled")
            other = (
                pool.submit(stall, pairs[1][1], "also-stalled") if all_stalled
                else pool.submit(survivor, pairs[1][1])
            )
            try:
                if all_stalled:
                    error = TimeoutError if global_timeout < timeout else protocol.ProtocolError
                    with self.assertRaisesRegex(error, "restart workers.*new job_id"):
                        future.result(timeout=1.5)
                else:
                    self.assertTrue(survivor_progress.wait(timeout * 0.8))
                    summary = future.result(timeout=1.5)
                    self.assertEqual(other.result(timeout=1), "9bcd4fd2")
                    self.assertEqual(summary["checksum32"], "9bcd4fd2")
                    self.assertEqual(summary["tiles_completed"], 8)
                    self.assertEqual(summary["requeued_tiles"], 2)
                    self.assertEqual(summary["worker_count_active_at_completion"], 1)
                    self.assertEqual(len(summary["worker_timeouts"]), 1)
                    event = summary["worker_timeouts"][0]
                    self.assertEqual(event["node_id"], "stalled")
                    self.assertGreaterEqual(event["idle_ms"], timeout * 1000)
                    self.assertLess(event["idle_ms"], timeout * 2000)
                    if mode in ("duplicate", "old-job"):
                        self.assertGreater(summary["ignored_tile_results"], 0)
            finally:
                stop.set()
                for pair in pairs:
                    for conn in pair:
                        conn.close()
            bad.result(timeout=1)
            if all_stalled:
                other.result(timeout=1)

    def test_partial_frames_do_not_block_healthy_worker(self):
        for mode in ("prefix", "header", "payload", "trickle"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_ignored_results_do_not_extend_worker_deadline(self):
        for mode in ("old-job", "duplicate"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_partial_writes_and_send_backpressure_preserve_frames(self):
        self.exercise("prefix", slow_send=True)

    def test_all_trickling_workers_fail_in_bounded_time(self):
        self.exercise("trickle", all_stalled=True)

    def test_old_job_traffic_does_not_extend_global_deadline(self):
        self.exercise("old-job", all_stalled=True, global_timeout=0.15)


if __name__ == "__main__":
    unittest.main()
