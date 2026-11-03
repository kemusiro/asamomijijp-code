#!/usr/bin/env python3
"""Piクラスタの相互SSHを段階適用し、エージェントなしで検証する。"""

import argparse
import concurrent.futures
import json
import pathlib
import shlex
import subprocess
import sys


REMOTE = r'''
import concurrent.futures, getpass, json, os, pathlib, re, shutil, socket, subprocess, sys
p = json.load(sys.stdin)
node = p['node']
home = pathlib.Path.home()
ssh = home / '.ssh'
assert socket.gethostname() == node['name'], '接続先ホスト名が不一致'
assert getpass.getuser() == node['user'], '接続先ユーザーが不一致'
assert pathlib.Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()[:2] == node['host_key'].split()[:2], 'ホスト公開鍵が不一致'
key = ssh / 'id_ed25519_exhibition_cluster'
managed = ['config', 'authorized_keys', 'exhibition_cluster.conf', 'known_hosts_exhibition_cluster']
def tokens(text):
    return re.findall(r'(?:^|\s)(ssh-ed25519|ssh-rsa)\s+([A-Za-z0-9+/=]+)', text, re.M)
def write(path, text):
    if path.exists() and path.read_text() == text:
        return
    tmp = path.with_name(path.name + '.exhibition-tmp')
    with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        f.write(text)
    tmp.replace(path)
    path.chmod(0o600)
def snapshot():
    backup = ssh / p['run_id']
    if not backup.exists():
        backup.mkdir(mode=0o700)
        existed = []
        for name in managed:
            path = ssh / name
            if path.exists():
                assert path.is_file() and not path.is_symlink(), '通常ファイル以外は変更しない: ' + name
                shutil.copy2(path, backup / name)
                (backup / name).chmod(0o600)
                existed.append(name)
        (backup / 'manifest.json').write_text(json.dumps({'existed': existed, 'key_existed': key.exists()}))
        (backup / 'manifest.json').chmod(0o600)
    return str(backup)
stage = p['stage']
if stage == 'prepare':
    assert not ssh.is_symlink(), '.sshのsymlinkは対象外'
    ssh.mkdir(mode=0o700, exist_ok=True)
    ssh.chmod(0o700)
    backup = snapshot()
    assert key.exists() == key.with_suffix('.pub').exists(), '鍵ペアが不完全。復旧手順で確認する'
    if not key.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'exhibition-cluster@' + node['name'], '-f', str(key)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
    public = subprocess.check_output(['ssh-keygen', '-y', '-P', '', '-f', str(key)], text=True, timeout=10).strip()
    assert public.split()[:2] == key.with_suffix('.pub').read_text().split()[:2], '鍵ペア不一致'
    key.chmod(0o600)
    key.with_suffix('.pub').chmod(0o644)
    print(json.dumps({'name': node['name'], 'public_key': key.with_suffix('.pub').read_text().strip(), 'backup': backup, 'ssh_version': subprocess.run(['ssh','-V'],capture_output=True,text=True).stderr.strip(), 'os': pathlib.Path('/etc/os-release').read_text().splitlines()}))
elif stage == 'apply':
    assert key.exists(), '先にprepareを実行する'
    backup = snapshot()
    for name in managed:
        path = ssh / name
        assert not path.is_symlink(), 'symlinkは変更しない: ' + name
    start = '# BEGIN exhibition-cluster-ssh'
    end = '# END exhibition-cluster-ssh'
    auth = ssh / 'authorized_keys'
    original = auth.read_text() if auth.exists() else ''
    assert original.count(start) == original.count(end) <= 1, '管理ブロックが不正'
    block = re.search(re.escape(start) + r'\n(.*?)' + re.escape(end), original, flags=re.S)
    previous_mac_keys = [line for line in block[1].splitlines() if line.startswith(('ssh-rsa ', 'ssh-ed25519 '))] if block else []
    retained = re.sub(re.escape(start) + r'\n.*?' + re.escape(end) + r'\n?', '', original, flags=re.S)
    existing = set(tokens(retained))
    additions = []
    for public in p['public_keys']:
        assert len(tokens(public)) == 1, '公開鍵が不正'
        if tokens(public)[0] not in existing:
            additions.append('from="192.168.2.0/24" ' + public)
            existing.add(tokens(public)[0])
    mac_keys = [p['mac_key'].strip()] + p['additional_mac_keys']
    for mac in previous_mac_keys + mac_keys:
        assert len(tokens(mac)) == 1 and mac.startswith(('ssh-rsa ', 'ssh-ed25519 ')), 'Mac公開鍵が不正'
        if tokens(mac)[0] not in existing:
            additions.append(mac)
            existing.add(tokens(mac)[0])
    updated = retained.rstrip('\n') + '\n' + start + '\n' + '\n'.join(additions) + '\n' + end + '\n'
    write(auth, updated)
    config = []
    for target in p['nodes']:
        names = [target['name'], target['name'] + '.mpi.test', target['ip']]
        if target['name'] == 'rpi5':
            names += ['pi5', 'pi5.mpi.test', 'rpi5.local']
        config += ['Host ' + ' '.join(names), '    HostName ' + target['ip'], '    User ' + target['user'], '    IdentityFile ~/.ssh/id_ed25519_exhibition_cluster', '    IdentitiesOnly yes', '    IdentityAgent none', '    ForwardAgent no', '    HostKeyAlias ' + target['ip'], '    UserKnownHostsFile ~/.ssh/known_hosts_exhibition_cluster', '    StrictHostKeyChecking yes', '    UpdateHostKeys no', '    ConnectTimeout 5', '    ServerAliveInterval 15', '    ServerAliveCountMax 2', '']
    config += ['Host *', '']
    write(ssh / 'exhibition_cluster.conf', '\n'.join(config))
    write(ssh / 'known_hosts_exhibition_cluster', ''.join(n['ip'] + ' ' + n['host_key'] + '\n' for n in p['nodes']))
    config_path = ssh / 'config'
    original_config = config_path.read_text() if config_path.exists() else ''
    include = 'Include ~/.ssh/exhibition_cluster.conf'
    retained_config = '\n'.join(line for line in original_config.splitlines() if line.strip() != include)
    write(config_path, include + '\n' + retained_config + ('\n' if retained_config else ''))
    for name in managed:
        (ssh / name).chmod(0o600)
    counts = [tokens(auth.read_text()).count(tokens(mac)[0]) for mac in mac_keys]
    assert all(count == 1 for count in counts), 'Mac公開鍵が重複または不在'
    print(json.dumps({'name': node['name'], 'backup': backup, 'mac_key_count': counts[0], 'additional_mac_key_counts': counts[1:], 'cluster_key_count': sum(k in tokens(auth.read_text()) for public in p['public_keys'] for k in tokens(public))}))
elif stage == 'verify':
    def check(item):
        target, method = item
        dest = target['ip'] if method == 'ip' else target['name']
        env = dict(os.environ)
        env.pop('SSH_AUTH_SOCK', None)
        args = ['ssh','-o','BatchMode=yes','-o','ConnectionAttempts=1','-o','ControlMaster=no','-o','ControlPath=none',dest,'hostname; id -un']
        try:
            result = subprocess.run(args,capture_output=True,text=True,timeout=12,env=env)
            ok = result.returncode == 0 and result.stdout.splitlines() == [target['name'], target['user']]
            return {'target':target['name'],'method':method,'ok':ok,'rc':result.returncode,'stdout':result.stdout.strip(),'stderr':result.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {'target':target['name'],'method':method,'ok':False,'error':'12秒タイムアウト'}
    pairs = [(n,method) for n in p['nodes'] if n['name'] != node['name'] for method in ['ip','name']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        checks = list(pool.map(check,pairs))
    mac = tokens(p['mac_key'])[0]
    mac_count = tokens((ssh / 'authorized_keys').read_text()).count(mac)
    additional_counts = [tokens((ssh / 'authorized_keys').read_text()).count(tokens(key)[0]) for key in p['additional_mac_keys']]
    print(json.dumps({'name':node['name'],'mac_key_count':mac_count,'additional_mac_key_counts':additional_counts,'checks':checks,'ok':all(c['ok'] for c in checks) and mac_count == 1 and all(c == 1 for c in additional_counts)}))
else:
    raise ValueError(stage)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True, type=pathlib.Path)
    parser.add_argument('--bootstrap-known-hosts', required=True, type=pathlib.Path)
    parser.add_argument('--mac-public-key', required=True, type=pathlib.Path)
    parser.add_argument('--additional-mac-public-key', action='append', default=[], type=pathlib.Path,
                        help='既存のMac公開鍵を保持して追加する公開鍵。複数回指定可能')
    parser.add_argument('--state-dir', required=True, type=pathlib.Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--stage', choices=['prepare', 'apply', 'verify'], required=True)
    parser.add_argument('--nodes', nargs='+', help='今回操作する接続元だけを指定する')
    args = parser.parse_args()
    if not args.run_id.startswith('exhibition-backup-') or '/' in args.run_id or '..' in args.run_id:
        parser.error('run-idはexhibition-backup-で始まる単一ディレクトリ名にする')
    nodes = json.loads(args.inventory.read_text())
    if len({n['name'] for n in nodes}) != len(nodes) or len({n['ip'] for n in nodes}) != len(nodes):
        parser.error('インベントリの名前またはIPが重複している')
    if len({tuple(n['host_key'].split()[:2]) for n in nodes}) != len(nodes):
        parser.error('機器間でホスト公開鍵が重複しているため照合する')
    selected = [n for n in nodes if not args.nodes or n['name'] in args.nodes]
    if not selected or (args.nodes and set(args.nodes) != {n['name'] for n in selected}):
        parser.error('nodesがインベントリに存在しない')
    args.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    mac_key = args.mac_public_key.read_text().strip()
    subprocess.run(['ssh-keygen', '-lf', str(args.mac_public_key)], check=True, capture_output=True)
    additional_mac_keys = []
    for path in args.additional_mac_public_key:
        subprocess.run(['ssh-keygen', '-lf', str(path)], check=True, capture_output=True)
        additional_mac_keys.append(path.read_text().strip())
    public_keys = []
    if args.stage != 'prepare':
        for node in nodes:
            public_keys.append(json.loads((args.state_dir / (node['name'] + '-prepare.json')).read_text())['public_key'])
        if len({tuple(key.split()[:2]) for key in public_keys}) != len(nodes):
            parser.error('機器間で専用公開鍵が重複しているため照合する')

    def execute(node):
        payload = dict(stage=args.stage, node=node, nodes=nodes, public_keys=public_keys,
                       mac_key=mac_key, additional_mac_keys=additional_mac_keys, run_id=args.run_id)
        # connect_ipは操作Macから到達するアドレス。クラスタ内のIPとは区別する。
        host = node.get('connect_ip', node['ip'])
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o', 'ConnectionAttempts=1',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no',
                   '-o', 'UserKnownHostsFile=' + str(args.bootstrap_known_hosts.resolve()),
                   node['user'] + '@' + host, 'python3 -c ' + shlex.quote(REMOTE)]
        try:
            result = subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True, timeout=200)
            if result.returncode:
                return dict(name=node['name'], ok=False, error=result.stderr.strip())
            data = json.loads(result.stdout)
            path = args.state_dir / (node['name'] + '-' + args.stage + '.json')
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            path.chmod(0o600)
            return dict(name=node['name'], ok=data.get('ok', True), checks=len(data.get('checks', [])))
        except (subprocess.TimeoutExpired, ValueError) as error:
            return dict(name=node['name'], ok=False, error=str(error))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, selected))
    for result in results:
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if all(r['ok'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
