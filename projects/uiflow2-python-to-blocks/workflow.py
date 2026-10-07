"""Build and watch MicroPython sources for hand-off to the UiFlow2 Web IDE."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser

from best_effort import BestEffortError, best_effort_convert, markdown_report


UIFLOW_URL = 'https://uiflow2.m5stack.com/'


@dataclass(frozen=True)
class BuildResult:
    project: Path
    notes_json: Path
    notes_markdown: Path
    ready_manifest: Path
    strategy: str
    warning_count: int
    changed: bool


def artifact_paths(source, output_dir, name=None):
    base_name = name or source.stem
    if not base_name or Path(base_name).name != base_name or base_name in {'.', '..'}:
        raise ValueError('artifact name must be one file-name component')
    return {
        'project': output_dir / f'{base_name}.m5f2',
        'notes_json': output_dir / f'{base_name}.notes.json',
        'notes_markdown': output_dir / f'{base_name}.notes.md',
        'ready_manifest': output_dir / f'{base_name}.ready.json',
        'error': output_dir / f'{base_name}.error.txt',
    }


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8') == content:
        return False
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=path.parent,
                prefix=f'.{path.name}.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True


def build_once(source, output_dir, name=None):
    source = source.resolve()
    output_dir = output_dir.resolve()
    paths = artifact_paths(source, output_dir, name)
    text = source.read_text(encoding='utf-8')
    project, report = best_effort_convert(text)
    project_text = json.dumps(project, ensure_ascii=False, indent=2) + '\n'
    notes_json_text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    notes_markdown_text = markdown_report(report)
    warning_count = sum(note['severity'] == 'warning' for note in report['notes'])
    manifest = {
        'schema': 1,
        'status': 'ready',
        'source': str(source),
        'source_sha256': report['source_sha256'],
        'profile': report['profile'],
        'strategy': report['strategy'],
        'warning_count': warning_count,
        'project': str(paths['project']),
        'notes_json': str(paths['notes_json']),
        'notes_markdown': str(paths['notes_markdown']),
    }
    writes = [
        atomic_write(paths['project'], project_text),
        atomic_write(paths['notes_json'], notes_json_text),
        atomic_write(paths['notes_markdown'], notes_markdown_text),
        atomic_write(
            paths['ready_manifest'],
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        ),
    ]
    if paths['error'].exists():
        paths['error'].unlink()
    return BuildResult(
        paths['project'],
        paths['notes_json'],
        paths['notes_markdown'],
        paths['ready_manifest'],
        report['strategy'],
        warning_count,
        any(writes),
    )


def write_error(source, output_dir, name, error):
    paths = artifact_paths(source, output_dir, name)
    timestamp = datetime.now(timezone.utc).isoformat()
    atomic_write(paths['error'], f'{timestamp}\n{type(error).__name__}: {error}\n')
    return paths['error']


def copy_path(path):
    value = str(path.resolve())
    if sys.platform == 'darwin' and shutil.which('pbcopy'):
        subprocess.run(['pbcopy'], input=value, text=True, check=True)
        return
    if sys.platform == 'win32' and shutil.which('clip'):
        subprocess.run(['clip'], input=value, text=True, check=True)
        return
    raise RuntimeError('clipboard copy is supported automatically on macOS and Windows')


def report_success(result, copied=False):
    state = 'updated' if result.changed else 'unchanged'
    copied_text = ' path-copied' if copied else ''
    print(
        f'UIFLOW2_READY project={result.project} strategy={result.strategy} '
        f'warnings={result.warning_count} state={state}{copied_text}',
        flush=True,
    )
    print(f'notes={result.notes_markdown}', flush=True)


def source_signature(source):
    stat = source.stat()
    return stat.st_mtime_ns, stat.st_size


def build_and_handoff(source, output_dir, name, should_copy):
    result = build_once(source, output_dir, name)
    if should_copy:
        copy_path(result.project)
    report_success(result, should_copy)
    return result


def watch(source, output_dir, name, interval, should_copy, should_open):
    last_signature = None
    opened = False
    print(f'UIFLOW2_WATCHING source={source.resolve()}', flush=True)
    while True:
        try:
            signature = source_signature(source)
            if signature != last_signature:
                try:
                    result = build_and_handoff(
                        source, output_dir, name, should_copy)
                    last_signature = signature
                    if should_open and not opened:
                        webbrowser.open(UIFLOW_URL)
                        opened = True
                    print(f'ready_manifest={result.ready_manifest}', flush=True)
                except (BestEffortError, OSError, RuntimeError, ValueError) as exc:
                    error_path = write_error(source, output_dir, name, exc)
                    print(f'UIFLOW2_ERROR error={exc} details={error_path}',
                          file=sys.stderr, flush=True)
                    last_signature = signature
        except FileNotFoundError:
            if last_signature != 'missing':
                print(f'UIFLOW2_WAITING source-missing={source.resolve()}',
                      file=sys.stderr, flush=True)
                last_signature = 'missing'
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('build'))
    parser.add_argument('--name')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=float, default=0.4)
    parser.add_argument('--copy-path', action='store_true')
    parser.add_argument('--open-uiflow', action='store_true')
    args = parser.parse_args()
    if args.interval < 0.1:
        parser.error('--interval must be at least 0.1 seconds')
    try:
        artifact_paths(args.source, args.output_dir, args.name)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        if args.watch:
            watch(
                args.source, args.output_dir, args.name, args.interval,
                args.copy_path, args.open_uiflow,
            )
            return
        result = build_and_handoff(
            args.source, args.output_dir, args.name, args.copy_path)
        if args.open_uiflow:
            webbrowser.open(UIFLOW_URL)
        print(f'ready_manifest={result.ready_manifest}', flush=True)
    except KeyboardInterrupt:
        print('\nUIFLOW2_STOPPED', flush=True)
    except (BestEffortError, OSError, RuntimeError, ValueError) as exc:
        try:
            error_path = write_error(args.source, args.output_dir, args.name, exc)
            parser.exit(2, f'error: {exc}\ndetails: {error_path}\n')
        except (OSError, ValueError):
            parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    main()
