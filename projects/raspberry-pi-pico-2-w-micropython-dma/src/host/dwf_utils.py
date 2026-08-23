"""Small ctypes helpers shared by the WaveForms SDK acquisition scripts."""

from __future__ import annotations

import ctypes.util
import os
from ctypes import cdll, create_string_buffer
from pathlib import Path


def resolve_dwf_path(explicit: str | None = None) -> str:
    """Return a usable WaveForms SDK library path without embedding host details."""
    candidates = (
        explicit,
        os.environ.get("DWF_LIBRARY"),
        ctypes.util.find_library("dwf"),
        "/Library/Frameworks/dwf.framework/dwf",
        "/usr/lib/libdwf.so",
        "/usr/local/lib/libdwf.so",
    )
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isabs(candidate) and not Path(candidate).exists():
            continue
        return candidate
    raise FileNotFoundError(
        "WaveForms SDK library not found; pass --dwf or set DWF_LIBRARY"
    )


def load_dwf(explicit: str | None = None):
    return cdll.LoadLibrary(resolve_dwf_path(explicit))


def last_error(dwf) -> str:
    message = create_string_buffer(512)
    dwf.FDwfGetLastErrorMsg(message)
    return message.value.decode(errors="replace")


def check(dwf, result, operation: str) -> None:
    if not result:
        raise RuntimeError(f"{operation}: {last_error(dwf)}")
