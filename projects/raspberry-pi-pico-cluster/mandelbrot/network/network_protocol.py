"""MicroPython-compatible framing for the multi-node Mandelbrot protocol."""

try:
    import json
except ImportError:
    import ujson as json
import struct


PROTOCOL_VERSION = "mandelbrot-wire-v2"
ALGORITHM_VERSION = "mandelbrot-tile-float32-v2"
OUTPUT_VERSION = "iterations-u8-v1"
CHECKSUM_VERSION = "row-crc32-mix-v1"

MAX_HEADER_BYTES = 8192
MAX_PAYLOAD_BYTES = 65536
_LENGTH_FORMAT = ">I"
_LENGTH_SIZE = 4


class ProtocolError(Exception):
    pass


def _json_dumps(message):
    try:
        return json.dumps(message, separators=(",", ":"), sort_keys=True)
    except TypeError:
        return json.dumps(message)


def _send_all(sock, data):
    view = memoryview(data)
    sent = 0
    while sent < len(view):
        count = sock.send(view[sent:])
        if count is None:
            count = len(view) - sent
        if count <= 0:
            raise ProtocolError("socket closed while sending")
        sent += count


def recv_exact(sock, size):
    if size < 0:
        raise ProtocolError("negative receive size")
    result = bytearray(size)
    view = memoryview(result)
    received = 0
    while received < size:
        chunk = sock.recv(size - received)
        if not chunk:
            raise ProtocolError("socket closed while receiving")
        view[received : received + len(chunk)] = chunk
        received += len(chunk)
    return result


def _encode_header(message, payload_length):
    if not isinstance(message, dict):
        raise ProtocolError("message must be a dict")
    if payload_length > MAX_PAYLOAD_BYTES:
        raise ProtocolError("payload is too large")
    header = dict(message)
    header["payload_length"] = payload_length
    encoded = _json_dumps(header).encode("utf-8")
    if not encoded or len(encoded) > MAX_HEADER_BYTES:
        raise ProtocolError("header size is invalid")
    return encoded


def encode_frame(message, payload=b""):
    encoded = _encode_header(message, len(payload))
    return struct.pack(_LENGTH_FORMAT, len(encoded)) + encoded + bytes(payload)


def send_frame(sock, message, payload=b""):
    encoded = _encode_header(message, len(payload))
    prefix = struct.pack(_LENGTH_FORMAT, len(encoded))
    header = prefix + encoded
    _send_all(sock, header)
    if payload:
        _send_all(sock, payload)
    return len(header) + len(payload)


def recv_frame(sock):
    header_length = struct.unpack(
        _LENGTH_FORMAT, recv_exact(sock, _LENGTH_SIZE)
    )[0]
    if header_length <= 0 or header_length > MAX_HEADER_BYTES:
        raise ProtocolError("header size is invalid")
    encoded = recv_exact(sock, header_length)
    try:
        message = json.loads(bytes(encoded).decode("utf-8"))
    except (TypeError, ValueError):
        raise ProtocolError("header is not valid JSON")
    if not isinstance(message, dict):
        raise ProtocolError("header JSON must be an object")
    payload_length = message.get("payload_length")
    if not isinstance(payload_length, int) or payload_length < 0:
        raise ProtocolError("payload_length is invalid")
    if payload_length > MAX_PAYLOAD_BYTES:
        raise ProtocolError("payload is too large")
    payload = recv_exact(sock, payload_length)
    return message, payload


def require_message_type(message, expected):
    actual = message.get("type")
    if actual != expected:
        raise ProtocolError("expected %s, got %s" % (expected, actual))


def validate_hello(
    message,
    algorithm_version=ALGORITHM_VERSION,
    output_version=OUTPUT_VERSION,
    checksum_version=CHECKSUM_VERSION,
):
    require_message_type(message, "hello")
    expected = (
        ("protocol_version", PROTOCOL_VERSION),
        ("algorithm_version", algorithm_version),
        ("output_version", output_version),
        ("checksum_version", checksum_version),
    )
    for field, value in expected:
        if message.get(field) != value:
            raise ProtocolError("incompatible " + field)
    node_id = message.get("node_id")
    if not isinstance(node_id, str) or not node_id or len(node_id) > 64:
        raise ProtocolError("node_id is invalid")
    udp_port = message.get("udp_port")
    if not isinstance(udp_port, int) or not 1 <= udp_port <= 65535:
        raise ProtocolError("udp_port is invalid")


def make_start_datagram(job_id):
    message = {
        "type": "start",
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job_id,
    }
    return _json_dumps(message).encode("utf-8")


def parse_start_datagram(data, expected_job_id):
    try:
        message = json.loads(bytes(data).decode("utf-8"))
    except (TypeError, ValueError):
        raise ProtocolError("start datagram is not valid JSON")
    require_message_type(message, "start")
    if message.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("incompatible protocol_version")
    if message.get("job_id") != expected_job_id:
        raise ProtocolError("start datagram has a different job_id")
    return message
