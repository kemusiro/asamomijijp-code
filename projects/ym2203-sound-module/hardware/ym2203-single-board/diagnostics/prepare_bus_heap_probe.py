# SPDX-License-Identifier: MIT
"""Prepare a silent MicroPython heap probe without importing the audio engine.

Only production method bodies are extracted; emitter/platform-dependent setup
is omitted. This tests Python allocation, not electrical timing or GC latency.
Usage: python3 prepare_bus_heap_probe.py OUT_DIR [LEGACY_BUS_PY]
"""
import ast
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent


def constant(file, name):
    source = (HERE/file).read_text()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.get_source_segment(source, node.value)
    raise ValueError(name)


def method(file, cls, name):
    source = (HERE/file).read_text()
    owner = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == cls)
    node = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node)


def prepare(destination, bus_source=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    helper = 'from rev_c_bus_check import RevCBus, SSG_MASKS\n'
    helper += 'CHORD_LEVEL=7\nSINGLE_LEVEL=10\n'
    helper += 'SSG_PERIODS='+constant('rev_c_i2c_voice_pitch_target.py', 'SSG_PERIODS')+'\n'
    helper += 'class Live:\n    PITCHES='+constant('rev_c_fm_live.py', 'PITCHES')+'\n'
    helper += 'class Control:\n    live=Live\ncontrol=Control\nclass PitchBus(RevCBus):\n'
    for file, cls, name in (
        ('rev_c_fm_ssg_check.py', 'MixerBus', 'write_ssg'),
        ('rev_c_fm_ssg_check.py', 'MixerBus', 'checked'),
        ('rev_c_i2c_voice_pitch_target.py', 'PitchBus', 'pitch_step'),
    ):
        helper += '    '+method(file, cls, name)+'\n'
    (destination/'_probe_target.py').write_text(helper)
    shutil.copyfile(bus_source or HERE/'rev_c_bus_check.py', destination/'rev_c_bus_check.py')
    shutil.copyfile(HERE/'verify_bus_heap_micropython.py', destination/'verify_bus_heap_micropython.py')


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    prepare(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
