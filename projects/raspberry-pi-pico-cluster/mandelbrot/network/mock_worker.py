#!/usr/bin/env python3
"""CPython worker used to test the multi-Pico protocol without hardware."""

from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import socket
import sys
import time

NETWORK_DIR = Path(__file__).resolve().parent
MANDELBROT_DIR = NETWORK_DIR.parent
HOST_DIR = MANDELBROT_DIR / "host"
for directory in (str(NETWORK_DIR), str(HOST_DIR)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import network_protocol as protocol  # noqa: E402
from mandelbrot_reference import (  # noqa: E402
    float32,
    reference_iteration_float32,
)


def compute_reference_tile(job, tile):
    xmin = float32(job["xmin"])
    ymin = float32(job["ymin"])
    dx = float32(float32(float32(job["xmax"]) - xmin) / job["width"])
    dy = float32(float32(float32(job["ymax"]) - ymin) / job["height"])
    half = float32(0.5)
    output = bytearray(tile["width"] * tile["height"])
    offset = 0
    for py in range(tile["y0"], tile["y0"] + tile["height"]):
        ci = float32(ymin + float32(float32(py + half) * dy))
        for px in range(tile["x0"], tile["x0"] + tile["width"]):
            cr = float32(xmin + float32(float32(px + half) * dx))
            output[offset] = reference_iteration_float32(cr, ci, job["max_iter"])
            offset += 1
    return output


def run_worker_session(
    conn,
    await_start,
    node_id="mock-pico-1",
    udp_port=40000,
    compute_tile=compute_reference_tile,
    stall_after_tiles=None,
    stall_seconds=0,
):
    if stall_after_tiles is not None:
        if type(stall_after_tiles) is not int or stall_after_tiles < 0:
            raise ValueError("stall_after_tiles must be a non-negative integer")
        if not isinstance(stall_seconds, (int, float)) or stall_seconds <= 0:
            raise ValueError("stall_seconds must be positive when injecting a stall")
    protocol.send_frame(
        conn,
        {
            "type": "hello",
            "protocol_version": protocol.PROTOCOL_VERSION,
            "algorithm_version": protocol.ALGORITHM_VERSION,
            "output_version": protocol.OUTPUT_VERSION,
            "checksum_version": protocol.CHECKSUM_VERSION,
            "node_id": node_id,
            "udp_port": udp_port,
            "implementation": "cpython-mock",
        },
    )
    job_message, payload = protocol.recv_frame(conn)
    protocol.require_message_type(job_message, "job")
    if payload:
        raise protocol.ProtocolError("job must not have a payload")
    if job_message.get("protocol_version") != protocol.PROTOCOL_VERSION:
        raise protocol.ProtocolError("job protocol_version mismatch")
    expected_versions = (
        ("algorithm_version", protocol.ALGORITHM_VERSION),
        ("output_version", protocol.OUTPUT_VERSION),
        ("checksum_version", protocol.CHECKSUM_VERSION),
    )
    for field, expected in expected_versions:
        if job_message.get(field) != expected:
            raise protocol.ProtocolError("job %s mismatch" % field)
    job_id = job_message["job_id"]
    job = job_message["job"]
    protocol.send_frame(conn, {"type": "ready", "job_id": job_id})
    await_start(job_id)

    completed = 0
    checksum = None
    stall_injected = False
    while True:
        tile, payload = protocol.recv_frame(conn)
        if tile.get("type") == "complete":
            if payload or tile.get("job_id") != job_id:
                raise protocol.ProtocolError("complete message is invalid")
            checksum = tile["checksum32"]
            break
        if tile.get("type") == "error":
            raise protocol.ProtocolError(tile.get("message", "manager error"))
        protocol.require_message_type(tile, "tile")
        if payload or tile.get("job_id") != job_id:
            raise protocol.ProtocolError("tile message is invalid")
        if not stall_injected and stall_after_tiles == completed:
            stall_injected = True
            time.sleep(stall_seconds)
        started = time.perf_counter()
        result = compute_tile(job, tile)
        compute_ms = round((time.perf_counter() - started) * 1000)
        protocol.send_frame(
            conn,
            {
                "type": "tile_result",
                "job_id": job_id,
                "tile_id": tile["tile_id"],
                "x0": tile["x0"],
                "y0": tile["y0"],
                "width": tile["width"],
                "height": tile["height"],
                "payload_crc32": "%08x" % (binascii.crc32(result) & 0xFFFFFFFF),
                "compute_ms": compute_ms,
                "mem_free_min_sampled": -1,
            },
            result,
        )
        completed += 1
    return {
        "job_id": job_id,
        "tiles_completed": completed,
        "checksum32": checksum,
    }


def run_tcp_client(
    host,
    port,
    timeout,
    node_id,
    udp_port,
    stall_after_tiles=None,
    stall_seconds=0,
):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("0.0.0.0", udp_port))
    actual_udp_port = udp.getsockname()[1]
    udp.settimeout(timeout)
    conn = socket.create_connection((host, port), timeout=timeout)
    conn.settimeout(timeout)
    if hasattr(socket, "TCP_NODELAY"):
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def await_start(job_id):
        data, _address = udp.recvfrom(2048)
        protocol.parse_start_datagram(data, job_id)

    try:
        return run_worker_session(
            conn,
            await_start,
            node_id,
            actual_udp_port,
            stall_after_tiles=stall_after_tiles,
            stall_seconds=stall_seconds,
        )
    finally:
        conn.close()
        udp.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--udp-port", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--node-id", default="mock-pico-1")
    parser.add_argument("--stall-after-tiles", type=int)
    parser.add_argument("--stall-seconds", type=float, default=0)
    args = parser.parse_args()
    result = run_tcp_client(
        args.host,
        args.port,
        args.timeout,
        args.node_id,
        args.udp_port,
        stall_after_tiles=args.stall_after_tiles,
        stall_seconds=args.stall_seconds,
    )
    print(json.dumps({"type": "mock_worker", "data": result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
