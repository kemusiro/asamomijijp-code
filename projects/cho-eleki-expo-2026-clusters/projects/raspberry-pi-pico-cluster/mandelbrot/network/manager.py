#!/usr/bin/env python3
"""Raspberry Pi manager for the multi-Pico Mandelbrot prototype."""

from __future__ import annotations

import argparse
import binascii
from collections import deque
import json
import math
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
    RECOVERY_JOB,
    SMALL_JOB,
    checksum_image_rows,
    known_pixels,
)


EXPECTED_CHECKSUMS = {
    "small-v1": "9bcd4fd2",
    "exhibition-candidate-v1": "1a26b685",
    "recovery-probe-v1": "e590a9e7",
}
EXPECTED_KNOWN_PIXELS = {
    "small-v1": {"0,0": 1},
    "exhibition-candidate-v1": {
        "0,0": 1,
        "256,160": 64,
        "384,160": 64,
        "511,319": 2,
    },
    "recovery-probe-v1": {"0,0": 1},
}
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_STARTUP_HANDSHAKE_TIMEOUT_SECONDS = 5.0
DEFAULT_WORKER_TIMEOUT_SECONDS = 5.0
MIN_WORKER_TIMEOUT_SECONDS = 0.1
MAX_WORKER_TIMEOUT_SECONDS = 300.0
DEFAULT_REQUEST_WINDOW = 4
MAX_REQUEST_WINDOW = 16
MAX_WORKERS = 64
START_DATAGRAM_REPETITIONS = 3
START_DATAGRAM_INTERVAL_SECONDS = 0.05


class AllWorkersUnavailable(protocol.ProtocolError):
    """Report every worker's final state without relying on traceback locals."""

    def __init__(self, worker_failures):
        self.worker_failures = worker_failures
        details = json.dumps(
            worker_failures,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        super().__init__(
            "all workers unavailable; worker_failures=%s; "
            "restart workers and retry with a new job_id" % details
        )


class WorkerStartupError(protocol.ProtocolError):
    """Identify the worker and stage that failed before the ready barrier."""

    def __init__(self, stage, node_id, reason):
        self.stage = stage
        self.node_id = node_id
        self.reason = reason
        label = node_id or "unidentified worker"
        super().__init__(
            "%s failed during %s: %s" % (label, stage, reason)
        )

    def as_record(self):
        return {
            "stage": self.stage,
            "node_id": self.node_id,
            "reason": str(self.reason),
            "reason_type": type(self.reason).__name__,
        }


class FrameReader:
    """Read at most one available chunk; never wait for the rest of a frame."""

    def __init__(self):
        self.buffer = bytearray()
        self.target = 4
        self.header_length = None
        self.message = None
        self.bytes_received = 0

    def receive(self, conn):
        try:
            chunk = conn.recv(self.target - len(self.buffer))
        except BlockingIOError:
            return None
        if not chunk:
            raise protocol.ProtocolError("socket closed while receiving")
        self.buffer.extend(chunk)
        self.bytes_received += len(chunk)
        if len(self.buffer) < self.target:
            return None
        if self.header_length is None:
            self.header_length = int.from_bytes(self.buffer, "big")
            if not 1 <= self.header_length <= protocol.MAX_HEADER_BYTES:
                raise protocol.ProtocolError("header size is invalid")
            self.buffer.clear()
            self.target = self.header_length
            return None
        if self.message is None:
            try:
                self.message = json.loads(self.buffer.decode("utf-8"))
            except (ValueError, UnicodeError):
                raise protocol.ProtocolError("header is not valid JSON")
            if not isinstance(self.message, dict):
                raise protocol.ProtocolError("header JSON must be an object")
            length = self.message.get("payload_length")
            if type(length) is not int or not 0 <= length <= protocol.MAX_PAYLOAD_BYTES:
                raise protocol.ProtocolError("payload_length is invalid")
            self.buffer.clear()
            self.target = length
            if length:
                return None
        result = self.message, self.buffer
        self.__init__()
        return result


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
        expected_pixels = EXPECTED_KNOWN_PIXELS.get(self.job["name"])
        checksum_matches = expected is None or checksum == expected
        pixels_match = expected_pixels is None or pixels == expected_pixels
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
        progress_callback=None,
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
        if not math.isfinite(timeout) or timeout <= 0:
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
        if progress_callback is not None and not callable(progress_callback):
            raise ValueError("progress_callback must be callable")
        self.progress_callback = progress_callback

    def emit_progress(self, event, assembler=None):
        if self.progress_callback is not None:
            try:
                self.progress_callback(dict(event), assembler)
            except Exception as exc:
                print(
                    "progress callback disabled after error: %s" % exc,
                    file=sys.stderr,
                    flush=True,
                )
                self.progress_callback = None

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

    def _prepare_worker(
        self,
        conn,
        start_notifier,
        session_started_at,
        handshake_timeout=None,
    ):
        node_id = None
        stage = "hello"
        conn.settimeout(handshake_timeout or self.timeout)
        try:
            hello, payload = protocol.recv_frame(conn)
            if payload:
                raise protocol.ProtocolError("hello must not have a payload")
            protocol.validate_hello(
                hello,
                algorithm_version=self.workload.algorithm_version,
                output_version=self.workload.output_version,
                checksum_version=self.workload.checksum_version,
            )
            node_id = hello["node_id"]
            stage = "job_send"
            bytes_sent = protocol.send_frame(conn, self._job_message())
            stage = "ready"
            ready, payload = protocol.recv_frame(conn)
            protocol.require_message_type(ready, "ready")
            if payload or ready.get("job_id") != self.job_id:
                raise protocol.ProtocolError("ready message is invalid")
        except Exception as exc:
            if isinstance(exc, WorkerStartupError):
                raise
            raise WorkerStartupError(stage, node_id, exc) from exc
        now = time.monotonic()
        return {
            "conn": conn,
            "start_notifier": start_notifier,
            "hello": hello,
            "node_id": hello["node_id"],
            "outstanding": set(),
            "reader": FrameReader(),
            "send_buffer": bytearray(),
            "manager_bytes_sent": bytes_sent,
            "payload_bytes_received": 0,
            "worker_compute_ms": 0,
            "worker_mem_free_min_sampled": None,
            "tiles_completed": 0,
            "ignored_tile_results": 0,
            "disconnected": False,
            "disconnect_reason": None,
            "failure": None,
            "phase": "prepared",
            "session_started_at": session_started_at,
            "prepared_at": now,
            "start_notified_at": None,
            "first_tile_queued_at": None,
            "first_tile_frame_bytes": None,
            "request_bytes_sent": 0,
            "first_request_byte_sent_at": None,
            "first_request_fully_sent_at": None,
            "first_result_byte_received_at": None,
            "first_result_accepted_at": None,
            "last_progress_at": None,
            "timed_out": False,
            "timeout_detected_ms": None,
            "requeued_tiles": 0,
        }

    @staticmethod
    def _elapsed_ms(worker, timestamp):
        if timestamp is None:
            return None
        return round((timestamp - worker["session_started_at"]) * 1000, 3)

    @classmethod
    def _worker_diagnostics(cls, worker):
        reader = worker["reader"]
        return {
            "phase": worker["phase"],
            "prepared_ms": cls._elapsed_ms(worker, worker["prepared_at"]),
            "start_notified_ms": cls._elapsed_ms(
                worker, worker["start_notified_at"]
            ),
            "first_tile_queued_ms": cls._elapsed_ms(
                worker, worker["first_tile_queued_at"]
            ),
            "first_request_byte_sent_ms": cls._elapsed_ms(
                worker, worker["first_request_byte_sent_at"]
            ),
            "first_request_fully_sent_ms": cls._elapsed_ms(
                worker, worker["first_request_fully_sent_at"]
            ),
            "first_result_byte_received_ms": cls._elapsed_ms(
                worker, worker["first_result_byte_received_at"]
            ),
            "first_result_accepted_ms": cls._elapsed_ms(
                worker, worker["first_result_accepted_at"]
            ),
            "request_bytes_sent": worker["request_bytes_sent"],
            "tiles_completed": worker["tiles_completed"],
            "send_buffer_bytes": len(worker["send_buffer"]),
            "outstanding_tile_ids": sorted(worker["outstanding"]),
            "reader_bytes_received": reader.bytes_received,
            "reader_buffered_bytes": len(reader.buffer),
            "reader_target_bytes": reader.target,
            "reader_header_length": reader.header_length,
        }

    @staticmethod
    def _worker_summary(worker):
        return {
            "node_id": worker["node_id"],
            "reset_cause": worker["hello"].get("reset_cause"),
            "reset_cause_name": worker["hello"].get("reset_cause_name"),
            "watchdog_enabled": worker["hello"].get("watchdog_enabled", False),
            "watchdog_timeout_ms": worker["hello"].get("watchdog_timeout_ms"),
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
            "failure": worker["failure"],
        }

    def run_workers(
        self,
        worker_connections,
        prepared_workers=None,
        startup_failures=None,
        session_started_at=None,
    ):
        prepared_workers = list(prepared_workers or ())
        startup_failures = list(startup_failures or ())
        if not worker_connections and not prepared_workers:
            raise ValueError("at least one worker connection is required")
        assembler = self.workload.create_assembler(
            self.job, self.tiles, self.job_id
        )
        workers = prepared_workers
        active = {worker["conn"]: worker for worker in workers}
        pending = deque(self.tiles)
        ignored_tile_results = 0
        requeued_tiles = 0
        worker_timeouts = []
        progress_events = []
        session_started_at = session_started_at or time.monotonic()
        started = None
        last_activity_at = None

        def fill_window(worker):
            while pending and len(worker["outstanding"]) < self.request_window:
                tile = pending.popleft()
                if not worker["outstanding"]:
                    worker["last_progress_at"] = time.monotonic()
                worker["outstanding"].add(tile["tile_id"])
                request = dict(tile)
                request.update({"type": "tile", "job_id": self.job_id})
                frame = protocol.encode_frame(request)
                if worker["first_tile_queued_at"] is None:
                    worker["first_tile_queued_at"] = time.monotonic()
                    worker["first_tile_frame_bytes"] = len(frame)
                    worker["phase"] = "initial_requests_queued"
                worker["send_buffer"].extend(frame)

        def drop_worker(worker, reason, timed_out=False, detected_at=None):
            nonlocal requeued_tiles
            if worker["disconnected"]:
                return
            if timed_out:
                detected_at = detected_at or time.monotonic()
            worker["disconnected"] = True
            worker["disconnect_reason"] = str(reason)
            failure = self._worker_diagnostics(worker)
            failure.update(
                {
                    "node_id": worker["node_id"],
                    "reason": str(reason),
                    "reason_type": type(reason).__name__,
                    "timed_out": timed_out,
                    "detected_after_ms": (
                        round((detected_at - started) * 1000, 3)
                        if timed_out
                        else None
                    ),
                    "idle_ms": (
                        round(
                            (detected_at - worker["last_progress_at"]) * 1000,
                            3,
                        )
                        if timed_out
                        else None
                    ),
                    "requeued_tiles": len(worker["outstanding"]),
                }
            )
            worker["failure"] = failure
            worker["phase"] = "dropped"
            active.pop(worker["conn"], None)
            tile_by_id = {tile["tile_id"]: tile for tile in self.tiles}
            returned = [tile_by_id[tile_id] for tile_id in worker["outstanding"]]
            for tile in sorted(returned, key=lambda item: item["tile_id"], reverse=True):
                pending.appendleft(tile)
            requeued_tiles += len(returned)
            worker["requeued_tiles"] += len(returned)
            worker["outstanding"].clear()
            worker["send_buffer"].clear()
            if timed_out:
                worker["timed_out"] = True
                worker["timeout_detected_ms"] = round(
                    (detected_at - started) * 1000, 3
                )
                worker_timeouts.append(
                    {
                        "node_id": worker["node_id"],
                        "detected_after_ms": worker["timeout_detected_ms"],
                        "idle_ms": failure["idle_ms"],
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
                worker = self._prepare_worker(
                    conn, start_notifier, session_started_at
                )
                if any(item["node_id"] == worker["node_id"] for item in workers):
                    raise protocol.ProtocolError("duplicate node_id")
                workers.append(worker)
                active[conn] = worker

            started = time.monotonic()
            last_activity_at = started
            udp_workers = []
            for worker in workers:
                if worker["hello"].get("start_transport") == "tcp":
                    protocol.send_frame(
                        worker["conn"],
                        {
                            "type": "start",
                            "protocol_version": protocol.PROTOCOL_VERSION,
                            "job_id": self.job_id,
                        },
                    )
                    worker["start_notified_at"] = time.monotonic()
                    worker["phase"] = "start_notified"
                else:
                    udp_workers.append(worker)
            for attempt in range(START_DATAGRAM_REPETITIONS):
                for worker in udp_workers:
                    worker["start_notifier"](worker["hello"], self.job_id)
                    if worker["start_notified_at"] is None:
                        worker["start_notified_at"] = time.monotonic()
                        worker["phase"] = "start_notified"
                if udp_workers and attempt + 1 < START_DATAGRAM_REPETITIONS:
                    time.sleep(START_DATAGRAM_INTERVAL_SECONDS)
            for worker in workers:
                worker["conn"].setblocking(False)
            for worker in workers:
                fill_window(worker)
            self.emit_progress(
                {
                    "type": "job_started",
                    "job_id": self.job_id,
                    "node_ids": [worker["node_id"] for worker in workers],
                    "total_tiles": len(self.tiles),
                },
                assembler,
            )

            while len(assembler.completed) < len(self.tiles):
                if not active:
                    raise AllWorkersUnavailable(
                        [worker["failure"] for worker in workers]
                    )
                now = time.monotonic()
                deadlines = [last_activity_at + self.timeout]
                deadlines.extend(
                    worker["last_progress_at"] + self.worker_timeout
                    for worker in active.values()
                    if worker["outstanding"]
                )
                wait_seconds = max(0.0, min(deadlines) - now)
                readable, writable, _exceptional = select.select(
                    list(active),
                    [conn for conn, worker in active.items() if worker["send_buffer"]],
                    [],
                    wait_seconds,
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
                            TimeoutError(
                                "worker progress timed out after %.3f seconds"
                                % self.worker_timeout
                            ),
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
                if now - last_activity_at >= self.timeout:
                    raise TimeoutError(
                        "job progress timed out after %.3f seconds; "
                        "restart workers and retry with a new job_id"
                        % self.timeout
                    )
                for conn in writable:
                    worker = active.get(conn)
                    if worker is None:
                        continue
                    try:
                        sent = conn.send(worker["send_buffer"])
                        if sent <= 0:
                            raise protocol.ProtocolError("socket closed while sending")
                        del worker["send_buffer"][:sent]
                        worker["manager_bytes_sent"] += sent
                        worker["request_bytes_sent"] += sent
                        sent_at = time.monotonic()
                        if worker["first_request_byte_sent_at"] is None:
                            worker["first_request_byte_sent_at"] = sent_at
                        if (
                            worker["first_request_fully_sent_at"] is None
                            and worker["request_bytes_sent"]
                            >= worker["first_tile_frame_bytes"]
                        ):
                            worker["first_request_fully_sent_at"] = sent_at
                            worker["phase"] = "waiting_first_result"
                    except BlockingIOError:
                        pass
                    except Exception as exc:
                        drop_worker(worker, exc)
                for conn in readable:
                    worker = active.get(conn)
                    if worker is None:
                        continue
                    try:
                        reader_bytes_before = worker["reader"].bytes_received
                        frame = worker["reader"].receive(conn)
                        if (
                            worker["first_result_byte_received_at"] is None
                            and worker["reader"].bytes_received > reader_bytes_before
                        ):
                            worker["first_result_byte_received_at"] = time.monotonic()
                            worker["phase"] = "receiving_first_result"
                        if frame is None:
                            continue
                        result, payload = frame
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
                        last_activity_at = time.monotonic()
                        if worker["first_result_accepted_at"] is None:
                            worker["first_result_accepted_at"] = last_activity_at
                        worker["phase"] = "receiving_results"
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
                    self.emit_progress(
                        {
                            "type": "tile_accepted",
                            "job_id": self.job_id,
                            "node_id": worker["node_id"],
                            "tile": dict(assembler.tiles[tile_id]),
                            "completed_tiles": len(assembler.completed),
                            "total_tiles": len(self.tiles),
                            "worker_tiles": {
                                item["node_id"]: item["tiles_completed"]
                                for item in workers
                            },
                        },
                        assembler,
                    )
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
                    "startup_ready_ms": round(
                        (started - session_started_at) * 1000, 3
                    ),
                    "startup_failure_count": len(startup_failures),
                    "startup_failures": startup_failures,
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
                    # Computation is over; send the final notification with the
                    # existing bounded blocking policy, including partial writes.
                    worker["conn"].settimeout(min(self.timeout, self.worker_timeout))
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
                    # A partially sent tile cannot be followed by an error frame.
                    if worker["send_buffer"]:
                        continue
                    worker["conn"].settimeout(min(self.timeout, self.worker_timeout))
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
    minimum_worker_count=None,
    progress_callback=None,
):
    if type(worker_count) is not int or not 1 <= worker_count <= MAX_WORKERS:
        raise ValueError("worker_count must be between 1 and %d" % MAX_WORKERS)
    if minimum_worker_count is None:
        minimum_worker_count = worker_count
    if (
        type(minimum_worker_count) is not int
        or not 1 <= minimum_worker_count <= worker_count
    ):
        raise ValueError("minimum_worker_count must be between 1 and worker_count")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(worker_count)
    server.settimeout(timeout)
    if ready_callback is not None:
        ready_callback(server.getsockname())
    connections = []
    prepared_workers = []
    startup_failures = []
    try:
        session = ManagerSession(
            job,
            tile_size,
            job_id,
            timeout,
            worker_timeout=worker_timeout,
            request_window=request_window,
            record_path=record_path,
            workload=workload,
            progress_callback=progress_callback,
        )
        session_started_at = time.monotonic()
        startup_deadline = session_started_at + timeout
        node_ids = set()

        def startup_timeout_error():
            ready_node_ids = sorted(
                worker["node_id"] for worker in prepared_workers
            )
            return TimeoutError(
                "worker startup timed out after %.3f seconds; "
                "ready=%d/%d; ready_node_ids=%s; startup_failures=%s"
                % (
                    timeout,
                    len(prepared_workers),
                    worker_count,
                    json.dumps(ready_node_ids),
                    json.dumps(startup_failures, sort_keys=True),
                )
            )

        while len(prepared_workers) < worker_count:
            remaining = startup_deadline - time.monotonic()
            if remaining <= 0:
                if len(prepared_workers) >= minimum_worker_count:
                    break
                raise startup_timeout_error()
            server.settimeout(remaining)
            try:
                conn, address = server.accept()
            except socket.timeout as exc:
                if len(prepared_workers) >= minimum_worker_count:
                    break
                raise startup_timeout_error() from exc
            enable_tcp_nodelay(conn)
            notifier = udp_start_notifier(address[0])
            connections.append((conn, notifier))
            try:
                worker = session._prepare_worker(
                    conn,
                    notifier,
                    session_started_at,
                    handshake_timeout=min(
                        DEFAULT_STARTUP_HANDSHAKE_TIMEOUT_SECONDS,
                        remaining,
                    ),
                )
                if worker["node_id"] in node_ids:
                    raise WorkerStartupError(
                        "duplicate_node_id",
                        worker["node_id"],
                        protocol.ProtocolError("duplicate node_id"),
                    )
            except WorkerStartupError as exc:
                record = exc.as_record()
                startup_failures.append(record)
                conn.close()
                continue
            node_ids.add(worker["node_id"])
            prepared_workers.append(worker)
            session.emit_progress(
                {
                    "type": "worker_ready",
                    "job_id": job_id,
                    "node_id": worker["node_id"],
                    "ready_count": len(prepared_workers),
                    "expected_workers": worker_count,
                }
            )
        return session.run_workers(
            [],
            prepared_workers=prepared_workers,
            startup_failures=startup_failures,
            session_started_at=session_started_at,
        )
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
