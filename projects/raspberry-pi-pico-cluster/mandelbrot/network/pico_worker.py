"""MicroPython worker for multi-Pico Mandelbrot network verification.

Copy this file as pico_worker.py together with network_protocol.py,
mandelbrot_core.py, and a local network_config.py.  Importing the module does
not connect to Wi-Fi; call run_once() or run_forever() explicitly.
"""

try:
    import binascii
except ImportError:
    import ubinascii as binascii
import gc
try:
    import json
except ImportError:
    import ujson as json
import network
import socket
import sys
try:
    import time
except ImportError:
    import utime as time

import mandelbrot_core as core
import network_config as config
import network_protocol as protocol
import rgb_status


def _ticks_ms():
    return time.ticks_ms()


def _ticks_diff(later, earlier):
    return time.ticks_diff(later, earlier)


def _mem_free():
    return gc.mem_free() if hasattr(gc, "mem_free") else -1


def _emit(record_type, data):
    print(json.dumps({"type": record_type, "data": data}))


def _show(status_led, state):
    if status_led is not None:
        getattr(status_led, state)()


def _is_communication_error(exc):
    return isinstance(exc, OSError) or (
        isinstance(exc, RuntimeError) and "Wi-Fi" in str(exc)
    )


def connect_wifi(timeout_seconds=None, status_led=None):
    _show(status_led, "waiting")
    timeout_seconds = timeout_seconds or config.WIFI_TIMEOUT_SECONDS
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    started = _ticks_ms()
    while not wlan.isconnected():
        if _ticks_diff(_ticks_ms(), started) >= int(timeout_seconds * 1000):
            raise RuntimeError("Wi-Fi connection timed out; status=%s" % wlan.status())
        time.sleep_ms(100)
    return wlan


def _connect_tcp(host, port, timeout_seconds):
    address = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(timeout_seconds)
    if hasattr(socket, "TCP_NODELAY"):
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.connect(address)
    return conn


def _validate_job_message(
    message, core_module=None, symmetry="real-axis-upper-half"
):
    if core_module is None:
        core_module = core
    protocol.require_message_type(message, "job")
    expected = (
        ("protocol_version", protocol.PROTOCOL_VERSION),
        ("algorithm_version", core_module.ALGORITHM_VERSION),
        ("output_version", core_module.OUTPUT_VERSION),
        ("checksum_version", core_module.CHECKSUM_VERSION),
    )
    for field, value in expected:
        if message.get(field) != value:
            raise protocol.ProtocolError("job has incompatible " + field)
    if message.get("symmetry") != symmetry:
        raise protocol.ProtocolError("unsupported symmetry mode")
    core_module.validate_job(message["job"])


def run_worker_session(
    conn,
    udp,
    node_id,
    udp_port,
    stall_after_tiles=None,
    stall_seconds=0,
    status_led=None,
    core_module=None,
    symmetry="real-axis-upper-half",
    bytes_per_pixel=1,
    compute_tile_into=None,
):
    if core_module is None:
        core_module = core
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
            "algorithm_version": core_module.ALGORITHM_VERSION,
            "output_version": core_module.OUTPUT_VERSION,
            "checksum_version": core_module.CHECKSUM_VERSION,
            "node_id": node_id,
            "udp_port": udp_port,
            "implementation": str(sys.implementation),
        },
    )
    job_message, payload = protocol.recv_frame(conn)
    if payload:
        raise protocol.ProtocolError("job must not have a payload")
    _validate_job_message(job_message, core_module, symmetry)
    _show(status_led, "job_received")
    job_id = job_message["job_id"]
    job = job_message["job"]
    tile_size = job_message["tile_size"]
    tile_buffer = bytearray(tile_size * tile_size * bytes_per_pixel)

    protocol.send_frame(conn, {"type": "ready", "job_id": job_id})
    data, _address = udp.recvfrom(2048)
    protocol.parse_start_datagram(data, job_id)
    _show(status_led, "tile_waiting")
    completed = 0
    checksum = None
    job_min_free = _mem_free()
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
        _show(status_led, "computing")
        if not stall_injected and stall_after_tiles == completed:
            _emit(
                "fault_injection",
                {
                    "node_id": node_id,
                    "job_id": job_id,
                    "after_tiles": completed,
                    "stall_seconds": stall_seconds,
                },
            )
            stall_injected = True
            time.sleep(stall_seconds)
        gc.collect()
        free_before = _mem_free()
        started = _ticks_ms()
        if compute_tile_into is None:
            core_module.compute_tile_into(
                job,
                tile["x0"],
                tile["y0"],
                tile["width"],
                tile["height"],
                tile_buffer,
                "float",
            )
        else:
            compute_tile_into(
                job,
                tile["x0"],
                tile["y0"],
                tile["width"],
                tile["height"],
                tile_buffer,
            )
        compute_ms = _ticks_diff(_ticks_ms(), started)
        free_after_compute = _mem_free()
        if job_min_free < 0 or (0 <= free_after_compute < job_min_free):
            job_min_free = free_after_compute
        payload_length = tile["width"] * tile["height"] * bytes_per_pixel
        result = memoryview(tile_buffer)[:payload_length]
        _show(status_led, "sending")
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
                "mem_free_before": free_before,
                "mem_free_min_sampled": free_after_compute,
            },
            result,
        )
        del result
        gc.collect()
        completed += 1
        _show(status_led, "tile_waiting")
    _show(status_led, "success")
    return {
        "job_id": job_id,
        "tiles_completed": completed,
        "checksum32": checksum,
        "mem_free_min_sampled": job_min_free,
        "mem_free_after_gc": _mem_free(),
    }


def _run_once(stall_after_tiles, stall_seconds, status_led):
    wlan = connect_wifi(status_led=status_led)
    _emit(
        "wifi",
        {
            "node_id": config.NODE_ID,
            "ifconfig": wlan.ifconfig(),
            "mem_free": _mem_free(),
        },
    )
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.settimeout(config.SOCKET_TIMEOUT_SECONDS)
    if not 1 <= config.UDP_PORT <= 65535:
        raise ValueError("UDP_PORT must be a fixed port between 1 and 65535")
    udp.bind(("0.0.0.0", config.UDP_PORT))
    conn = _connect_tcp(
        config.MANAGER_HOST,
        config.MANAGER_PORT,
        config.SOCKET_TIMEOUT_SECONDS,
    )
    try:
        result = run_worker_session(
            conn,
            udp,
            config.NODE_ID,
            config.UDP_PORT,
            stall_after_tiles=stall_after_tiles,
            stall_seconds=stall_seconds,
            status_led=status_led,
        )
        _emit("complete", result)
        return result
    finally:
        conn.close()
        udp.close()


def run_once(stall_after_tiles=None, stall_seconds=0, status_led=None):
    owns_status_led = status_led is None
    if owns_status_led:
        status_led = rgb_status.RgbStatusLed()
    try:
        return _run_once(stall_after_tiles, stall_seconds, status_led)
    finally:
        if owns_status_led:
            status_led.deinit()


def run_forever(status_led=None):
    if status_led is None:
        status_led = rgb_status.RgbStatusLed()
    try:
        while True:
            try:
                _run_once(None, 0, status_led)
            except Exception as exc:
                if _is_communication_error(exc):
                    status_led.communication_error()
                else:
                    status_led.error()
                _emit("error", {"message": str(exc)})
            gc.collect()
            time.sleep(config.RECONNECT_DELAY_SECONDS)
    finally:
        status_led.deinit()


if __name__ == "__main__":
    run_forever()
