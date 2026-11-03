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


def run_worker_session(
    conn,
    udp,
    node_id,
    udp_port,
    stall_after_tiles=None,
    stall_seconds=0,
    status_led=None,
    watchdog=None,
    reset_cause=None,
    reset_cause_name=None,
    watchdog_timeout_ms=None,
):
    return cluster_worker.run_worker_session(
        conn,
        udp,
        node_id,
        udp_port,
        stall_after_tiles=stall_after_tiles,
        stall_seconds=stall_seconds,
        status_led=status_led,
        core_module=core,
        symmetry="none",
        bytes_per_pixel=3,
        compute_tile_into=core.compute_tile_into,
        watchdog=watchdog,
        reset_cause=reset_cause,
        reset_cause_name=reset_cause_name,
        watchdog_timeout_ms=watchdog_timeout_ms,
    )


def _run_once(
    status_led,
    stall_after_tiles=None,
    stall_seconds=0,
    watchdog=None,
    reset_cause=None,
    reset_cause_name=None,
    watchdog_timeout_ms=None,
):
    wlan = cluster_worker.connect_wifi(
        status_led=status_led,
        watchdog=watchdog,
    )
    _emit(
        "wifi",
        {
            "node_id": config.NODE_ID,
            "ifconfig": wlan.ifconfig(),
            "mem_free": _mem_free(),
        },
    )
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    startup_timeout = cluster_worker._startup_timeout_seconds()
    socket_timeout = startup_timeout
    connect_timeout = cluster_worker._connect_timeout_seconds()
    if watchdog is not None:
        socket_timeout = min(
            startup_timeout,
            cluster_worker._runtime_socket_timeout_seconds(),
        )
        connect_timeout = min(
            connect_timeout,
            cluster_worker._runtime_socket_timeout_seconds(),
        )
    udp.settimeout(socket_timeout)
    if not 1 <= config.UDP_PORT <= 65535:
        raise ValueError("UDP_PORT must be a fixed port between 1 and 65535")
    udp.bind(("0.0.0.0", config.UDP_PORT))
    conn = cluster_worker._connect_manager_tcp(
        wlan,
        config.MANAGER_HOST,
        config.MANAGER_PORT,
        connect_timeout,
        watchdog=watchdog,
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
            watchdog=watchdog,
            reset_cause=reset_cause,
            reset_cause_name=reset_cause_name,
            watchdog_timeout_ms=watchdog_timeout_ms,
        )
        _emit("complete", result)
        return result
    finally:
        conn.close()
        udp.close()


def run_once(
    status_led=None,
    stall_after_tiles=None,
    stall_seconds=0,
    watchdog=None,
    reset_cause=None,
    reset_cause_name=None,
    watchdog_timeout_ms=None,
):
    owns_status_led = status_led is None
    if owns_status_led:
        status_led = rgb_status.RgbStatusLed()
    try:
        return _run_once(
            status_led,
            stall_after_tiles=stall_after_tiles,
            stall_seconds=stall_seconds,
            watchdog=watchdog,
            reset_cause=reset_cause,
            reset_cause_name=reset_cause_name,
            watchdog_timeout_ms=watchdog_timeout_ms,
        )
    finally:
        if owns_status_led:
            status_led.deinit()


def run_forever(status_led=None, machine_module=None):
    if status_led is None:
        status_led = rgb_status.RgbStatusLed()
    watchdog, reset_cause, reset_cause_name, timeout_ms = (
        cluster_worker._create_watchdog(machine_module)
    )
    _emit(
        "watchdog",
        {
            "enabled": True,
            "timeout_ms": timeout_ms,
            "reset_cause": reset_cause,
            "reset_cause_name": reset_cause_name,
        },
    )
    try:
        while True:
            try:
                _run_once(
                    status_led,
                    watchdog=watchdog,
                    reset_cause=reset_cause,
                    reset_cause_name=reset_cause_name,
                    watchdog_timeout_ms=timeout_ms,
                )
            except Exception as exc:
                cluster_worker._feed_watchdog(watchdog)
                if cluster_worker._is_communication_error(exc):
                    status_led.communication_error()
                else:
                    status_led.error()
                _emit("error", {"message": str(exc)})
                cluster_worker._feed_watchdog(watchdog)
            gc.collect()
            cluster_worker._watchdog_sleep(
                config.RECONNECT_DELAY_SECONDS,
                watchdog,
            )
    finally:
        status_led.deinit()


if __name__ == "__main__":
    run_forever()
