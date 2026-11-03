#!/usr/bin/env python3
"""指定Picoの描画コアだけを退避・更新・復旧する（mpremote 1.28.0）。"""
import argparse
import glob
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import re
import time

ROOT = Path(__file__).resolve().parents[1]
PICO = ROOT / 'projects/raspberry-pi-pico-cluster/raytracing/pico'
ORIGINALS = ('main.py', 'ray_worker.py', 'raytracer_core.py')
COMPANIONS = ('gallery_raytracer.py', 'vehicle_raytracer.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sources():
    return {'gallery_raytracer.py': (PICO/'raytracer_core.py').read_bytes(),
            'vehicle_raytracer.py': (PICO/'vehicle_raytracer.py').read_bytes(),
            'raytracer_core.py': (PICO/'scene_raytracer.py').read_bytes()}


def previous_sources(revision):
    if not re.fullmatch(r'[0-9a-f]{40}',revision):
        raise ValueError('更新元は確認済みcommitの40桁SHAを指定してください')
    git_root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True).strip())
    relative=PICO.resolve().relative_to(git_root.resolve()).as_posix()
    names={'gallery_raytracer.py':'raytracer_core.py','vehicle_raytracer.py':'vehicle_raytracer.py','raytracer_core.py':'scene_raytracer.py'}
    return {name:subprocess.check_output(['git','show',revision+':'+relative+'/'+source],cwd=ROOT) for name,source in names.items()}


def feed(board):
    board.exec('import machine; machine.WDT(timeout=8000).feed()')


def usb_disconnected(exc):
    # pyserialはOSの切断例外をerrnoなしのSerialExceptionで包む場合がある。
    seen=set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc,OSError) and exc.errno in (5,6,19):return True
        exc=exc.__cause__ or exc.__context__
    return False


def close_board(board):
    try:
        board.close()
    except OSError as exc:
        # machine.reset()に伴うUSB再列挙ではRTS/DTRの解除が失敗する。
        # OSのシリアルfdは必ず閉じる。無関係なエラーは隠さない。
        serial = getattr(board, 'serial', None)
        if serial is not None:
            serial.close()
        if not usb_disconnected(exc):
            raise


def open_board(port):
    from mpremote.transport_serial import SerialTransport
    last = None
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        board = None
        try:
            board = SerialTransport(port)
            board.enter_raw_repl(soft_reset=False, timeout_overall=3)
            feed(board)
            return board
        except Exception as exc:
            last = exc
            if board is not None:
                close_board(board)
            time.sleep(.5)
    raise RuntimeError('raw REPLへ接続できません: '+port+': '+str(last))


def reset(board):
    try:
        board.exec_raw_no_follow('import machine; machine.reset()')
    except OSError as exc:
        if not usb_disconnected(exc):
            raise


def hashfile(board, name):
    feed(board)
    return board.fs_hashfile(name, 'sha256').hex()


def identity(board):
    return board.exec('import network_config; print(network_config.NODE_ID)').decode().strip()


def write_file(board, name, payload):
    temporary = name+'.scene-update.tmp'
    feed(board)
    board.fs_writefile(temporary, payload)
    if hashfile(board, temporary) != digest(payload):
        raise RuntimeError('転送hash不一致: '+name)
    board.exec('import os; os.rename(%r,%r)' % (temporary, name))
    if hashfile(board, name) != digest(payload):
        raise RuntimeError('書換後hash不一致: '+name)


def restore_board(board, record, backup_dir, payloads):
    if identity(board) != record['nodeId']:
        raise RuntimeError('復旧対象node IDが不一致')
    installed=record.get('afterInstall',{})
    current = hashfile(board, 'raytracer_core.py')
    if current not in (record['before']['raytracer_core.py'], digest(payloads['raytracer_core.py']), installed.get('raytracer_core.py')):
        raise RuntimeError('復旧前のコアが想定外です。上書きしません')
    if record.get('previousFiles'):
        # 交互表示版の更新は、球体専用ではなく直前の3モジュールへ戻す。
        for name in (*COMPANIONS,'raytracer_core.py'):
            if hashfile(board,name) not in (record['before'][name],digest(payloads[name]),installed.get(name)):
                raise RuntimeError('復旧対象の追加コアが想定外: '+name)
            original=(backup_dir/record['nodeId']/name).read_bytes()
            if digest(original)!=record['before'][name]:raise RuntimeError('退避hash不一致: '+name)
            write_file(board,name,original)
        record['afterRestore']={name:hashfile(board,name) for name in (*ORIGINALS,*COMPANIONS)}
        if record['afterRestore']!=record['before']:raise RuntimeError('更新前への復旧hash不一致')
        record['restored']=True;reset(board);return
    original = (backup_dir/record['nodeId']/'raytracer_core.py').read_bytes()
    if digest(original) != record['before']['raytracer_core.py']:
        raise RuntimeError('退避ファイルのhash不一致')
    write_file(board, 'raytracer_core.py', original)
    for name in COMPANIONS:
        exists = board.exec('import os; print(%r in os.listdir())' % name).decode().strip() == 'True'
        if exists:
            if hashfile(board, name) not in (digest(payloads[name]),installed.get(name)):
                raise RuntimeError('復旧時の追加ファイルが想定外です: '+name)
            board.exec('import os; os.remove(%r)' % name)
    record['afterRestore'] = {name: hashfile(board, name) for name in ORIGINALS}
    if record['afterRestore'] != record['before']:
        raise RuntimeError('原本の復旧hash不一致')
    record['restored'] = True
    reset(board)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('install','restore'))
    p.add_argument('--port-glob', required=True)
    p.add_argument('--expected-nodes', required=True)
    p.add_argument('--backup-dir', type=Path, required=True)
    p.add_argument('--previous-revision', help='既存交互表示を更新する際の確認済み40桁commit SHA')
    a = p.parse_args()
    ports = sorted(glob.glob(a.port_glob));expected = a.expected_nodes.split(',')
    if not ports or len(ports)!=len(expected) or len(set(expected))!=len(expected) or any(not n.startswith('pico-') for n in expected):
        p.error('USB台数/期待node ID集合が不正です')
    a.backup_dir.mkdir(parents=True, exist_ok=True)
    state_path=a.backup_dir/'devices.json';payloads=sources()
    previous=previous_sources(a.previous_revision) if a.previous_revision else None
    records=json.loads(state_path.read_text()) if state_path.exists() else []
    def save():
        temp=state_path.with_suffix('.tmp');temp.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n');temp.replace(state_path)
    failures=[]
    if a.action=='install':
        # 全台のIDと原本hashを確認してから最初の書き込みへ進む。
        inventory=[]
        for port in ports:
            board=open_board(port)
            try:
                node=identity(board)
                if node not in expected:raise RuntimeError('期待していないnode IDです: '+node)
                before={name:hashfile(board,name) for name in ORIGINALS}
                old=next((r for r in records if r['nodeId']==node),None)
                if old is not None:
                    if before['raytracer_core.py'] not in (old['before']['raytracer_core.py'],digest(payloads['raytracer_core.py'])) or any(before[n]!=old['before'][n] for n in ('main.py','ray_worker.py')):
                        raise RuntimeError('再実行時の原本hashが一致しません: '+node)
                    record=old;record['port']=port
                    for name in COMPANIONS:
                        exists=board.exec('import os; print(%r in os.listdir())'%name).decode().strip()=='True'
                        if exists and hashfile(board,name) not in (digest(payloads[name]),old['before'].get(name,'')):raise RuntimeError('追加コアが想定外です: '+node+'/'+name)
                elif previous is not None:
                    before.update({name:hashfile(board,name) for name in COMPANIONS})
                    if any(before[name]!=digest(data) for name,data in previous.items()):
                        raise RuntimeError('更新元commitと実機コアが不一致: '+node)
                    target=a.backup_dir/node;target.mkdir(exist_ok=True)
                    for name,data in previous.items():
                        original=board.fs_readfile(name)
                        if digest(original)!=before[name]:raise RuntimeError('退避hash不一致: '+name)
                        (target/name).write_bytes(original)
                    record={'nodeId':node,'port':port,'before':before,'installed':False,'previousFiles':list(previous),'previousRevision':a.previous_revision}
                    records.append(record)
                else:
                    if before['raytracer_core.py']!=digest(payloads['gallery_raytracer.py']):
                        raise RuntimeError('未知の球体コアです: '+node)
                    names=board.exec('import os; print(os.listdir())').decode()
                    if any(name in names for name in COMPANIONS):
                        raise RuntimeError('既存の追加コアがあります。上書きしません: '+node)
                    target=a.backup_dir/node;target.mkdir(exist_ok=True)
                    original=board.fs_readfile('raytracer_core.py')
                    if digest(original)!=before['raytracer_core.py']:raise RuntimeError('退避hash不一致')
                    (target/'raytracer_core.py').write_bytes(original)
                    record={'nodeId':node,'port':port,'before':before,'installed':False}
                    records.append(record)
                record["firmware"] = board.exec("import sys; print(sys.implementation)").decode().strip()
                inventory.append(record);save();print('INVENTORY',node,flush=True)
            finally:
                reset(board);close_board(board)
        if {r['nodeId'] for r in inventory}!=set(expected) or len({r['nodeId'] for r in inventory})!=len(expected):
            raise RuntimeError('node ID集合が不一致です。書き込みません')
        try:
            for record in inventory:
                board=open_board(record['port'])
                try:
                    if identity(board)!=record['nodeId']:raise RuntimeError('書込対象のnode ID不一致')
                    record['writeStarted']=True;save()
                    for name in (*COMPANIONS,'raytracer_core.py'):write_file(board,name,payloads[name])
                    record['installed']=True;record['restored']=False
                    record['afterInstall']={name:hashfile(board,name) for name in (*ORIGINALS,*COMPANIONS)}
                    if any(record['afterInstall'][n]!=record['before'][n] for n in ('main.py','ray_worker.py')):raise RuntimeError('main/workerが変化しました')
                    save();reset(board);print('INSTALLED',record['nodeId'],flush=True)
                finally:close_board(board)
        except BaseException:
            # 途中失敗時も、書込開始済みの全対象を独立に復旧する。
            for record in inventory:
                if not record.get('writeStarted'):continue
                board=None
                try:
                    board=open_board(record['port']);restore_board(board,record,a.backup_dir,payloads);print('RESTORED',record['nodeId'],flush=True)
                except Exception as exc:record['restoreError']=str(exc);failures.append(record['nodeId'])
                finally:
                    if board is not None:close_board(board)
                    save()
            if failures:print('手動復旧が必要: '+','.join(failures),file=sys.stderr)
            raise
    else:
        if {r['nodeId'] for r in records}!=set(expected):raise RuntimeError('退避したnode ID集合と一致しません')
        # USBの番号が変わってもIDで対応を決める。1台失敗しても残りを復旧する。
        for port in ports:
            board=None
            try:
                board=open_board(port);node=identity(board);record=next(r for r in records if r['nodeId']==node)
                restore_board(board,record,a.backup_dir,payloads);print('RESTORED',node,flush=True)
            except Exception as exc:failures.append(port);print('RESTORE_ERROR',port,str(exc),file=sys.stderr,flush=True)
            finally:
                if board is not None:close_board(board)
                save()
        if failures:raise RuntimeError('復旧未完了: '+','.join(failures))
    save()


if __name__=='__main__':main()
