#!/usr/bin/env python3
import argparse, hashlib, json, pathlib, signal, subprocess, time
p = argparse.ArgumentParser()
p.add_argument('--uid', required=True)
p.add_argument('--template-sha', required=True)
p.add_argument('--seconds', type=int, default=12000)
p.add_argument('--stop-file', required=True)
p.add_argument('--check-only', action='store_true')
a = p.parse_args()

def command(args):
    return subprocess.check_output(['k3s', 'kubectl', '-n', 'traffic-demo', *args, '--request-timeout=10s'], text=True, timeout=15)

def check():
    d = json.loads(command(['get', 'deployment', 'traffic-coordinator', '-o', 'json']))
    h = hashlib.sha256(json.dumps(d['spec']['template'], sort_keys=True).encode()).hexdigest()
    if d['metadata']['uid'] != a.uid or h != a.template_sha:
        raise RuntimeError('deployment identity/template changed; manual restore required')
    return d['spec']['replicas']
if check() != 1:
    raise RuntimeError('traffic replicas must be 1 before arming')
if a.check_only:
    print('guard identity check passed')
    raise SystemExit(0)
stopping = False

def stop(*_):
    global stopping
    stopping = True
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
deadline = time.monotonic() + a.seconds
try:
    print(json.dumps({'state': 'armed', 'duration_seconds': a.seconds, 'previous_replicas': 0}), flush=True)
    while not stopping and time.monotonic() < deadline and (not pathlib.Path(a.stop_file).exists()):
        time.sleep(5)
finally:
    for attempt in range(18):
        try:
            if check() == 1:
                print(command(['scale', 'deployment/traffic-coordinator', '--replicas=0']), flush=True)
            if check() != 0:
                raise RuntimeError('traffic restoration not confirmed')
            print(json.dumps({'state': 'restored', 'replicas': 0}), flush=True)
            break
        except Exception as e:
            print(json.dumps({'restore_attempt': attempt + 1, 'error': str(e)}), flush=True)
            if attempt == 17:
                raise
            time.sleep(10)
