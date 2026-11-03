#!/usr/bin/env python3
"""Pico workerをnode ID照合後に1台ずつ転送して再起動する。"""

import argparse
import glob
import hashlib
import json
from pathlib import Path
import re
import time


NODE_ID_PATTERN = re.compile(r"^pico-(\d{2})$")
FILES = (
    (
        "projects/raspberry-pi-pico-cluster/mandelbrot/network/pico_worker.py",
        "pico_worker.py",
    ),
    (
        "projects/raspberry-pi-pico-cluster/raytracing/network/ray_worker.py",
        "ray_worker.py",
    ),
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_node_id(output):
    lines = output.decode().strip().splitlines()
    if not lines or NODE_ID_PATTERN.fullmatch(lines[-1]) is None:
        raise RuntimeError("node IDを取得できません: %r" % lines)
    return lines[-1]


def expected_node_ids(count):
    return {"pico-%02d" % number for number in range(1, count + 1)}


def load_payloads(repo_root):
    payloads = []
    for local_name, remote_name in FILES:
        path = repo_root / local_name
        data = path.read_bytes()
        payloads.append((path, remote_name, data, sha256(data)))
    return payloads


def feed_watchdog(board):
    board.exec("import machine; machine.WDT(timeout=8000).feed()")


def reset_board(board):
    try:
        board.exec_raw_no_follow("import machine; machine.reset()")
    except OSError:
        pass


def process_board(transport_class, port, payloads, apply):
    board = transport_class(port)
    record = {"serial_port": port, "applied": False, "files": {}}
    reset_requested = False
    try:
        board.enter_raw_repl(soft_reset=False)
        feed_watchdog(board)
        node_id = parse_node_id(
            board.exec("import network_config; print(network_config.NODE_ID)")
        )
        record["node_id"] = node_id
        for _path, remote_name, _data, target_hash in payloads:
            before = board.fs_hashfile(remote_name, "sha256").hex()
            record["files"][remote_name] = {
                "before_sha256": before,
                "target_sha256": target_hash,
            }
        if apply:
            for _path, remote_name, data, target_hash in payloads:
                feed_watchdog(board)
                if record["files"][remote_name]["before_sha256"] != target_hash:
                    board.fs_writefile(remote_name, data)
                feed_watchdog(board)
                after = board.fs_hashfile(remote_name, "sha256").hex()
                record["files"][remote_name]["after_sha256"] = after
                if after != target_hash:
                    raise RuntimeError(
                        "%sのhash不一致: %s" % (remote_name, after)
                    )
            record["applied"] = True
        reset_board(board)
        reset_requested = True
        return record
    finally:
        if not reset_requested:
            try:
                board.enter_raw_repl(soft_reset=False)
                reset_board(board)
            except Exception:
                pass
        try:
            board.close()
        except Exception:
            pass


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--port-glob", default="/dev/cu.usbmodem*")
    parser.add_argument("--expected", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reset-stagger-seconds", type=float, default=6)
    args = parser.parse_args()
    if args.expected <= 0 or args.reset_stagger_seconds < 0:
        parser.error("expectedは正数、reset間隔は0以上にしてください")
    return args


def main():
    args = parse_args()
    try:
        from mpremote.transport_serial import SerialTransport
    except ImportError as exc:
        raise RuntimeError("mpremoteをインストールしたPythonで実行してください") from exc

    ports = sorted(glob.glob(args.port_glob))
    if len(ports) != args.expected:
        raise RuntimeError(
            "USB serial deviceは%d台、期待値は%d台です"
            % (len(ports), args.expected)
        )
    payloads = load_payloads(args.repo_root.resolve())
    inventory = []
    seen = set()
    for index, port in enumerate(ports, 1):
        record = process_board(SerialTransport, port, payloads, False)
        node_id = record["node_id"]
        if node_id in seen:
            raise RuntimeError("node IDが重複しています: " + node_id)
        seen.add(node_id)
        inventory.append(record)
        print(
            "%02d/%02d %s %s %s"
            % (
                index,
                args.expected,
                node_id,
                port,
                "確認",
            ),
            flush=True,
        )
        if index < len(ports):
            time.sleep(args.reset_stagger_seconds)

    missing = expected_node_ids(args.expected) - seen
    unexpected = seen - expected_node_ids(args.expected)
    if missing or unexpected:
        raise RuntimeError(
            "node ID不一致: missing=%s unexpected=%s"
            % (sorted(missing), sorted(unexpected))
        )
    records = inventory
    if args.apply:
        records = []
        expected_by_port = {
            record["serial_port"]: record["node_id"] for record in inventory
        }
        for index, port in enumerate(ports, 1):
            record = process_board(SerialTransport, port, payloads, True)
            if record["node_id"] != expected_by_port[port]:
                raise RuntimeError(
                    "確認時とnode IDが変わりました: %s: %s -> %s"
                    % (port, expected_by_port[port], record["node_id"])
                )
            records.append(record)
            print(
                "%02d/%02d %s %s 適用"
                % (index, args.expected, record["node_id"], port),
                flush=True,
            )
            if index < len(ports):
                time.sleep(args.reset_stagger_seconds)
    result = {
        "applied": args.apply,
        "expected": args.expected,
        "payloads": {
            remote_name: target_hash
            for _path, remote_name, _data, target_hash in payloads
        },
        "inventory": sorted(inventory, key=lambda item: item["node_id"]),
        "devices": sorted(records, key=lambda item: item["node_id"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("完了:", args.output)


if __name__ == "__main__":
    main()
