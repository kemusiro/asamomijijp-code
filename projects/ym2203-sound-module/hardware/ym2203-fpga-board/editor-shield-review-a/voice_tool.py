#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline JSON validator/register-plan viewer; no USB/device access."""
import argparse,json
from pathlib import Path
from voice_model import loads,dumps,register_plan
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--registers',action='store_true');a=p.parse_args()
    if a.file.stat().st_size>4096:raise SystemExit('voice file exceeds4096bytes')
    voice=loads(a.file.read_text(encoding='utf8'))
    print(json.dumps(register_plan(voice),indent=2) if a.registers else dumps(voice),end='\n' if a.registers else '')
