#!/usr/bin/env python3
import argparse, json, pathlib, shlex, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
p = argparse.ArgumentParser()
p.add_argument('--mng', required=True)
p.add_argument('--pico', required=True)
p.add_argument('--storage', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--stop-file', required=True)
p.add_argument('--output', required=True)
p.add_argument('--seconds', type=int, default=10800)
p.add_argument('--interval', type=int, default=60)
a = p.parse_args()
if a.seconds < 10800 or not 10 <= a.interval <= 75:
    p.error('3時間以上・採取間隔10〜75秒を指定してください')
if not pathlib.Path(a.probe).is_absolute() or not pathlib.Path(a.stop_file).is_absolute():
    p.error('probeとstop-fileは対象ホストの絶対パスが必要です')
r = pathlib.Path(a.output)
r.mkdir(exist_ok=False)

def ssh(host, command):
    return subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=6', host, command], text=True, timeout=22)

def get(host, role):
    try:
        return dict(ok=True, value=json.loads(ssh(host, 'sudo -n python3 -B ' + shlex.quote(a.probe) + ' ' + role)))
    except Exception as e:
        return dict(ok=False, error_type=type(e).__name__, error=str(e)[:500])

def evaluate(row, baseline=None):
    errors = []
    for role in ('local', 'pico', 'storage'):
        q = row[role]
        if not q['ok']:
            errors.append(role + ': SSH/probe failed')
            continue
        for k, v in q['value'].items():
            if not v['ok']:
                errors.append(role + ': ' + k + ' failed')
        d = q['value']
        if 'monitor' in d and d['monitor']['ok']:
            m = d['monitor']['value']
            if m['status'] != 'ok' or m['failures'] or (not 0 <= m['age_seconds'] < 75):
                errors.append(role + ': unhealthy/stale monitor')
            if baseline and baseline[role]['ok'] and (m['boot_id'] != baseline[role]['value']['monitor']['value']['boot_id']):
                errors.append(role + ': boot changed')
        if 'units' in d and d['units']['ok']:
            for u in d['units']['value']:
                if u['ActiveState'] != 'active' or u['NRestarts'] != '0':
                    errors.append(role + ': service abnormal ' + u['Id'])
            if baseline and baseline[role]['ok'] and (d['units']['value'] != baseline[role]['value']['units']['value']):
                errors.append(role + ': unit identity changed')
        if role == 'local':
            if d['traffic']['ok']:
                t = d['traffic']['value']
                e = t['exhibition']
                if t['ready'] != 12 or t['expected'] != 12 or t['errors'] or (e['status'] != 'running') or e['error']:
                    errors.append('traffic unhealthy')
            if d['vehicle']['ok'] and (not d['vehicle']['value']['running'] or d['vehicle']['value']['error']):
                errors.append('vehicle unhealthy')
            if d['workloads']['ok']:
                pods = d['workloads']['value']
                if len(pods) != 13 or any((p['phase'] != 'Running' or not p['ready'] or p['restarts'] for p in pods)):
                    errors.append('traffic pods abnormal')
                if baseline and baseline['local']['ok'] and ({p['uid'] for p in pods} != {p['uid'] for p in baseline['local']['value']['workloads']['value']}):
                    errors.append('traffic pods replaced')
        elif role == 'pico' and d['pico']['ok'] and (d['pico']['value']['mode'] in ('display_error', 'waiting_for_manual_recovery', 'recovering')):
            errors.append('pico abnormal')
        elif role == 'storage' and d['sessions']['ok'] and (d['sessions']['value'] != 12):
            errors.append('iSCSI sessions not 12')
    return errors
rows = []
baseline = None
start = None
try:
    while True:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {role: pool.submit(get, host, role) for role, host in [('local', a.mng), ('pico', a.pico), ('storage', a.storage)]}
            row = {k: f.result() for k, f in futures.items()}
        now = time.monotonic()
        if start is None:
            start = now
        row.update(at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=now - start)
        row['failures'] = evaluate(row, baseline)
        if baseline is None:
            baseline = row
        rows.append(row)
        with (r / 'samples.jsonl').open('a') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
        brief = dict(at=row['at'], elapsed_seconds=round(row['elapsed_seconds']), samples=len(rows), failures=row['failures'])
        for role, key, field in [('local', 'traffic', 'exhibition'), ('local', 'vehicle', 'evaluated'), ('pico', 'pico', 'cycle')]:
            try:
                brief[key] = row[role]['value'][key]['value'][field]
            except (KeyError, TypeError):
                pass
        if isinstance(brief.get('traffic'), dict):
            brief['traffic'] = {k: brief['traffic'][k] for k in ('cycle', 'phase', 'completedCandidates')}
        print(json.dumps(brief, ensure_ascii=False), flush=True)
        (r / 'latest.json').write_text(json.dumps(brief, ensure_ascii=False, indent=2) + '\n')
        if row['elapsed_seconds'] >= a.seconds:
            break
        time.sleep(max(0, start + min(a.seconds, len(rows) * a.interval) - time.monotonic()))
finally:
    try:
        ssh(a.mng, 'touch -- ' + shlex.quote(a.stop_file))
        restore = 'requested guard restoration'
    except Exception as e:
        restore = 'guard deadline remains active: ' + str(e)
    report = dict(samples=len(rows), elapsed_seconds=rows[-1]['elapsed_seconds'] if rows else 0, failed_samples=sum((bool(row['failures']) for row in rows)), restore=restore)
    report['passed'] = report['elapsed_seconds'] >= a.seconds and report['failed_samples'] == 0
    (r / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report), flush=True)
raise SystemExit(0 if report['passed'] else 1)
