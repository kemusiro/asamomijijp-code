"""更新順・破損転送の拒否・部分失敗時の原本復旧をUSBなしで検査する。"""
import ast
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT=Path(__file__).resolve().parents[4]/'scripts/manage-pico-scene-workers.py'
spec=importlib.util.spec_from_file_location('manage_scenes',SCRIPT);install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)


class Board:
    def __init__(self,node):
        self.node=node;self.files={'main.py':b'original-main','ray_worker.py':b'original-worker','raytracer_core.py':install.sources()['gallery_raytracer.py']}
        self.writes=[];self.fail=None;self.corrupt=False
    def exec(self,code):
        if 'network_config.NODE_ID' in code:return (self.node+'\n').encode()
        if 'os.rename(' in code:
            a,b=ast.literal_eval('('+code.split('os.rename(',1)[1].split(')',1)[0]+')');self.files[b]=self.files.pop(a)
        elif 'os.remove(' in code:self.files.pop(ast.literal_eval(code.split('os.remove(',1)[1].split(')',1)[0]))
        elif 'in os.listdir()' in code:
            name=ast.literal_eval(code.split('print(',1)[1].split(' in ',1)[0]);return str(name in self.files).encode()
        elif 'os.listdir()' in code:return repr(list(self.files)).encode()
        return b''
    def fs_hashfile(self,name,algorithm):return hashlib.sha256(self.files[name]).digest()
    def fs_readfile(self,name):return self.files[name]
    def fs_writefile(self,name,payload):
        if self.fail and self.fail in name:
            self.fail=None;raise OSError('injected USB failure')
        self.writes.append(name);self.files[name]=payload+(b'bad' if self.corrupt else b'')
    def exec_raw_no_follow(self,code):pass
    def close(self):pass


class InstallTests(unittest.TestCase):
    def test_reset_disconnect_closes_serial_without_masking_other_errors(self):
        board=mock.Mock()
        for number in (5,6,19):
            board.close.side_effect=OSError(number,'reset disconnect')
            install.close_board(board)
        self.assertEqual(board.serial.close.call_count,3)
        board.close.side_effect=OSError(13,'unexpected permission error')
        with self.assertRaises(OSError):install.close_board(board)

    def test_reset_accepts_wrapped_disconnect_but_rejects_other_errors(self):
        board=mock.Mock()
        wrapped=OSError('serial read failed');wrapped.__context__=OSError(6,'Device not configured')
        board.exec_raw_no_follow.side_effect=wrapped
        install.reset(board)
        wrapped.__context__=OSError(13,'Permission denied')
        with self.assertRaises(OSError):install.reset(board)

    def test_corrupt_transfer_never_replaces_active_core(self):
        board=Board('pico-01');old=board.files['raytracer_core.py'];board.corrupt=True
        with self.assertRaisesRegex(RuntimeError,'転送hash'):
            install.write_file(board,'raytracer_core.py',b'new-core')
        self.assertEqual(board.files['raytracer_core.py'],old)

    def test_failed_second_device_restores_every_touched_original(self):
        with tempfile.TemporaryDirectory() as directory:
            boards={'/fake/one':Board('pico-01'),'/fake/two':Board('pico-02')}
            original={p:dict(b.files) for p,b in boards.items()};boards['/fake/two'].fail='vehicle_raytracer'
            argv=['manage','install','--port-glob','/fake/*','--expected-nodes','pico-01,pico-02','--backup-dir',directory]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(install.glob,'glob',return_value=list(boards)),mock.patch.object(install,'open_board',side_effect=lambda p:boards[p]):
                with self.assertRaisesRegex(OSError,'USB failure'):install.main()
            for p,b in boards.items():
                for name,payload in original[p].items():self.assertEqual(b.files[name],payload)
                self.assertNotIn('gallery_raytracer.py',b.files);self.assertNotIn('vehicle_raytracer.py',b.files)
            import json
            records=json.loads((Path(directory)/'devices.json').read_text());self.assertTrue(all(r['restored'] for r in records))

    def test_successful_install_has_core_last_and_restores_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            board=Board('pico-01');original=dict(board.files)
            argv=['manage','install','--port-glob','/fake/*','--expected-nodes','pico-01','--backup-dir',directory]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(install.glob,'glob',return_value=['/fake/one']),mock.patch.object(install,'open_board',return_value=board):install.main()
            self.assertEqual(board.writes[-1],'raytracer_core.py.scene-update.tmp')
            self.assertEqual(board.files['main.py'],original['main.py']);self.assertEqual(board.files['ray_worker.py'],original['ray_worker.py'])
            argv[1]='restore'
            with mock.patch.object(sys,'argv',argv),mock.patch.object(install.glob,'glob',return_value=['/fake/one']),mock.patch.object(install,'open_board',return_value=board):install.main()
            self.assertEqual(board.files,original)

    def test_existing_scene_upgrade_restores_previous_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            board=Board('pico-01')
            previous={'gallery_raytracer.py':install.sources()['gallery_raytracer.py'],'vehicle_raytracer.py':b'previous-vehicle','raytracer_core.py':b'previous-router'}
            board.files.update(previous);original=dict(board.files)
            argv=['manage','install','--port-glob','/fake/*','--expected-nodes','pico-01','--backup-dir',directory,'--previous-revision','a'*40]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(install.glob,'glob',return_value=['/fake/one']),mock.patch.object(install,'open_board',return_value=board),mock.patch.object(install,'previous_sources',return_value=previous):install.main()
            self.assertNotEqual(board.files['vehicle_raytracer.py'],previous['vehicle_raytracer.py'])
            argv[1]='restore'
            later={**install.sources(),'vehicle_raytracer.py':b'later source edit'}
            with mock.patch.object(sys,'argv',argv),mock.patch.object(install.glob,'glob',return_value=['/fake/one']),mock.patch.object(install,'open_board',return_value=board),mock.patch.object(install,'previous_sources',return_value=previous),mock.patch.object(install,'sources',return_value=later):install.main()
            self.assertEqual(board.files,original)

    def test_unexpected_node_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            board=Board('pico-99')
            argv=['manage','install','--port-glob','/fake/*','--expected-nodes','pico-01','--backup-dir',directory]
            with mock.patch.object(sys,'argv',argv),mock.patch.object(install.glob,'glob',return_value=['/fake/one']),mock.patch.object(install,'open_board',return_value=board):
                with self.assertRaisesRegex(RuntimeError,'期待していない'):install.main()
            self.assertEqual(board.writes,[])


class PreviousSourceLayoutTests(unittest.TestCase):
    def test_previous_revision_uses_nested_project_path(self):
        # 公開リポジトリでは展示プロジェクトがprojects/配下に入る。
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            project = repo / 'projects/exhibition'
            pico = project / 'projects/raspberry-pi-pico-cluster/raytracing/pico'
            pico.mkdir(parents=True)
            expected = {'raytracer_core.py': b'gallery', 'vehicle_raytracer.py': b'vehicle', 'scene_raytracer.py': b'router'}
            for name, data in expected.items():
                (pico / name).write_bytes(data)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            with mock.patch.object(install, 'ROOT', project), mock.patch.object(install, 'PICO', pico):
                actual = install.previous_sources(revision)
            self.assertEqual(actual, {'gallery_raytracer.py': b'gallery', 'vehicle_raytracer.py': b'vehicle', 'raytracer_core.py': b'router'})


if __name__=='__main__':unittest.main()
