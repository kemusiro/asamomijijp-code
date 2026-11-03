"""Exercise device rollback paths without USB or an mpremote installation."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('vehicle_probe_test_module',ROOT/'scripts/validate-pico-vehicle-network.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeRollbackTests(unittest.TestCase):
    def run_preflight(self, mismatch):
        writes=[]
        reads={}
        class TransportError(Exception): pass
        class Board:
            def __init__(self,port): self.port=port
            def enter_raw_repl(self,**kwargs): pass
            def exec(self,code):
                if 'NODE_ID' in code:
                    return ('pico-01' if self.port=='port1' else 'pico-02').encode()
                return b''
            def fs_hashfile(self,name,algorithm):
                reads[self.port]=reads.get(self.port,0)+1
                return b'bad' if mismatch and self.port=='port1' and reads[self.port]>3 else b'good'
            def fs_writefile(self,*args): writes.append(args)
            def exec_raw_no_follow(self,code): raise OSError(6,'USB detached after reset')
            def close(self): raise OSError(6,'USB already detached')
        serial=types.ModuleType('mpremote.transport_serial'); serial.SerialTransport=Board
        transport=types.ModuleType('mpremote.transport'); transport.TransportError=TransportError
        modules={'mpremote':types.ModuleType('mpremote'),'mpremote.transport_serial':serial,'mpremote.transport':transport}
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'new'
            argv=['probe','--ssh-host','unused','--remote-root','/unused','--remote-output','/unused.png',
                  '--port-glob','port*','--expected-nodes','pico-01,pico-03','--output-dir',str(output)]
            with mock.patch.dict(sys.modules,modules),mock.patch.object(sys,'argv',argv),mock.patch.object(probe.glob,'glob',return_value=['port1','port2']),mock.patch.object(probe.subprocess,'Popen') as popen:
                with self.assertRaises(RuntimeError): probe.main()
                popen.assert_not_called()
            records=json.loads((output/'devices.json').read_text())
        self.assertEqual(writes,[])
        self.assertEqual(len(records),2)
        return records

    def test_unexpected_identity_writes_nothing_and_usb_detach_does_not_skip_cleanup(self):
        self.assertTrue(all(r['restored'] for r in self.run_preflight(False)))

    def test_cleanup_failure_on_first_device_still_resets_second(self):
        records=self.run_preflight(True)
        self.assertIn('cleanupError',records[0])
        self.assertTrue(records[1]['restored'])


if __name__=='__main__': unittest.main()
