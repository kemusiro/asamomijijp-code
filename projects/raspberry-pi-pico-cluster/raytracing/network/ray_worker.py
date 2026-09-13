"""MicroPython network worker for the Pico cluster ray-tracing demo."""

import gc
try:
    import json
except ImportError:
    import ujson as json
import socket
try:
    import time
except ImportError:
    import utime as time

import network_config as config
import network_protocol as protocol
import pico_worker as cluster_worker
import raytracer_core as core
import rgb_status


def _mem_free():
    return gc.mem_free() if hasattr(gc, "mem_free") else -1


def _emit(record_type, data):
    print(json.dumps({"type": record_type, "data": data}))


def run_worker_session(conn, udp, node_id, udp_port, status_led=None):
    return cluster_worker.run_worker_session(
        conn,
        udp,
        node_id,
        udp_port,
        status_led=status_led,
        core_module=core,
        symmetry="none",
        bytes_per_pixel=3,
        compute_tile_into=core.compute_tile_into,
    )


def _run_once(status_led):
    wlan = cluster_worker.connect_wifi(status_led=status_led)
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
    conn = cluster_worker._connect_tcp(
        config.MANAGER_HOST,
        config.MANAGER_PORT,
        config.SOCKET_TIMEOUT_SECONDS,
    )
    try:
        result = run_worker_session(
            conn, udp, config.NODE_ID, config.UDP_PORT, status_led=status_led
        )
        _emit("complete", result)
        return result
    finally:
        conn.close()
        udp.close()


def run_once(status_led=None):
    owns_status_led = status_led is None
    if owns_status_led:
        status_led = rgb_status.RgbStatusLed()
    try:
        return _run_once(status_led)
    finally:
        if owns_status_led:
            status_led.deinit()


def run_forever(status_led=None):
    if status_led is None:
        status_led = rgb_status.RgbStatusLed()
    try:
        while True:
            try:
                _run_once(status_led)
            except Exception as exc:
                if cluster_worker._is_communication_error(exc):
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
