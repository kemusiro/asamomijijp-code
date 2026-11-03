#!/usr/bin/env python3
"""実機操作を行わず、依存順・失敗時の停止・再開時の誤操作防止を検証する。"""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('shutdown', Path(__file__).with_name('shutdown-exhibition.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CONFIG = mod.load_config(mod.DEFAULT_CONFIG)


class FakeSSH:
    def __init__(self):
        self.boots, self.off, self.calls = {}, set(), []
        self.coordinators, self.workers, self.pico = 1, 12, True
        self.stuck_iscsi, self.nfs, self.fail_node = False, [], None

    def pin(self, host):
        pass

    def online(self, host):
        return host['name'] not in self.off

    def action(self, host, action, **extra):
        name = host['name']
        self.calls.append((name, action))
        if action == 'probe':
            return {'boot_id': 'boot-' + name, 'model': host['model_prefix']}
        if action == 'nfs':
            return {'mounts': self.nfs}
        if action == 'inspect':
            if host['role'] == 'management':
                return {'workloads': [{'coordinator_pods': self.coordinators, 'worker_pods': self.workers}], 'labels': {}}
            if host['role'] == 'storage':
                clients = [h for h in CONFIG['hosts'] if h['role'] == 'compute' and (h['name'] not in self.off or self.stuck_iscsi)]
                return {'sessions': [{'addresses': [h['address']]} for h in clients]}
            return {'services': {'runner': 'LoadState=loaded\nActiveState=' + ('active' if self.pico else 'inactive')}}
        if action == 'stop_pico':
            self.pico = False
        elif action == 'scale':
            self.coordinators = 0
        elif action == 'labels':
            self.workers = 0
        elif action == 'poweroff':
            if name == self.fail_node:
                raise mod.StopError('受付応答が不明')
            self.off.add(name)
            return {'scheduled': extra['unit']}
        return {}


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.ssh = FakeSSH()
        self.state = dict(run_id='abc123', requests={}, probes={}, done=[])
        self.control = mod.Shutdown(CONFIG, self.ssh, self.state, lambda: None, lambda message: None, timeout=0, quiet=0)

    def test_default_is_offline_plan(self):
        with patch.object(mod.sys, 'argv', ['shutdown-exhibition.py']), patch.object(subprocess, 'run', side_effect=AssertionError('SSHを実行した')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mod.main(), 0)

    def test_check_transport_rejects_every_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            ssh = mod.SSH(CONFIG, folder, execute=False)
            for action in mod.MUTATIONS:
                with self.assertRaises(mod.StopError):
                    ssh.action(CONFIG['hosts'][0], action)

    def test_preflight_has_no_mutations(self):
        self.control.preflight()
        self.assertFalse(any(action in mod.MUTATIONS for _, action in self.ssh.calls))
        self.assertEqual(len(self.state['probes']), 15)

    def test_dependency_order(self):
        self.control.preflight()
        self.control.run()
        off = [name for name, action in self.ssh.calls if action == 'poweroff']
        self.assertEqual(off, ['node' + str(i) for i in range(10, 22)] + ['storage', 'mng', 'rpi5'])
        self.assertLess(self.ssh.calls.index(('rpi5', 'stop_pico')), self.ssh.calls.index(('mng', 'scale')))
        self.assertLess(self.ssh.calls.index(('mng', 'labels')), self.ssh.calls.index(('node10', 'poweroff')))
        self.assertTrue(all(r['offline'] and not r['uncertain'] for r in self.state['requests'].values()))

    def test_remaining_iscsi_keeps_all_providers_on(self):
        self.ssh.stuck_iscsi = True
        with self.assertRaises(mod.StopError):
            self.control.run()
        self.assertTrue({'storage', 'mng', 'rpi5'}.isdisjoint(self.ssh.off))

    def test_management_nfs_blocks_storage(self):
        self.ssh.nfs = [{'source': 'storage:/share', 'target': '/share'}]
        with self.assertRaises(mod.StopError):
            self.control.run()
        self.assertNotIn('storage', self.ssh.off)
        self.assertNotIn('mng', self.ssh.off)

    def test_management_nfs_also_blocks_preflight(self):
        self.ssh.nfs = [{'source': 'storage:/share', 'target': '/private', 'pid': '123'}]
        with self.assertRaises(mod.StopError):
            self.control.preflight()
        self.assertFalse(any(action in mod.MUTATIONS for _, action in self.ssh.calls))

    def test_unknown_iscsi_client_blocks_preflight(self):
        original = self.ssh.action
        def extra_client(host, action, **extra):
            result = original(host, action, **extra)
            if host['role'] == 'storage' and action == 'inspect':
                result['sessions'].append({'addresses': ['192.0.2.99']})
            return result
        self.ssh.action = extra_client
        with self.assertRaises(mod.StopError):
            self.control.preflight()
        self.assertFalse(any(action in mod.MUTATIONS for _, action in self.ssh.calls))

    def test_disconnect_must_be_continuous(self):
        self.control.quiet, self.control.timeout = 3, 30
        host = next(h for h in CONFIG['hosts'] if h['name'] == 'node10')
        sequence = iter([False, True, False, False, False, False])
        count = []
        original = self.ssh.online
        def connection(h):
            if h['name'] == 'node10':
                count.append(1)
                return next(sequence, False)
            return original(h)
        self.ssh.online = connection
        now = [0]
        def advance(seconds):
            now[0] += seconds
        with patch.object(mod.time, 'monotonic', side_effect=lambda: now[0]), patch.object(mod.time, 'sleep', side_effect=advance):
            self.control.poweroff(host)
        self.assertGreaterEqual(len(count), 5)

    def test_failed_compute_request_stops_sequence(self):
        self.ssh.fail_node = 'node11'
        with self.assertRaises(mod.StopError):
            self.control.run()
        self.assertEqual(self.ssh.off, {'node10'})
        self.assertTrue(self.state['requests']['node11']['uncertain'])
        with self.assertRaises(mod.StopError):
            self.control.preflight()

    def test_resume_does_not_resend_accepted_request(self):
        self.control.preflight()
        self.control.poweroff(next(h for h in CONFIG['hosts'] if h['name'] == 'node10'))
        self.control.preflight()
        self.control.run()
        self.assertEqual(self.ssh.calls.count(('node10', 'poweroff')), 1)

    def test_reappeared_shutdown_host_blocks_resume(self):
        self.control.preflight()
        host = next(h for h in CONFIG['hosts'] if h['name'] == 'node10')
        self.control.poweroff(host)
        self.ssh.off.remove('node10')
        with self.assertRaises(mod.StopError):
            self.control.preflight()

    def test_changed_boot_id_blocks_resume(self):
        self.state['probes']['node10'] = {'boot_id': 'old-boot'}
        with self.assertRaises(mod.StopError):
            self.control.preflight()
        self.assertFalse(any(action in mod.MUTATIONS for _, action in self.ssh.calls))

    def test_restarted_pico_blocks_resume(self):
        self.state['done'] = ['pico']
        with self.assertRaises(mod.StopError):
            self.control.preflight()

    def test_initial_app_snapshot_is_retained(self):
        initial = {'workloads': [{'replicas': 1}], 'labels': {'saved': {}}}
        self.state['apps'] = copy.deepcopy(initial)
        self.control.preflight()
        self.assertEqual(self.state['apps'], initial)

    def test_wrong_host_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            ssh = mod.SSH(CONFIG, folder)
            reply = subprocess.CompletedProcess([], 0, '192.168.2.1 ssh-ed25519 YWJj\n', '')
            with patch.object(subprocess, 'run', return_value=reply), self.assertRaises(mod.StopError):
                ssh.pin(CONFIG['hosts'][0])

    def test_missing_compute_is_rejected(self):
        cfg = copy.deepcopy(CONFIG)
        cfg['hosts'].pop(2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'hosts.json'
            path.write_text(json.dumps(cfg))
            with self.assertRaises(mod.StopError):
                mod.load_config(path)


if __name__ == '__main__':
    unittest.main()
