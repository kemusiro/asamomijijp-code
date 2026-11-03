#!/usr/bin/env python3
"""既存runnerを停止した状態で、指定Picoだけを一時的な車体workerにする。"""
import argparse
import glob
import json
from pathlib import Path
import select
import shlex
import subprocess
import uuid
import time
import threading


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ssh-host', required=True)
    p.add_argument('--remote-root', required=True, help='vehicle code staged repository root on Pi 5')
    p.add_argument('--remote-output', required=True, help='new PNG path on Pi 5')
    p.add_argument('--port-glob', required=True)
    p.add_argument('--expected-nodes', required=True, help='comma separated exact node IDs')
    p.add_argument('--preset', choices=['recovery','preview','exhibition'], default='recovery')
    p.add_argument('--manager-port', type=int, default=8765)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    from mpremote.transport_serial import SerialTransport
    root = Path(__file__).resolve().parents[1]
    source = root/'projects/raspberry-pi-pico-cluster/raytracing/pico/vehicle_raytracer.py'
    ports = sorted(glob.glob(a.port_glob))
    expected = a.expected_nodes.split(',')
    if len(set(expected)) != len(expected) or len(ports) != len(expected):
        p.error('USB台数/期待node IDが一致しません')
    a.output_dir.mkdir(parents=True, exist_ok=False)
    module = 'vehicle_net_' + uuid.uuid4().hex[:8]
    records = []
    process = None
    open_boards = []
    readers = []
    worker_errors = []
    manager_pid = None

    def feed(board):
        board.exec('import machine; machine.WDT(timeout=8000).feed()')

    def safe_close(board):
        try: board.close()
        except OSError: pass

    def reset(board):
        # RP2350 may disconnect USB before raw-paste acknowledgement arrives.
        try:
            board.exec_raw_no_follow('import machine; machine.reset()')
        except OSError as exc:
            if exc.errno not in (6, 5, 19):
                raise

    def connect(port):
        deadline=time.monotonic()+15
        while True:
            try:
                return SerialTransport(port)
            except Exception:
                if time.monotonic() >= deadline: raise
                time.sleep(.25)

    def open_raw(port):
        from mpremote.transport import TransportError
        deadline=time.monotonic()+20
        while True:
            board=connect(port)
            try:
                board.enter_raw_repl(soft_reset=False)
                feed(board)
                return board
            except (OSError, TransportError):
                try: board.close()
                except OSError: pass
                if time.monotonic() >= deadline: raise
                time.sleep(.3)

    try:
        # Validate all identities before writing any device. Original main/core
        # hashes are recorded. Secrets in network_config are never read out.
        for port in ports:
            board = open_raw(port)
            try:
                node = board.exec('import network_config; print(network_config.NODE_ID)').decode().strip()
                hashes = {name:board.fs_hashfile(name,'sha256').hex() for name in ('main.py','raytracer_core.py','ray_worker.py')}
                records.append({'port':port,'nodeId':node,'before':hashes,'temporaryModule':module+'.py','installed':False})
                print('INVENTORY',node,flush=True)
            finally:
                safe_close(board)
        if {r['nodeId'] for r in records} != set(expected) or len({r['nodeId'] for r in records}) != len(records):
            raise RuntimeError('対象node ID集合が一致しません')
        command = ['python3','-u','-B',a.remote_root.rstrip('/')+'/projects/raspberry-pi-pico-cluster/raytracing/network/vehicle_manager.py',
                   '--preset',a.preset,'--workers',str(len(ports)),'--tile-size','8','--request-window','1',
                   '--port',str(a.manager_port),'--timeout','240','--worker-timeout','7',
                   '--output',a.remote_output,'--record-trace',str(Path(a.remote_output).with_suffix('.trace.json'))]
        process = subprocess.Popen(['ssh','-o','BatchMode=yes',a.ssh_host,shlex.join(command)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if not select.select([process.stdout],[],[],15)[0]:
            raise RuntimeError('managerのREADYがありません')
        ready = process.stdout.readline()
        if not ready.startswith('READY '):
            rest,error=process.communicate(timeout=10)
            (a.output_dir/'manager.log').write_text(ready+rest+error)
            raise RuntimeError('manager起動に失敗: '+error)
        manager_pid=json.loads(ready[6:]).get('pid')
        for record in records:
            board = open_raw(record['port'])
            try:
                node=board.exec('import network_config; print(network_config.NODE_ID)').decode().strip()
                if node != record['nodeId']: raise RuntimeError('stage node ID mismatch: '+node)
                record['installed'] = True
                board.fs_writefile(module+'.py',source.read_bytes()); feed(board)
                if board.fs_hashfile(module+'.py','sha256').hex() != __import__('hashlib').sha256(source.read_bytes()).hexdigest():
                    raise RuntimeError('一時コアの転送hash不一致')
                code = "import machine, sys\nwdt=machine.WDT(timeout=8000)\nwdt.feed()\nimport %s as vehicle\nsys.modules['raytracer_core']=vehicle\nimport network_config\nnetwork_config.MANAGER_PORT=%d\nimport ray_worker\nray_worker.core=vehicle\nimport gc\ngc.collect()\nwdt.feed()\nprint(ray_worker.core.ALGORITHM_VERSION)\n" % (module,a.manager_port)
                loaded=board.exec(code).decode().strip()
                if loaded != 'vehicle-extrusion-raytracer-v2':
                    raise RuntimeError('Pico core import mismatch: '+loaded)
                board.exec_raw_no_follow('ray_worker.run_once(watchdog=wdt,watchdog_timeout_ms=8000)')
                open_boards.append(board)
                def read_worker(b=board,r=record):
                    try:
                        with (a.output_dir/(r['nodeId']+'.stream.log')).open('ab',buffering=0) as stream:
                            stdout,stderr=b.follow(timeout=300,data_consumer=stream.write)
                        (a.output_dir/(r['nodeId']+'.log')).write_bytes(stdout+stderr)
                        if stderr:
                            worker_errors.append(r['nodeId'])
                            print('WORKER_ERROR',r['nodeId'],stderr.decode(),flush=True)
                    except Exception as exc:
                        (a.output_dir/(r['nodeId']+'.log')).write_text(str(exc))
                reader=threading.Thread(target=read_worker,daemon=True)
                reader.start();readers.append(reader)
                print('STARTED',record['nodeId'],flush=True)
            except BaseException:
                safe_close(board)
                raise
        deadline=time.monotonic()+300
        while True:
            if worker_errors:
                raise RuntimeError('worker error: '+','.join(worker_errors))
            try:
                output,error=process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline: raise
        (a.output_dir/'manager.log').write_text(ready+output+error)
        if process.returncode:
            raise RuntimeError('manager失敗: '+error)
        summaries=[json.loads(line)['data'] for line in output.splitlines() if line.startswith('{') and json.loads(line).get('type')=='summary']
        if len(summaries)!=1:
            raise RuntimeError('manager summaryがありません')
        summary=summaries[0]
        if summary.get('worker_timeouts') or summary.get('tiles_completed') != summary.get('total_tiles',summary.get('tiles_completed')):
            raise RuntimeError('worker timeout/タイル不足')
        (a.output_dir/'network-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        print('NETWORK_COMPLETE',summary['checksum32'],flush=True)
    finally:
        manager_cleanup_error = None
        if process is not None and process.poll() is None:
            try:
                if manager_pid is not None:
                    cleanup = "import os,pathlib,signal; p=pathlib.Path('/proc/%d/cmdline'); a=p.read_bytes().split(b'\\0') if p.exists() else []; expected=%r; os.kill(%d,signal.SIGTERM) if expected.encode() in a else None" % (manager_pid,a.remote_root.rstrip('/')+'/projects/raspberry-pi-pico-cluster/raytracing/network/vehicle_manager.py',manager_pid)
                    subprocess.run(['ssh','-o','BatchMode=yes',a.ssh_host,shlex.join(['python3','-c',cleanup])],timeout=15,check=True)
            except Exception as exc:
                manager_cleanup_error = str(exc)
            finally:
                process.terminate()
                try: process.communicate(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.communicate()
        for reader in readers: reader.join(timeout=1)
        for board in open_boards:
            safe_close(board)
        cleanup_errors=[]
        for record in records:
            board=None
            try:
                board=open_raw(record['port'])
                if record['installed']:
                    board.exec('import os; os.remove(%r)'%(module+'.py'))
                record['after']={name:board.fs_hashfile(name,'sha256').hex() for name in record['before']}
                if record['after'] != record['before']:
                    raise RuntimeError('元の展示ファイルのhash不一致')
                reset(board)
                record['restored']=True
                print('RESTORED',record['nodeId'],flush=True)
            except Exception as exc:
                record['cleanupError']=str(exc);cleanup_errors.append(record['nodeId'])
                if board is not None:
                    try: reset(board)
                    except Exception: pass
            finally:
                if board is not None:
                    safe_close(board)
        (a.output_dir/'devices.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        if manager_cleanup_error:
            (a.output_dir/'manager-cleanup-error.txt').write_text(manager_cleanup_error)
            cleanup_errors.append('remote manager')
        if cleanup_errors:
            raise RuntimeError('復旧の手動確認が必要: '+','.join(cleanup_errors))


if __name__=='__main__':
    main()
