#!/usr/bin/env python3
"""現地MacからPi 4クラスタとPi 5を依存順に正常停止する（既定は計画表示のみ）。"""

import argparse
import base64
import datetime
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import uuid


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / 'projects/raspberry-pi-4-cluster/shutdown-hosts.example.json'
MUTATIONS = {'stop_pico', 'scale', 'labels', 'poweroff'}
REMOTE = r'''
import json,os,pathlib,re,shutil,socket,subprocess,sys
p=json.load(sys.stdin); h=p['host']; action=p['action']
def run(argv):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=45)
    if r.returncode: raise RuntimeError(' '.join(argv[:5])+': '+r.stderr.strip())
    return r.stdout
if socket.gethostname()!=h['name']: raise RuntimeError('ホスト名不一致')
if os.environ.get('SUDO_USER')!=h['user']: raise RuntimeError('ログインユーザー不一致')
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
if p.get('boot_id') and boot!=p['boot_id']: raise RuntimeError('確認後にOSが再起動されている')
model=pathlib.Path('/proc/device-tree/model').read_text().strip('\x00\n')
if not model.startswith(h['model_prefix']): raise RuntimeError('機種不一致: '+model)
def sessions():
    from rtslib_fb import RTSRoot
    return [{'alias':s['alias'],'state':s['state'],'addresses':[c['address'] for c in s['connections']]} for s in RTSRoot().sessions]
def kube(*args):
    return run(['k3s','kubectl','--request-timeout=10s',*args])
def resource(w,kind,name):
    return json.loads(kube('-n',w['namespace'],'get',kind,name,'-o','json'))
def apps():
    result=[]
    for w in p['config']['workloads']:
        dep=resource(w,'deployment',w['coordinator'])
        ds=resource(w,'daemonset',w['worker'])
        counts={}
        for name,obj in [('coordinator',dep),('worker',ds)]:
            selector=','.join(k+'='+v for k,v in sorted(obj['spec']['selector']['matchLabels'].items()))
            pods=json.loads(kube('-n',w['namespace'],'get','pods','-l',selector,'-o','json'))
            counts[name+'_pods']=len(pods['items'])
        result.append(dict(w,replicas=dep['spec'].get('replicas',1),**counts))
    nodes=json.loads(kube('get','nodes','-o','json'))
    return {'workloads':result,'labels':{n['metadata']['name']:{w['label']:n['metadata'].get('labels',{}).get(w['label']) for w in p['config']['workloads']} for n in nodes['items']}}
def mounts():
    rows={}
    for path in pathlib.Path('/proc').glob('[0-9]*/mountinfo'):
        try: text=path.read_text()
        except (FileNotFoundError,ProcessLookupError): continue
        for line in text.splitlines():
            left,right=line.split(' - ',1)
            if right.split()[0] in ['nfs','nfs4']:
                target,source=left.split()[4],right.split()[1]
                rows[(source,target)]={'target':target,'source':source,'pid':path.parent.name}
    return list(rows.values())
if action=='probe':
    for binary in ['systemctl','systemd-run']:
        if not shutil.which(binary): raise RuntimeError(binary+'がない')
    result={'boot_id':boot,'model':model,'python':sys.version.split()[0]}
elif action=='inspect':
    if h['role']=='management': result=apps()
    elif h['role']=='storage': result={'sessions':sessions()}
    elif h['role']=='gateway':
        result={'services':{unit:run(['systemctl','show',unit,'-p','LoadState','-p','ActiveState']).strip() for unit in p['config']['pico_services']}}
        if any('LoadState=loaded' not in value for value in result['services'].values()): raise RuntimeError('Picoサービスが未導入')
    else: result={}
elif action=='nfs': result={'mounts':mounts()}
elif action=='stop_pico':
    for unit in p['config']['pico_services']: run(['systemctl','stop',unit])
    states=[run(['systemctl','show',unit,'-p','ActiveState','--value']).strip() for unit in p['config']['pico_services']]
    if any(s not in ['inactive','failed'] for s in states): raise RuntimeError('Picoサービスが停止していない')
    result={'states':states}
elif action=='scale':
    for w in p['config']['workloads']: kube('-n',w['namespace'],'scale','deployment/'+w['coordinator'],'--replicas=0')
    result={'scaled_to':0}
elif action=='labels':
    current=apps()['labels']
    for n in p['config']['hosts']:
        if n['role']=='compute':
            for w in p['config']['workloads']:
                if current.get(n['name'],{}).get(w['label']) is not None: kube('label','node',n['name'],w['label']+'-')
    result={'labels_removed':True}
elif action=='poweroff':
    if h['role']=='storage' and sessions(): raise RuntimeError('iSCSI利用中のためstorage停止を拒否')
    unit=p['unit']
    if not re.fullmatch(r'exhibition-stop-[a-f0-9]+-[a-z0-9-]+',unit): raise RuntimeError('停止unit名が不正')
    run(['systemd-run','--quiet','--unit='+unit,'--on-active=5s','--timer-property=AccuracySec=1s',shutil.which('systemctl'),'poweroff'])
    result={'scheduled':unit}
else: raise RuntimeError('未定義の操作')
print(json.dumps(result))
'''


class StopError(RuntimeError):
    pass


def load_config(path):
    cfg = json.loads(path.read_text())
    hosts = cfg['hosts']
    for field in ['name', 'address']:
        if len({h[field] for h in hosts}) != len(hosts):
            raise StopError(field + 'が重複しています')
    for role in ['management', 'storage', 'gateway']:
        if sum(h['role'] == role for h in hosts) != 1:
            raise StopError(role + 'は1台を指定してください')
    if sum(h['role'] == 'compute' for h in hosts) != cfg['expected_compute_count']:
        raise StopError('計算ノードの台数が設定と一致しません')
    for h in hosts:
        ipaddress.IPv4Address(h['address'])
        if h['role'] not in ['management', 'storage', 'gateway', 'compute']:
            raise StopError('未定義の役割')
        if not re.fullmatch(r'[a-z][a-z0-9-]*', h['name']) or not re.fullmatch(r'[a-z_][a-z0-9_-]*', h['user']):
            raise StopError('ホスト名またはユーザーが不正です')
        if not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}', h['host_key_sha256']) or not h['model_prefix']:
            raise StopError('機種またはホスト鍵の指紋が不正です')
    for w in cfg['workloads']:
        if any(not re.fullmatch(r'[a-z0-9./-]+', v) for v in w.values()):
            raise StopError('展示リソース名が不正です')
    if not cfg['workloads'] or not cfg['pico_services']:
        raise StopError('停止対象の展示リソースとPicoサービスを指定してください')
    if any(not re.fullmatch(r'[a-z0-9-]+\.service', unit) for unit in cfg['pico_services']):
        raise StopError('Picoサービス名が不正です')
    return cfg


def fingerprint(blob):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(base64.b64decode(blob, validate=True)).digest()).decode().rstrip('=')


class SSH:
    def __init__(self, cfg, directory, execute=False, identity=None):
        self.cfg, self.execute, self.identity = cfg, execute, identity
        self.known_hosts = Path(directory) / 'known_hosts'
        self.boots = {}

    def pin(self, host):
        r = subprocess.run(['ssh-keyscan', '-T', '5', '-t', 'ed25519', host['address']], capture_output=True, text=True, timeout=10)
        keys = []
        for line in r.stdout.splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[1] == 'ssh-ed25519' and fingerprint(fields[2]) == host['host_key_sha256']:
                keys.append(host['address'] + ' ' + ' '.join(fields[1:]))
        if not keys:
            raise StopError(host['name'] + ': 照合済みホスト鍵が取得できません。LANと接続先を確認してください')
        with self.known_hosts.open('a') as stream:
            stream.write(keys[0] + '\n')
        self.known_hosts.chmod(0o600)

    def action(self, host, action, **extra):
        if action in MUTATIONS and not self.execute:
            raise StopError('確認モードで変更操作を拒否しました')
        payload = dict(host=host, config=self.cfg, action=action, boot_id=self.boots.get(host['name']), **extra)
        argv = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlgorithms=ssh-ed25519',
                '-o', 'UserKnownHostsFile=' + str(self.known_hosts), '-o', 'GlobalKnownHostsFile=/dev/null',
                '-o', 'HostKeyAlias=' + host['address'], '-o', 'HostName=' + host['address'],
                '-o', 'UpdateHostKeys=no', '-o', 'ForwardAgent=no', '-o', 'ClearAllForwardings=yes',
                '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none']
        if self.identity:
            argv += ['-o', 'IdentitiesOnly=yes', '-i', str(self.identity)]
        argv += [host['user'] + '@' + host['address'], 'sudo -n python3 -c ' + shlex.quote(REMOTE)]
        try:
            r = subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True, timeout=110)
        except subprocess.TimeoutExpired as error:
            raise StopError(host['name'] + ': SSH操作が時間切れです。再送せず記録を確認してください') from error
        if r.returncode:
            raise StopError(host['name'] + ': ' + r.stderr.strip())
        try:
            return json.loads(r.stdout)
        except ValueError as error:
            raise StopError(host['name'] + ': 正常な操作応答がありません') from error

    def online(self, host):
        try:
            with socket.create_connection((host['address'], 22), timeout=1):
                return True
        except OSError as error:
            if error.errno in [50, 51, 100, 101]:
                raise StopError('MacのLANが利用できません。後続の停止は行いません') from error
            return False


class Shutdown:
    def __init__(self, cfg, ssh, state, save, log, timeout=180, quiet=10):
        self.cfg, self.ssh, self.state = cfg, ssh, state
        self.save, self.log, self.timeout, self.quiet = save, log, timeout, quiet
        self.hosts = {h['name']: h for h in cfg['hosts']}
        self.roles = {r: next(h for h in cfg['hosts'] if h['role'] == r) for r in ['management', 'storage', 'gateway']}

    def call(self, host, action, **extra):
        self.log(host['name'] + ': ' + action)
        return self.ssh.action(host, action, **extra)

    def preflight(self):
        for host in self.cfg['hosts']:
            name = host['name']
            stopped = self.state['requests'].get(name)
            if stopped and stopped.get('uncertain'):
                raise StopError(name + ': 停止要求の受付が不明です。現物と記録を確認してください')
            if stopped and not self.ssh.online(host):
                continue
            if stopped and stopped.get('offline'):
                raise StopError(name + ': 停止後に再びオンラインです。古い記録で停止を続行しません')
            self.ssh.pin(host)
            probe = self.call(host, 'probe')
            old = self.state['probes'].get(name)
            if old and probe['boot_id'] != old['boot_id']:
                raise StopError(name + ': 記録後に再起動されています。古い記録を再利用しません')
            self.state['probes'][name] = probe
            self.ssh.boots[name] = probe['boot_id']
        if self.roles['management']['name'] not in self.state['requests']:
            apps = self.call(self.roles['management'], 'inspect')
            for phase, field in [('coordinators', 'coordinator_pods'), ('workers', 'worker_pods')]:
                if phase in self.state['done'] and any(w[field] for w in apps['workloads']):
                    raise StopError('停止済みの展示処理が再開されています。記録を確認してください')
            self.state.setdefault('apps', apps)
            self.state['management_nfs'] = self.call(self.roles['management'], 'nfs')['mounts']
            if self.state['management_nfs']:
                raise StopError('mngにNFS利用が残っています。各プロセスのmount namespaceを確認し、通常のアンマウントを行ってください')
        if self.roles['storage']['name'] not in self.state['requests']:
            sessions = self.call(self.roles['storage'], 'inspect')['sessions']
            allowed = {h['address'] for h in self.cfg['hosts'] if h['role'] == 'compute'}
            if any(ip not in allowed for s in sessions for ip in s['addresses']):
                raise StopError('一覧外のiSCSIクライアントがいます。storageを停止できません')
            self.state['initial_iscsi_sessions'] = len(sessions)
        if self.roles['gateway']['name'] not in self.state['requests']:
            pico = self.call(self.roles['gateway'], 'inspect')
            if 'pico' in self.state['done'] and any('ActiveState=active' in value for value in pico['services'].values()):
                raise StopError('停止済みのPicoサービスが再開されています。記録を確認してください')
            self.state.setdefault('pico', pico)
        self.save()

    def wait_for(self, description, predicate):
        deadline = time.monotonic() + self.timeout
        while True:
            if predicate():
                return
            if time.monotonic() >= deadline:
                raise StopError(description + ': 時間切れ。基盤への給電を維持して記録を確認してください')
            time.sleep(2)

    def poweroff(self, host):
        name = host['name']
        if name not in self.state['requests']:
            unit = 'exhibition-stop-' + self.state['run_id'] + '-' + name
            self.state['requests'][name] = {'unit': unit, 'uncertain': True}
            self.save()
            result = self.call(host, 'poweroff', unit=unit)
            if result.get('scheduled') != unit:
                raise StopError(name + ': 停止予約の受付を確認できません')
            self.state['requests'][name]['uncertain'] = False
            self.save()
        gone_since = None
        def gone():
            nonlocal gone_since
            for role in ['management', 'storage', 'gateway']:
                guard = self.roles[role]
                if guard['name'] != name and guard['name'] not in self.state['requests'] and not self.ssh.online(guard):
                    raise StopError(guard['name'] + ': 基盤との通信が失われました。後続を停止しません')
            if self.ssh.online(host):
                gone_since = None
                return False
            gone_since = gone_since if gone_since is not None else time.monotonic()
            return time.monotonic() - gone_since >= self.quiet
        self.wait_for(name + 'のSSH終了待ち', gone)
        self.state['requests'][name]['offline'] = True
        self.save()
        self.log(name + ': 停止要求受付・SSH無応答を確認（給電断は現物確認後）')

    def phase(self, name, work):
        if name not in self.state['done']:
            work()
            self.state['done'].append(name)
            self.save()

    def run(self):
        mng, storage, pi5 = (self.roles[r] for r in ['management', 'storage', 'gateway'])
        self.phase('pico', lambda: self.call(pi5, 'stop_pico'))
        def coordinators():
            self.call(mng, 'scale')
            self.wait_for('coordinator終了待ち', lambda: all(w['coordinator_pods'] == 0 for w in self.call(mng, 'inspect')['workloads']))
        self.phase('coordinators', coordinators)
        def workers():
            self.call(mng, 'labels')
            self.wait_for('展示worker終了待ち', lambda: all(w['worker_pods'] == 0 for w in self.call(mng, 'inspect')['workloads']))
        self.phase('workers', workers)
        def computes():
            for host in self.cfg['hosts']:
                if host['role'] == 'compute':
                    self.poweroff(host)
        self.phase('computes', computes)
        def stop_storage():
            self.wait_for('iSCSI切断待ち', lambda: not self.call(storage, 'inspect')['sessions'])
            self.state['management_nfs'] = self.call(mng, 'nfs')['mounts']
            self.save()
            if self.state['management_nfs']:
                raise StopError('mngにNFSマウントが残っています。storageは停止しません。利用プロセスと通常アンマウントを確認してください')
            self.poweroff(storage)
        self.phase('storage', stop_storage)
        self.phase('management', lambda: self.poweroff(mng))
        self.phase('gateway', lambda: self.poweroff(pi5))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='計画表示だけ。SSH接続もしない（既定）')
    mode.add_argument('--check', action='store_true', help='実機の認証・権限・構成を読み取り確認する')
    mode.add_argument('--execute', action='store_true', help='確認後に正常停止を実行する')
    parser.add_argument('--identity', type=Path, help='MacのSSH鍵を明示選択する場合だけ指定')
    parser.add_argument('--log-dir', type=Path, default=Path.home() / '.local/state/cho-eleki-expo/shutdown')
    parser.add_argument('--resume', type=Path, help='同じ停止作業のstate.jsonから再開する（--execute併用）')
    parser.add_argument('--yes', action='store_true', help='実行時の入力確認を省く（--execute併用）')
    parser.add_argument('--timeout', type=int, default=180, help='各待機の上限秒、既定180')
    args = parser.parse_args()
    if (args.resume or args.yes) and not args.execute:
        parser.error('--resume/--yesは--executeとの併用が必要です')
    if args.timeout < 30:
        parser.error('--timeoutは30秒以上にしてください')
    cfg = load_config(args.config)
    print('停止順: Picoサービス → 車体・交通coordinator/worker → 計算ノード → storage → mng → Pi 5')
    for host in cfg['hosts']:
        print('  {role}: {name} ({user}@{address})'.format(**host))
    if not args.check and not args.execute:
        print('計画表示のみ。実機確認は --check、実際の停止は --execute を指定してください。')
        return 0
    digest = hashlib.sha256(args.config.read_bytes()).hexdigest()
    folder = args.resume.resolve().parent if args.resume else args.log_dir.expanduser() / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    state_path = args.resume.resolve() if args.resume else folder / 'state.json'
    state = json.loads(state_path.read_text()) if args.resume else dict(run_id=uuid.uuid4().hex[:12], config_sha256=digest, requests={}, probes={}, done=[])
    if state['config_sha256'] != digest:
        raise StopError('保存記録と設定が一致しません')
    def save():
        tmp = state_path.with_name(state_path.name + '.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        tmp.replace(state_path)
    def log(message):
        print(message, flush=True)
        fd = os.open(folder / 'events.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'a') as stream:
            stream.write(json.dumps({'time':datetime.datetime.now().astimezone().isoformat(), 'message':message}, ensure_ascii=False) + '\n')
    print('作業記録: ' + str(state_path))
    lock_path = folder.parent / '.shutdown.lock'
    lock_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with lock_path.open('a') as lock, tempfile.TemporaryDirectory(prefix='exhibition-shutdown-') as temp:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StopError('別の停止スクリプトが動作中です') from error
        ssh = SSH(cfg, temp, execute=args.execute, identity=args.identity)
        control = Shutdown(cfg, ssh, state, save, log, timeout=args.timeout)
        try:
            save()
            control.preflight()
            if args.check:
                log('事前確認成功。実機の設定・サービス・電源を変更していません。')
                return 0
            if not args.yes and input('全15台を停止します。続行する場合は SHUTDOWN と入力: ') != 'SHUTDOWN':
                log('中止しました。停止操作は行っていません。')
                return 1
            control.run()
            log('全対象の停止要求受付とSSH終了待ちが完了しました。ACT LED・画面・リンクを現物確認してから給電を切ってください。')
        except (StopError, KeyboardInterrupt) as error:
            save()
            log('中断: ' + (str(error) or 'Ctrl+C'))
            log('基盤の給電を維持してください。予約済みの停止は取消されません。再開: --execute --resume ' + str(state_path))
            return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (StopError, OSError, ValueError, KeyError, TypeError, EOFError, subprocess.SubprocessError) as error:
        print('エラー: ' + str(error), file=sys.stderr)
        sys.exit(1)
