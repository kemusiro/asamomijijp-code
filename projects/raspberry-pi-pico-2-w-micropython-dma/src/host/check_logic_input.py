"""Check the AD2 DIO2 to Pico GP18 connection using Low/High/Low."""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from ctypes import byref, c_int

from dwf_utils import check, last_error, load_dwf


DIO2_MASK = 1 << 2


def set_dio2(dwf, handle, high: bool):
    check(
        dwf,
        dwf.FDwfDigitalIOOutputEnableSet(handle, c_int(DIO2_MASK)),
        "OutputEnableSet",
    )
    check(
        dwf,
        dwf.FDwfDigitalIOOutputSet(handle, c_int(DIO2_MASK if high else 0)),
        "OutputSet",
    )
    check(dwf, dwf.FDwfDigitalIOConfigure(handle), "DigitalIOConfigure")
    time.sleep(0.05)


def read_gp18(mpremote: str, port: str) -> int:
    expression = (
        "from machine import Pin; p=Pin(18,Pin.IN); "
        "print(sum([p.value() for _ in range(101)]))"
    )
    completed = subprocess.run(
        (mpremote, "connect", port, "exec", expression),
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return int(completed.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mpremote", default=os.environ.get("MPREMOTE", "mpremote"))
    parser.add_argument("--port", default="auto")
    parser.add_argument("--dwf")
    args = parser.parse_args()

    dwf = load_dwf(args.dwf)
    handle = c_int()
    check(dwf, dwf.FDwfDeviceOpen(c_int(-1), byref(handle)), "DeviceOpen")
    if handle.value == 0:
        raise RuntimeError(f"device handle is zero: {last_error(dwf)}")
    try:
        set_dio2(dwf, handle, False)
        low_before = read_gp18(args.mpremote, args.port)
        set_dio2(dwf, handle, True)
        high = read_gp18(args.mpremote, args.port)
        set_dio2(dwf, handle, False)
        low_after = read_gp18(args.mpremote, args.port)
        print(f"RESULT,low_before,{low_before},high,{high},low_after,{low_after}")
        if (low_before, high, low_after) != (0, 101, 0):
            raise RuntimeError("DIO2 to GP18 connectivity check failed")
        print("STATUS,ok")
    finally:
        dwf.FDwfDigitalIOOutputSet(handle, c_int(0))
        dwf.FDwfDigitalIOOutputEnableSet(handle, c_int(0))
        dwf.FDwfDigitalIOConfigure(handle)
        dwf.FDwfDeviceClose(handle)


if __name__ == "__main__":
    main()
