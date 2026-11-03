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


DEFAULT_STARTUP_TIMEOUT_SECONDS = 90
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10
DEFAULT_RUNTIME_SOCKET_TIMEOUT_SECONDS = 7
DEFAULT_WATCHDOG_TIMEOUT_MS = 8000
MAX_RP2_WATCHDOG_TIMEOUT_MS = 8388
DEFAULT_WIFI_STAGGER_STEP_MS = 200
MAX_WIFI_STAGGER_STEP_MS = 500
DEFAULT_WIFI_RESET_DELAY_MS = 250
DEFAULT_WIFI_POWER_MANAGEMENT = "none"
DEFAULT_MANAGER_ERRORS_BEFORE_WIFI_RESET = 8
MAX_MANAGER_ERRORS_BEFORE_WIFI_RESET = 60


_consecutive_manager_connect_errors = 0


def _ticks_ms():
    return time.ticks_ms()


def _ticks_diff(later, earlier):
    return time.ticks_diff(later, earlier)


def _mem_free():
    return gc.mem_free() if hasattr(gc, "mem_free") else -1


def _startup_timeout_seconds():
    return getattr(
        config,
        "STARTUP_TIMEOUT_SECONDS",
        DEFAULT_STARTUP_TIMEOUT_SECONDS,
    )


def _connect_timeout_seconds():
    return getattr(
        config,
        "CONNECT_TIMEOUT_SECONDS",
        DEFAULT_CONNECT_TIMEOUT_SECONDS,
    )


def _runtime_socket_timeout_seconds():
    return getattr(
        config,
        "RUNTIME_SOCKET_TIMEOUT_SECONDS",
        DEFAULT_RUNTIME_SOCKET_TIMEOUT_SECONDS,
    )


def _wifi_stagger_step_ms():
    value = getattr(
        config,
        "WIFI_STAGGER_STEP_MS",
        DEFAULT_WIFI_STAGGER_STEP_MS,
    )
    if type(value) is not int or not 0 <= value <= MAX_WIFI_STAGGER_STEP_MS:
        raise ValueError(
            "WIFI_STAGGER_STEP_MS must be an integer from 0 to %d"
            % MAX_WIFI_STAGGER_STEP_MS
        )
    return value


def _wifi_stagger_delay_ms():
    try:
        node_number = int(str(config.NODE_ID).rsplit("-", 1)[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0
    if node_number < 1:
        return 0
    return ((node_number - 1) % 16) * _wifi_stagger_step_ms()


def _wifi_reset_delay_ms():
    value = getattr(
        config,
        "WIFI_RESET_DELAY_MS",
        DEFAULT_WIFI_RESET_DELAY_MS,
    )
    if type(value) is not int or not 100 <= value <= 1000:
        raise ValueError("WIFI_RESET_DELAY_MS must be an integer from 100 to 1000")
    return value


def _wifi_power_management():
    value = getattr(
        config,
        "WIFI_POWER_MANAGEMENT",
        DEFAULT_WIFI_POWER_MANAGEMENT,
    )
    if value not in ("none", "performance", "powersave", "default"):
        raise ValueError(
            "WIFI_POWER_MANAGEMENT must be none, performance, powersave, or default"
        )
    return value


def _manager_errors_before_wifi_reset():
    value = getattr(
        config,
        "MANAGER_ERRORS_BEFORE_WIFI_RESET",
        DEFAULT_MANAGER_ERRORS_BEFORE_WIFI_RESET,
    )
    if (
        type(value) is not int
        or not 1 <= value <= MAX_MANAGER_ERRORS_BEFORE_WIFI_RESET
    ):
        raise ValueError(
            "MANAGER_ERRORS_BEFORE_WIFI_RESET must be an integer from 1 to %d"
            % MAX_MANAGER_ERRORS_BEFORE_WIFI_RESET
        )
    return value


def _watchdog_timeout_ms():
    value = getattr(config, "WATCHDOG_TIMEOUT_MS", DEFAULT_WATCHDOG_TIMEOUT_MS)
    if type(value) is not int or not 1000 <= value <= MAX_RP2_WATCHDOG_TIMEOUT_MS:
        raise ValueError(
            "WATCHDOG_TIMEOUT_MS must be an integer from 1000 to %d"
            % MAX_RP2_WATCHDOG_TIMEOUT_MS
        )
    return value


def _feed_watchdog(watchdog):
    if watchdog is not None:
        watchdog.feed()


def _reset_cause_name(machine_module, reset_cause):
    for name in (
        "PWRON_RESET",
        "HARD_RESET",
        "WDT_RESET",
        "DEEPSLEEP_RESET",
        "SOFT_RESET",
    ):
        if getattr(machine_module, name, None) == reset_cause:
            return name
    return "UNKNOWN"


def _create_watchdog(machine_module=None):
    if machine_module is None:
        import machine as machine_module

    reset_cause = machine_module.reset_cause()
    timeout_ms = _watchdog_timeout_ms()
    watchdog = machine_module.WDT(timeout=timeout_ms)
    watchdog.feed()
    return (
        watchdog,
        reset_cause,
        _reset_cause_name(machine_module, reset_cause),
        timeout_ms,
    )


def _emit(record_type, data):
    print(json.dumps({"type": record_type, "data": data}))


def _show(status_led, state):
    if status_led is not None:
        getattr(status_led, state)()


def _is_communication_error(exc):
    return isinstance(exc, OSError) or (
        isinstance(exc, RuntimeError) and "Wi-Fi" in str(exc)
    )


def _configure_wifi_power_management(wlan):
    mode = _wifi_power_management()
    if mode == "default":
        return
    attribute = {
        "none": "PM_NONE",
        "performance": "PM_PERFORMANCE",
        "powersave": "PM_POWERSAVE",
    }[mode]
    value = getattr(wlan, attribute, None)
    if value is None:
        if mode != "none":
            raise RuntimeError("Wi-Fi power management mode is unsupported")
        value = 0xA11140
    wlan.config(pm=value)


def _deactivate_wifi(wlan, watchdog=None):
    try:
        wlan.disconnect()
    except OSError:
        pass
    _feed_watchdog(watchdog)
    wlan.active(False)
    _watchdog_sleep(_wifi_reset_delay_ms() / 1000, watchdog)


def connect_wifi(timeout_seconds=None, status_led=None, watchdog=None):
    _show(status_led, "waiting")
    _feed_watchdog(watchdog)
    timeout_seconds = timeout_seconds or config.WIFI_TIMEOUT_SECONDS
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        _configure_wifi_power_management(wlan)
        _feed_watchdog(watchdog)
        return wlan
    _watchdog_sleep(_wifi_stagger_delay_ms() / 1000, watchdog)
    _deactivate_wifi(wlan, watchdog)
    wlan.active(True)
    _configure_wifi_power_management(wlan)
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    started = _ticks_ms()
    while not wlan.isconnected():
        _feed_watchdog(watchdog)
        if _ticks_diff(_ticks_ms(), started) >= int(timeout_seconds * 1000):
            status = wlan.status()
            _deactivate_wifi(wlan, watchdog)
            raise RuntimeError("Wi-Fi connection timed out; status=%s" % status)
        time.sleep_ms(100)
    _feed_watchdog(watchdog)
    return wlan


def _reset_wifi_after_manager_connect_error(wlan, exc, watchdog=None):
    global _consecutive_manager_connect_errors
    if _is_socket_timeout(exc) or not wlan.isconnected():
        _consecutive_manager_connect_errors = 0
        _deactivate_wifi(wlan, watchdog)
        return True
    if isinstance(exc, OSError):
        _consecutive_manager_connect_errors += 1
        if (
            _consecutive_manager_connect_errors
            >= _manager_errors_before_wifi_reset()
        ):
            _consecutive_manager_connect_errors = 0
            _deactivate_wifi(wlan, watchdog)
            return True
    else:
        _consecutive_manager_connect_errors = 0
    return False


def _connect_tcp(host, port, timeout_seconds, watchdog=None):
    _feed_watchdog(watchdog)
    address = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.settimeout(timeout_seconds)
    if hasattr(socket, "TCP_NODELAY"):
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    _feed_watchdog(watchdog)
    conn.connect(address)
    _feed_watchdog(watchdog)
    return conn


def _is_socket_timeout(exc):
    timeout_type = getattr(socket, "timeout", None)
    if timeout_type is not None and isinstance(exc, timeout_type):
        return True
    if not isinstance(exc, OSError) or not exc.args:
        return False
    message = str(exc).lower()
    if "timed out" in message or "etimedout" in message:
        return True
    try:
        return abs(int(exc.args[0])) in (110, 116)
    except (TypeError, ValueError):
        return False


def _connect_manager_tcp(wlan, host, port, timeout_seconds, watchdog=None):
    global _consecutive_manager_connect_errors
    try:
        conn = _connect_tcp(
            host,
            port,
            timeout_seconds,
            watchdog=watchdog,
        )
    except Exception as exc:
        _reset_wifi_after_manager_connect_error(wlan, exc, watchdog)
        raise
    _consecutive_manager_connect_errors = 0
    return conn


def _wait_for_start(udp, job_id, timeout_seconds, watchdog=None):
    started = _ticks_ms()
    while True:
        _feed_watchdog(watchdog)
        try:
            data, _address = udp.recvfrom(2048)
        except OSError as exc:
            if not _is_socket_timeout(exc):
                raise
            if _ticks_diff(_ticks_ms(), started) >= int(timeout_seconds * 1000):
                raise RuntimeError("start datagram timed out")
            continue
        _feed_watchdog(watchdog)
        protocol.parse_start_datagram(data, job_id)
        return


def _wait_for_tcp_start(conn, job_id, timeout_seconds, watchdog=None):
    started = _ticks_ms()
    message, payload = protocol.recv_frame(
        conn,
        timeout_handler=(
            _startup_timeout_handler(started, timeout_seconds, watchdog)
            if watchdog is not None
            else None
        ),
    )
    if payload:
        raise protocol.ProtocolError("start message must not have a payload")
    protocol.validate_start_message(message, job_id)


def _startup_timeout_handler(started, timeout_seconds, watchdog):
    def handle(exc):
        if not _is_socket_timeout(exc):
            return False
        _feed_watchdog(watchdog)
        if _ticks_diff(_ticks_ms(), started) >= int(timeout_seconds * 1000):
            raise RuntimeError("worker startup timed out")
        return True

    return handle


def _watchdog_sleep(seconds, watchdog):
    remaining_ms = max(0, int(seconds * 1000))
    while remaining_ms:
        _feed_watchdog(watchdog)
        sleep_ms = min(remaining_ms, 500)
        time.sleep_ms(sleep_ms)
        remaining_ms -= sleep_ms
    _feed_watchdog(watchdog)


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
    watchdog=None,
    reset_cause=None,
    reset_cause_name=None,
    watchdog_timeout_ms=None,
):
    if core_module is None:
        core_module = core
    if stall_after_tiles is not None:
        if type(stall_after_tiles) is not int or stall_after_tiles < 0:
            raise ValueError("stall_after_tiles must be a non-negative integer")
        if not isinstance(stall_seconds, (int, float)) or stall_seconds <= 0:
            raise ValueError("stall_seconds must be positive when injecting a stall")
    hello = {
        "type": "hello",
        "protocol_version": protocol.PROTOCOL_VERSION,
        "algorithm_version": core_module.ALGORITHM_VERSION,
        "output_version": core_module.OUTPUT_VERSION,
        "checksum_version": core_module.CHECKSUM_VERSION,
        "node_id": node_id,
        "udp_port": udp_port,
        "start_transport": "tcp",
        "implementation": str(sys.implementation),
        "watchdog_enabled": watchdog is not None,
    }
    if reset_cause is not None:
        hello["reset_cause"] = reset_cause
        hello["reset_cause_name"] = reset_cause_name
    if watchdog_timeout_ms is not None:
        hello["watchdog_timeout_ms"] = watchdog_timeout_ms
    _feed_watchdog(watchdog)
    protocol.send_frame(
        conn,
        hello,
    )
    _feed_watchdog(watchdog)
    startup_started = _ticks_ms()
    job_message, payload = protocol.recv_frame(
        conn,
        timeout_handler=(
            _startup_timeout_handler(
                startup_started,
                _startup_timeout_seconds(),
                watchdog,
            )
            if watchdog is not None
            else None
        ),
    )
    _feed_watchdog(watchdog)
    if payload:
        raise protocol.ProtocolError("job must not have a payload")
    _validate_job_message(job_message, core_module, symmetry)
    _show(status_led, "job_received")
    job_id = job_message["job_id"]
    job = job_message["job"]
    tile_size = job_message["tile_size"]
    tile_buffer = bytearray(tile_size * tile_size * bytes_per_pixel)

    protocol.send_frame(conn, {"type": "ready", "job_id": job_id})
    _feed_watchdog(watchdog)
    _wait_for_tcp_start(
        conn,
        job_id,
        _startup_timeout_seconds(),
        watchdog,
    )
    if hasattr(conn, "settimeout"):
        conn.settimeout(_runtime_socket_timeout_seconds())
    _show(status_led, "tile_waiting")
    completed = 0
    checksum = None
    job_min_free = _mem_free()
    stall_injected = False

    while True:
        _feed_watchdog(watchdog)
        tile, payload = protocol.recv_frame(conn)
        _feed_watchdog(watchdog)
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
        _feed_watchdog(watchdog)
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
        _feed_watchdog(watchdog)
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
        _feed_watchdog(watchdog)
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


def _run_once(
    stall_after_tiles,
    stall_seconds,
    status_led,
    watchdog=None,
    reset_cause=None,
    reset_cause_name=None,
    watchdog_timeout_ms=None,
):
    wlan = connect_wifi(status_led=status_led, watchdog=watchdog)
    _emit(
        "wifi",
        {
            "node_id": config.NODE_ID,
            "ifconfig": wlan.ifconfig(),
            "mem_free": _mem_free(),
        },
    )
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    startup_timeout = _startup_timeout_seconds()
    socket_timeout = startup_timeout
    connect_timeout = _connect_timeout_seconds()
    if watchdog is not None:
        socket_timeout = min(startup_timeout, _runtime_socket_timeout_seconds())
        connect_timeout = min(connect_timeout, _runtime_socket_timeout_seconds())
    udp.settimeout(socket_timeout)
    if not 1 <= config.UDP_PORT <= 65535:
        raise ValueError("UDP_PORT must be a fixed port between 1 and 65535")
    udp.bind(("0.0.0.0", config.UDP_PORT))
    conn = _connect_manager_tcp(
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
    stall_after_tiles=None,
    stall_seconds=0,
    status_led=None,
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
            stall_after_tiles,
            stall_seconds,
            status_led,
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
    watchdog, reset_cause, reset_cause_name, timeout_ms = _create_watchdog(
        machine_module
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
                    None,
                    0,
                    status_led,
                    watchdog=watchdog,
                    reset_cause=reset_cause,
                    reset_cause_name=reset_cause_name,
                    watchdog_timeout_ms=timeout_ms,
                )
            except Exception as exc:
                _feed_watchdog(watchdog)
                if _is_communication_error(exc):
                    status_led.communication_error()
                else:
                    status_led.error()
                _emit("error", {"message": str(exc)})
                _feed_watchdog(watchdog)
            gc.collect()
            _watchdog_sleep(config.RECONNECT_DELAY_SECONDS, watchdog)
    finally:
        status_led.deinit()


if __name__ == "__main__":
    run_forever()
