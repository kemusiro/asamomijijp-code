#!/usr/bin/env python3
"""Raspberry Pi manager for the multi-Pico Mandelbrot prototype."""

from __future__ import annotations

import argparse
import binascii
from collections import deque
import json
from pathlib import Path
import select
import socket
import sys
import time

NETWORK_DIR = Path(__file__).resolve().parent
MANDELBROT_DIR = NETWORK_DIR.parent
HOST_DIR = MANDELBROT_DIR / "host"
PICO_DIR = MANDELBROT_DIR / "pico"
for directory in (str(NETWORK_DIR), str(HOST_DIR), str(PICO_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import network_protocol as protocol  # noqa: E402
from progress_recording import (  # noqa: E402
    IMAGE_ENCODING,
    TILE_MIRRORING_REAL_AXIS,
    write_recording,
)
from mandelbrot_reference import (  # noqa: E402
    EXHIBITION_JOB,
    SMALL_JOB,
    checksum_image_rows,
    known_pixels,
)


EXPECTED_CHECKSUMS = {
    "small-v1": "9bcd4fd2",
    "exhibition-candidate-v1": "1a26b685",
}
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_WORKER_TIMEOUT_SECONDS = 5.0
MIN_WORKER_TIMEOUT_SECONDS = 0.1
MAX_WORKER_TIMEOUT_SECONDS = 300.0
DEFAULT_REQUEST_WINDOW = 4
MAX_REQUEST_WINDOW = 16
MAX_WORKERS = 64
START_DATAGRAM_REPETITIONS = 3


def build_upper_half_tiles(job, tile_size):
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")
    if job["ymin"] != -job["ymax"]:
        raise ValueError("real-axis symmetry requires ymin == -ymax")
    y_stop = (job["height"] + 1) // 2
    tiles = []
    tile_id = 0
    for y0 in range(0, y_stop, tile_size):
        tile_height = min(tile_size, y_stop - y0)
        for x0 in range(0, job["width"], tile_size):
            tile_width = min(tile_size, job["width"] - x0)
            tiles.append(
                {
                    "tile_id": tile_id,
                    "x0": x0,
                    "y0": y0,
                    "width": tile_width,
                    "height": tile_height,
                }
            )
            tile_id += 1
    return tiles


class ResultAssembler:
    def __init__(self, job, tiles, job_id):
        self.job = job
        self.job_id = job_id
        self.tiles = {tile["tile_id"]: tile for tile in tiles}
        self.completed = set()
        self.image = bytearray(job["width"] * job["height"])
        self.payload_bytes = 0
        self.compute_ms = 0
        self.min_free = None

    def accept(self, message, payload):
        protocol.require_message_type(message, "tile_result")
        if message.get("job_id") != self.job_id:
            raise protocol.ProtocolError("tile_result has a different job_id")
        tile_id = message.get("tile_id")
        if tile_id not in self.tiles:
            raise protocol.ProtocolError("tile_result has an unknown tile_id")
        if tile_id in self.completed:
            raise protocol.ProtocolError("duplicate tile_result")
        tile = self.tiles[tile_id]
        for field in ("x0", "y0", "width", "height"):
            if message.get(field) != tile[field]:
                raise protocol.ProtocolError("tile_result has mismatched " + field)
        expected_length = tile["width"] * tile["height"]
        if len(payload) != expected_length:
            raise protocol.ProtocolError("tile_result payload size mismatch")
        expected_crc = "%08x" % (binascii.crc32(payload) & 0xFFFFFFFF)
        if message.get("payload_crc32") != expected_crc:
            raise protocol.ProtocolError("tile_result payload CRC mismatch")

        width = self.job["width"]
        height = self.job["height"]
        for local_y in range(tile["height"]):
            source = local_y * tile["width"]
            row = tile["y0"] + local_y
            destination = row * width + tile["x0"]
            self.image[destination : destination + tile["width"]] = payload[
                source : source + tile["width"]
            ]
            mirror_row = height - 1 - row
            mirror_destination = mirror_row * width + tile["x0"]
            self.image[
                mirror_destination : mirror_destination + tile["width"]
            ] = payload[source : source + tile["width"]]

        self.completed.add(tile_id)
        self.payload_bytes += len(payload)
        compute_ms = message.get("compute_ms")
        if isinstance(compute_ms, int) and compute_ms >= 0:
            self.compute_ms += compute_ms
        mem_free = message.get("mem_free_min_sampled")
        if isinstance(mem_free, int) and mem_free >= 0:
            if self.min_free is None or mem_free < self.min_free:
                self.min_free = mem_free

    def finish(self):
        if len(self.completed) != len(self.tiles):
            raise protocol.ProtocolError("job has missing tile results")
        checksum = "%08x" % checksum_image_rows(self.image, self.job)
        expected = EXPECTED_CHECKSUMS.get(self.job["name"])
        pixels = known_pixels(self.image, self.job)
        expected_pixels = {
            "0,0": 1,
            "256,160": 64,
            "384,160": 64,
            "511,319": 2,
        }
        if self.job["name"] == "small-v1":
            expected_pixels = {"0,0": 1}
        checksum_matches = expected is None or checksum == expected
        pixels_match = pixels == expected_pixels
        if not checksum_matches:
            raise protocol.ProtocolError("completed image checksum mismatch")
        if not pixels_match:
            raise protocol.ProtocolError("known pixels mismatch")
        return {
            "checksum32": checksum,
            "expected_checksum32": expected,
            "checksum_matches": checksum_matches,
            "known_pixels": pixels,
            "known_pixels_match": pixels_match,
            "tiles_completed": len(self.completed),
            "payload_bytes_received": self.payload_bytes,
            "worker_compute_ms": self.compute_ms,
            "worker_mem_free_min_sampled": self.min_free,
        }


class MandelbrotWorkload:
    algorithm_version = protocol.ALGORITHM_VERSION
    output_version = protocol.OUTPUT_VERSION
    checksum_version = protocol.CHECKSUM_VERSION
    symmetry = "real-axis-upper-half"
    recording_image_encoding = IMAGE_ENCODING
    recording_tile_mirroring = TILE_MIRRORING_REAL_AXIS

    @staticmethod
    def build_tiles(job, tile_size):
        return build_upper_half_tiles(job, tile_size)

    @staticmethod
    def create_assembler(job, tiles, job_id):
        return ResultAssembler(job, tiles, job_id)


class ManagerSession:
    def __init__(
        self,
        job,
        tile_size=16,
        job_id="job-1",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        request_window=DEFAULT_REQUEST_WINDOW,
        worker_timeout=DEFAULT_WORKER_TIMEOUT_SECONDS,
        record_path=None,
        workload=None,
    ):
        if (
            type(request_window) is not int
            or not 1 <= request_window <= MAX_REQUEST_WINDOW
        ):
            raise ValueError(
                "request_window must be between 1 and %d" % MAX_REQUEST_WINDOW
            )
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("timeout must be a positive number")
        if timeout <= 0:
            raise ValueError("timeout must be a positive number")
        if (
            isinstance(worker_timeout, bool)
            or not isinstance(worker_timeout, (int, float))
            or not MIN_WORKER_TIMEOUT_SECONDS
            <= worker_timeout
            <= MAX_WORKER_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "worker_timeout must be between %.1f and %.1f seconds"
                % (MIN_WORKER_TIMEOUT_SECONDS, MAX_WORKER_TIMEOUT_SECONDS)
            )
        self.job = dict(job)
        self.tile_size = tile_size
        self.job_id = job_id
        self.timeout = timeout
        self.worker_timeout = worker_timeout
        self.request_window = request_window
        self.workload = workload or MandelbrotWorkload()
        self.tiles = self.workload.build_tiles(self.job, tile_size)
        self.record_path = Path(record_path) if record_path is not None else None

    def _send_tile(self, conn, tile):
        request = dict(tile)
        request.update({"type": "tile", "job_id": self.job_id})
        return protocol.send_frame(conn, request)

    def run(self, conn, start_notifier):
        return self.run_workers([(conn, start_notifier)])

    def _job_message(self):
        return {
            "type": "job",
            "protocol_version": protocol.PROTOCOL_VERSION,
            "algorithm_version": self.workload.algorithm_version,
            "output_version": self.workload.output_version,
            "checksum_version": self.workload.checksum_version,
            "job_id": self.job_id,
            "job": self.job,
            "tile_size": self.tile_size,
            "tile_count": len(self.tiles),
            "symmetry": self.workload.symmetry,
        }

    def _prepare_worker(self, conn, start_notifier):
        conn.settimeout(self.timeout)
        hello, payload = protocol.recv_frame(conn)
        if payload:
            raise protocol.ProtocolError("hello must not have a payload")
        protocol.validate_hello(
            hello,
            algorithm_version=self.workload.algorithm_version,
            output_version=self.workload.output_version,
            checksum_version=self.workload.checksum_version,
        )
        bytes_sent = protocol.send_frame(conn, self._job_message())
        ready, payload = protocol.recv_frame(conn)
        protocol.require_message_type(ready, "ready")
        if payload or ready.get("job_id") != self.job_id:
            raise protocol.ProtocolError("ready message is invalid")
        return {
            "conn": conn,
            "start_notifier": start_notifier,
            "hello": hello,
            "node_id": hello["node_id"],
            "outstanding": set(),
            "manager_bytes_sent": bytes_sent,
            "payload_bytes_received": 0,
            "worker_compute_ms": 0,
            "worker_mem_free_min_sampled": None,
            "tiles_completed": 0,
            "ignored_tile_results": 0,
            "disconnected": False,
            "disconnect_reason": None,
            "last_progress_at": None,
            "timed_out": False,
            "timeout_detected_ms": None,
            "requeued_tiles": 0,
        }

    @staticmethod
    def _worker_summary(worker):
        return {
            "node_id": worker["node_id"],
            "tiles_completed": worker["tiles_completed"],
            "payload_bytes_received": worker["payload_bytes_received"],
            "worker_compute_ms": worker["worker_compute_ms"],
            "worker_mem_free_min_sampled": worker[
                "worker_mem_free_min_sampled"
            ],
            "manager_bytes_sent": worker["manager_bytes_sent"],
            "ignored_tile_results": worker["ignored_tile_results"],
            "disconnected": worker["disconnected"],
            "disconnect_reason": worker["disconnect_reason"],
            "timed_out": worker["timed_out"],
            "timeout_detected_ms": worker["timeout_detected_ms"],
            "requeued_tiles": worker["requeued_tiles"],
        }

    def run_workers(self, worker_connections):
        if not worker_connections:
            raise ValueError("at least one worker connection is required")
        assembler = self.workload.create_assembler(
            self.job, self.tiles, self.job_id
        )
        workers = []
        active = {}
        pending = deque(self.tiles)
        ignored_tile_results = 0
        requeued_tiles = 0
        worker_timeouts = []
        progress_events = []
        started = None
        last_activity_at = None

        def fill_window(worker):
            while pending and len(worker["outstanding"]) < self.request_window:
                tile = pending.popleft()
                if not worker["outstanding"]:
                    worker["last_progress_at"] = time.monotonic()
                worker["outstanding"].add(tile["tile_id"])
                worker["manager_bytes_sent"] += self._send_tile(
                    worker["conn"], tile
                )

        def drop_worker(worker, reason, timed_out=False, detected_at=None):
            nonlocal requeued_tiles
            if worker["disconnected"]:
                return
            worker["disconnected"] = True
            worker["disconnect_reason"] = str(reason)
            active.pop(worker["conn"], None)
            tile_by_id = {tile["tile_id"]: tile for tile in self.tiles}
            returned = [tile_by_id[tile_id] for tile_id in worker["outstanding"]]
            for tile in sorted(returned, key=lambda item: item["tile_id"], reverse=True):
                pending.appendleft(tile)
            requeued_tiles += len(returned)
            worker["requeued_tiles"] += len(returned)
            worker["outstanding"].clear()
            if timed_out:
                detected_at = detected_at or time.monotonic()
                worker["timed_out"] = True
                worker["timeout_detected_ms"] = round(
                    (detected_at - started) * 1000, 3
                )
                idle_ms = round(
                    (detected_at - worker["last_progress_at"]) * 1000, 3
                )
                worker_timeouts.append(
                    {
                        "node_id": worker["node_id"],
                        "detected_after_ms": worker["timeout_detected_ms"],
                        "idle_ms": idle_ms,
                        "requeued_tiles": len(returned),
                        "active_workers_remaining": len(active),
                    }
                )
            try:
                worker["conn"].shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            worker["conn"].close()

        try:
            for conn, start_notifier in worker_connections:
                worker = self._prepare_worker(conn, start_notifier)
                if any(item["node_id"] == worker["node_id"] for item in workers):
                    raise protocol.ProtocolError("duplicate node_id")
                workers.append(worker)
                active[conn] = worker

            started = time.monotonic()
            last_activity_at = started
            for worker in workers:
                worker["conn"].settimeout(min(self.timeout, self.worker_timeout))
                worker["start_notifier"](worker["hello"], self.job_id)
            for worker in workers:
                fill_window(worker)

            while len(assembler.completed) < len(self.tiles):
                if not active:
                    raise protocol.ProtocolError(
                        "all workers unavailable; restart workers and retry "
                        "with a new job_id"
                    )
                now = time.monotonic()
                deadlines = [last_activity_at + self.timeout]
                deadlines.extend(
                    worker["last_progress_at"] + self.worker_timeout
                    for worker in active.values()
                    if worker["outstanding"]
                )
                wait_seconds = max(0.0, min(deadlines) - now)
                readable, _writable, _exceptional = select.select(
                    list(active), [], [], wait_seconds
                )
                now = time.monotonic()
                for worker in list(active.values()):
                    if (
                        worker["outstanding"]
                        and now - worker["last_progress_at"]
                        >= self.worker_timeout
                    ):
                        drop_worker(
                            worker,
                            "worker progress timed out after %.3f seconds"
                            % self.worker_timeout,
                            timed_out=True,
                            detected_at=now,
                        )
                for worker in list(active.values()):
                    try:
                        fill_window(worker)
                    except Exception as exc:
                        drop_worker(worker, exc)
                if not active:
                    continue
                if not readable:
                    if now - last_activity_at >= self.timeout:
                        raise TimeoutError(
                            "job activity timed out after %.3f seconds; "
                            "restart workers and retry with a new job_id"
                            % self.timeout
                        )
                    continue
                for conn in readable:
                    worker = active.get(conn)
                    if worker is None:
                        continue
                    try:
                        result, payload = protocol.recv_frame(conn)
                        last_activity_at = time.monotonic()
                        protocol.require_message_type(result, "tile_result")
                        tile_id = result.get("tile_id")
                        if result.get("job_id") != self.job_id:
                            worker["ignored_tile_results"] += 1
                            ignored_tile_results += 1
                            continue
                        if tile_id not in assembler.tiles:
                            raise protocol.ProtocolError(
                                "tile_result has an unknown tile_id"
                            )
                        if (
                            tile_id in assembler.completed
                            or tile_id not in worker["outstanding"]
                        ):
                            worker["ignored_tile_results"] += 1
                            ignored_tile_results += 1
                            continue
                        assembler.accept(result, payload)
                        if self.record_path is not None:
                            progress_events.append(
                                {
                                    "accepted_ms": round(
                                        (time.monotonic() - started) * 1000, 3
                                    ),
                                    "tile_id": tile_id,
                                    "node_id": worker["node_id"],
                                }
                            )
                    except Exception as exc:
                        drop_worker(worker, exc)
                        continue

                    worker["outstanding"].remove(tile_id)
                    worker["last_progress_at"] = time.monotonic()
                    worker["tiles_completed"] += 1
                    worker["payload_bytes_received"] += len(payload)
                    compute_ms = result.get("compute_ms")
                    if isinstance(compute_ms, int) and compute_ms >= 0:
                        worker["worker_compute_ms"] += compute_ms
                    mem_free = result.get("mem_free_min_sampled")
                    current_min = worker["worker_mem_free_min_sampled"]
                    if isinstance(mem_free, int) and mem_free >= 0:
                        if current_min is None or mem_free < current_min:
                            worker["worker_mem_free_min_sampled"] = mem_free
                    try:
                        fill_window(worker)
                    except Exception as exc:
                        drop_worker(worker, exc)

                for worker in list(active.values()):
                    try:
                        fill_window(worker)
                    except Exception as exc:
                        drop_worker(worker, exc)

            summary = assembler.finish()
            manager_bytes_sent = sum(
                worker["manager_bytes_sent"] for worker in workers
            )
            summary.update(
                {
                    "job": self.job["name"],
                    "job_id": self.job_id,
                    "node_id": workers[0]["node_id"],
                    "node_ids": [worker["node_id"] for worker in workers],
                    "worker_count_started": len(workers),
                    "worker_count_active_at_completion": len(active),
                    "workers": [self._worker_summary(worker) for worker in workers],
                    "tile_size": self.tile_size,
                    "request_window": self.request_window,
                    "worker_timeout_seconds": self.worker_timeout,
                    "worker_timeouts": worker_timeouts,
                    "e2e_ms": round((time.monotonic() - started) * 1000, 3),
                    "manager_bytes_sent": manager_bytes_sent,
                    "ignored_tile_results": ignored_tile_results,
                    "requeued_tiles": requeued_tiles,
                    "protocol_version": protocol.PROTOCOL_VERSION,
                }
            )
            for worker in list(active.values()):
                try:
                    worker["manager_bytes_sent"] += protocol.send_frame(
                        worker["conn"],
                        {
                            "type": "complete",
                            "job_id": self.job_id,
                            "checksum32": summary["checksum32"],
                        },
                    )
                except Exception as exc:
                    drop_worker(worker, exc)
            if self.record_path is not None:
                summary["recording_path"] = str(self.record_path)
                summary["recording_events"] = len(progress_events)
                write_recording(
                    self.record_path,
                    self.job,
                    self.tiles,
                    assembler.image,
                    progress_events,
                    summary,
                    image_encoding=self.workload.recording_image_encoding,
                    tile_mirroring=self.workload.recording_tile_mirroring,
                )
            return summary
        except Exception as exc:
            for worker in list(active.values()):
                try:
                    protocol.send_frame(
                        worker["conn"],
                        {
                            "type": "error",
                            "job_id": self.job_id,
                            "code": "manager_error",
                            "message": str(exc),
                        },
                    )
                except Exception:
                    pass
            raise


def udp_start_notifier(peer_ip):
    def notify(hello, job_id):
        udp_port = hello["udp_port"]
        datagram = protocol.make_start_datagram(job_id)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for _attempt in range(START_DATAGRAM_REPETITIONS):
                sock.sendto(datagram, (peer_ip, udp_port))
        finally:
            sock.close()

    return notify


def enable_tcp_nodelay(sock):
    if hasattr(socket, "TCP_NODELAY"):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


def run_tcp_server(
    job,
    tile_size,
    host,
    port,
    timeout,
    job_id,
    ready_callback=None,
    request_window=DEFAULT_REQUEST_WINDOW,
    worker_count=1,
    worker_timeout=DEFAULT_WORKER_TIMEOUT_SECONDS,
    record_path=None,
    workload=None,
):
    if type(worker_count) is not int or not 1 <= worker_count <= MAX_WORKERS:
        raise ValueError("worker_count must be between 1 and %d" % MAX_WORKERS)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(worker_count)
    server.settimeout(timeout)
    if ready_callback is not None:
        ready_callback(server.getsockname())
    connections = []
    try:
        for _index in range(worker_count):
            conn, address = server.accept()
            enable_tcp_nodelay(conn)
            connections.append((conn, udp_start_notifier(address[0])))
        session = ManagerSession(
            job,
            tile_size,
            job_id,
            timeout,
            worker_timeout=worker_timeout,
            request_window=request_window,
            record_path=record_path,
            workload=workload,
        )
        return session.run_workers(connections)
    finally:
        for conn, _notifier in connections:
            conn.close()
        server.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--worker-timeout",
        type=float,
        default=DEFAULT_WORKER_TIMEOUT_SECONDS,
        help="seconds without accepted tile progress before dropping one worker",
    )
    parser.add_argument("--job", choices=("small", "exhibition"), default="small")
    parser.add_argument("--tile-size", type=int, default=16)
    parser.add_argument("--request-window", type=int, default=DEFAULT_REQUEST_WINDOW)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--job-id", default="manual-job-1")
    parser.add_argument(
        "--record-trace",
        help="write accepted-tile times and the completed image to this JSON file",
    )
    args = parser.parse_args()
    job = SMALL_JOB if args.job == "small" else EXHIBITION_JOB
    summary = run_tcp_server(
        job,
        args.tile_size,
        args.host,
        args.port,
        args.timeout,
        args.job_id,
        request_window=args.request_window,
        worker_count=args.workers,
        worker_timeout=args.worker_timeout,
        record_path=args.record_trace,
    )
    print(json.dumps({"type": "summary", "data": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
