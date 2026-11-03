#!/usr/bin/env python3
"""Calculate the exhibition AC power budget from the equipment inventory."""

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_UP
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = REPO_ROOT / "docs/power-capacity-inventory.csv"


def _decimal(value, field, line):
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("line %d has invalid %s: %r" % (line, field, value)) from exc


def calculate(path, margin_percent, voltage):
    known = []
    unresolved = []
    subtotal = Decimal("0")
    with path.open(encoding="utf-8", newline="") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            quantity = int(row["quantity"])
            if quantity <= 0:
                raise ValueError("line %d quantity must be positive" % line)
            if not row["ac_w_each"].strip():
                unresolved.append(
                    {
                        "section": row["section"],
                        "device": row["device"],
                        "model": row["model"],
                    }
                )
                continue
            watts_each = _decimal(row["ac_w_each"], "ac_w_each", line)
            if watts_each < 0:
                raise ValueError("line %d ac_w_each must not be negative" % line)
            watts = watts_each * quantity
            subtotal += watts
            known.append(
                {
                    "section": row["section"],
                    "device": row["device"],
                    "model": row["model"],
                    "quantity": quantity,
                    "ac_w_each": float(watts_each),
                    "ac_w_subtotal": float(watts),
                    "basis": row["basis"],
                    "status": row["status"],
                }
            )
    multiplier = Decimal("1") + margin_percent / Decimal("100")
    required = subtotal * multiplier
    current = required / voltage
    quantize = Decimal("0.001")
    return {
        "inventory": str(path),
        "known_items": known,
        "unresolved_items": unresolved,
        "margin_percent": float(margin_percent),
        "voltage_v": float(voltage),
        "known_ac_subtotal_w": float(subtotal.quantize(quantize, ROUND_UP)),
        "known_required_w": float(required.quantize(quantize, ROUND_UP)),
        "known_required_a": float(current.quantize(quantize, ROUND_UP)),
        "complete": not unresolved,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--margin-percent", type=Decimal, default=Decimal("25"))
    parser.add_argument("--voltage", type=Decimal, default=Decimal("100"))
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    if args.margin_percent < 0:
        parser.error("margin-percent must not be negative")
    if args.voltage <= 0:
        parser.error("voltage must be positive")
    return args


def main():
    args = parse_args()
    result = calculate(args.inventory, args.margin_percent, args.voltage)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_complete and not result["complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
