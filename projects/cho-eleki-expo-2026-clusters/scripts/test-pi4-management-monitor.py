import importlib.util
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


spec = importlib.util.spec_from_file_location("monitor", Path(__file__).with_name("monitor-pi4-management.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def good_local():
    return {k:dict(ok=True,value=v) for k,v in dict(
        resources={},services="ActiveState=active\nActiveState=active",ssh_listener="LISTEN",
        sockets="",livez="ok",kubelet="ok",nodes=dict(count=13,ready=13,expected=13),power="throttled=0x0").items()}


class MonitorTests(unittest.TestCase):
    def test_three_failures_are_classified_without_recovery(self):
        probes = good_local()
        probes["livez"] = dict(ok=False,error="timeout")
        with patch.object(m,"local_sample",return_value=probes), patch.object(m,"text_file",return_value="boot-test"):
            count=0
            for expected in ("suspect","suspect","degraded"):
                record,count=m.sample(dict(mode="local"),count)
                self.assertEqual(record["status"],expected)
                self.assertEqual(record["recovery_action"],"none")
                self.assertEqual(record["boot_id"],"boot-test")
                self.assertGreater(record["monotonic_seconds"],0)
                self.assertIn("livez",record["failures"])
        with patch.object(m,"local_sample",return_value=good_local()), patch.object(m,"text_file",return_value="boot-test"):
            record,count=m.sample(dict(mode="local"),count)
            self.assertEqual(count,0)
            self.assertEqual(record["status"],"ok")

    def test_node_loss_listener_power_and_livez_are_detected(self):
        for key,value in (("nodes",dict(count=13,ready=12,expected=13)),
                          ("ssh_listener",""),("power","throttled=0x50000"),
                          ("livez","not ok"),("services","ActiveState=active")):
            with self.subTest(key=key):
                probes=good_local();probes[key]["value"]=value
                self.assertTrue(m.failures("local",probes))

    def test_probe_timeout_does_not_discard_other_evidence(self):
        def fail(): raise TimeoutError("unavailable")
        values=m.parallel(dict(first=fail,second=lambda:42))
        self.assertFalse(values["first"]["ok"])
        self.assertEqual(values["second"]["value"],42)

    def test_ssh_closed_or_partial_banner_is_bounded(self):
        for chunks,valid in (([b"SSH-2.0-",b"OpenSSH_9.6\r\n"],True),
                             ([b"SSH-2.0-",b""],False),([b"HTTP/1.1 200\n"],False)):
            listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen()
            port=listener.getsockname()[1]
            def serve():
                with listener:
                    connection,_=listener.accept()
                    with connection:
                        for chunk in chunks: connection.sendall(chunk)
            thread=threading.Thread(target=serve);thread.start()
            try:
                if valid: self.assertTrue(m.ssh_banner("127.0.0.1",port,1).startswith("SSH-2.0-"))
                else:
                    with self.assertRaises(RuntimeError):m.ssh_banner("127.0.0.1",port,1)
            finally:thread.join(timeout=2)

    def test_ssh_no_banner_times_out(self):
        listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen()
        release=threading.Event()
        def serve():
            with listener:
                connection,_=listener.accept()
                with connection:release.wait(2)
        thread=threading.Thread(target=serve);thread.start()
        try:
            with self.assertRaises(TimeoutError):m.ssh_banner("127.0.0.1",listener.getsockname()[1],.05)
        finally:release.set();thread.join(timeout=2)

    def test_http_401_is_reachable_but_not_livez_health(self):
        error=HTTPError("https://example.test/livez",401,"Unauthorized",{},None)
        with patch.object(m,"urlopen",side_effect=error):
            result=m.http_read(error.url,1,transport_only=True)
            self.assertTrue(result["transport_ok"])
            self.assertIsNone(result["health"])
        with patch.object(m,"urlopen",side_effect=error):
            with self.assertRaises(HTTPError):m.http_read(error.url,1)

    def test_configuration_rejects_busy_loop_unbounded_timeout_and_insecure_api(self):
        for config in (dict(mode="local",interval=0),dict(mode="local",timeout=100),
                       dict(mode="local",interval=float("nan")),dict(mode="observer"),
                       dict(mode="observer",host="example.test",k3s_ca="ca.pem",
                            k3s_url="http://example.test/livez",vehicle_url="http://example.test",
                            pico_url="http://127.0.0.1:8080")):
            with self.assertRaises(ValueError):m.validate_config(config)
        self.assertEqual(m.validate_config(dict(mode="local"))["interval"],30)

    def test_missing_ca_does_not_hide_other_probes(self):
        config=dict(host="127.0.0.1",ssh_port=22,timeout=1,
                    k3s_ca="/nonexistent-ca.pem",k3s_url="https://127.0.0.1/livez")
        with patch.object(m,"ssh_banner",return_value="SSH-2.0-test"), \
             patch.object(m,"vehicle",return_value=dict(error=None)), \
             patch.object(m,"pico",return_value=dict(mode="rendering")):
            probes=m.observer_sample(config)
        self.assertFalse(probes["api_transport"]["ok"])
        self.assertTrue(probes["ssh_banner"]["ok"])
        self.assertTrue(probes["vehicle"]["ok"])
        self.assertTrue(probes["pico"]["ok"])

    def test_vehicle_api_session_is_identifier(self):
        data=dict(session="session-id",running=True,error=None,comparison=dict(id="experiment"),
                  generation=20,ranking=dict(evaluated=12345),version="vehicle-2")
        with patch.object(m,"http_read",return_value=data):
            value=m.vehicle(dict(vehicle_url="http://example.test",timeout=1))
        self.assertTrue(value["running"])
        self.assertEqual(value["evaluated"],12345)

    def test_observer_keeps_render_transitions_healthy(self):
        probes={k:dict(ok=True,value=v) for k,v in dict(
            ssh_banner="SSH-2.0-test",api_transport=dict(health=None),
            vehicle=dict(error=None),pico=dict(mode="waiting_for_workers")).items()}
        self.assertEqual(m.failures("observer",probes),[])
        probes["pico"]["value"]["mode"]="waiting_for_manual_recovery"
        self.assertIn("pico_error",m.failures("observer",probes))


if __name__ == "__main__":unittest.main()
