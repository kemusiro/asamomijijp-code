#!/usr/bin/env python3
import argparse, json, pathlib, subprocess, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
p = argparse.ArgumentParser()
p.add_argument('role', choices=['local', 'pico', 'storage'])
p.add_argument('--traffic-url', default='http://127.0.0.1:30095')
p.add_argument('--vehicle-url', default='http://127.0.0.1:30096')
p.add_argument('--pico-url', default='http://127.0.0.1:8080')
a = p.parse_args()

def command(args, timeout=8):
    return subprocess.check_output(args, text=True, timeout=timeout)

def http(url):
    with urllib.request.urlopen(url, timeout=8) as r:
        body = r.read(2097153)
        if len(body) > 2097152:
            raise ValueError('response too large')
        return json.loads(body)

def monitor():
    d = json.loads(pathlib.Path('/var/lib/pi4-management-monitor/latest.json').read_text())
    d['age_seconds'] = time.monotonic() - d['monotonic_seconds']
    return d

def units(names):
    raw = command(['systemctl', 'show', *names, '-p', 'Id', '-p', 'MainPID', '-p', 'ActiveState', '-p', 'NRestarts', '-p', 'ExecMainStartTimestampMonotonic'])
    return [dict((l.split('=', 1) for l in b.splitlines() if '=' in l)) for b in raw.strip().split('\n\n')]

def traffic():
    d = http(a.traffic_url + '/api/dashboard')
    e = d['exhibition'] or {}
    return dict(expected=d['expectedWorkers'], ready=d['readyWorkers'], errors=d['errors'], exhibition={k: e.get(k) for k in ('cycle', 'phase', 'status', 'error', 'updatedAt', 'completedCandidates', 'single', 'distributed', 'validation')})

def vehicle():
    d = http(a.vehicle_url + '/api/state')
    return dict(running=d['running'], error=d['error'], evaluated=d['ranking']['evaluated'], generation=d['generation'], experiment=d['comparison']['id'])

def workloads():
    d = json.loads(command(['k3s', 'kubectl', '-n', 'traffic-demo', 'get', 'pods', '-o', 'json', '--request-timeout=5s']))
    return [dict(name=n['metadata']['name'], uid=n['metadata']['uid'], node=n['spec']['nodeName'], phase=n['status']['phase'], ready=all((c['ready'] for c in n['status'].get('containerStatuses', []))), restarts=sum((c['restartCount'] for c in n['status'].get('containerStatuses', [])))) for n in d['items']]

def pico():
    d = http(a.pico_url + '/api/state')
    return {k: d.get(k) for k in ('mode', 'cycle', 'job_id', 'completed_tiles', 'total_tiles', 'updated_at', 'expected_workers', 'ready_node_ids')}

def run(fn):
    try:
        return dict(ok=True, value=fn())
    except Exception as e:
        return dict(ok=False, error_type=type(e).__name__, error=str(e)[:500])
if a.role == 'storage':
    probes = {'sessions': lambda: sum((l.startswith('alias:') for l in command(['targetcli', 'sessions', 'list']).splitlines()))}
elif a.role == 'local':
    probes = {'monitor': monitor, 'units': lambda: units(['ssh', 'k3s']), 'traffic': traffic, 'vehicle': vehicle, 'workloads': workloads}
else:
    probes = {'monitor': monitor, 'units': lambda: units(['pico-raytracing-runner', 'pico-raytracing-display']), 'pico': pico}
with ThreadPoolExecutor(max_workers=len(probes)) as pool:
    pending = {k: pool.submit(run, fn) for k, fn in probes.items()}
    result = {k: f.result() for k, f in pending.items()}
print(json.dumps(result, ensure_ascii=False))
