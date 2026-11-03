from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
import os
import json
import hashlib

spec = importlib.util.spec_from_file_location("audit", Path(__file__).with_name("audit-pi4-management-soak.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def good(value):
    return dict(ok=True, value=value)


def units(names):
    return good([dict(Id=name, MainPID=str(i+1), NRestarts="0", ActiveState="active",
                      ExecMainStartTimestampMonotonic="100") for i,name in enumerate(names)])


def fixture():
    rows = []
    for i in range(181):
        elapsed = i*60
        at = (datetime(2026,10,17,13,tzinfo=timezone.utc)+timedelta(seconds=elapsed)).isoformat()
        core = {key:good(value) for key,value in dict(
            nodes=dict(count=13,ready=13,expected=13), livez="ok", kubelet="ok",
            power="throttled=0x0", resources=dict(memory=dict(MemAvailable_kib=6000000))).items()}
        local_monitor = dict(status="ok", failures=[], age_seconds=1, boot_id="mng-boot",
                             monotonic_seconds=1000+elapsed, probes=core)
        pico_monitor = dict(status="ok", failures=[], age_seconds=1, boot_id="pico-host-boot",
                            monotonic_seconds=2000+elapsed, probes=dict(banner=good("SSH-2.0-test")))
        local = good(dict(monitor=good(local_monitor), units=units(["ssh.service","k3s.service"]),
                          traffic=good(dict(ready=12,expected=12,errors=[],exhibition=dict(
                              status="running",error=None,updatedAt=at,cycle=100+i,phase="result"))),
                          workloads=good([dict(uid=str(n),phase="Running",ready=True,restarts=0) for n in range(13)]),
                          vehicle=good(dict(running=True,error=None,experiment="experiment",evaluated=i*100))))
        pico = good(dict(monitor=good(pico_monitor),units=units([
            "pico-raytracing-runner.service","pico-raytracing-display.service"]),
            pico=good(dict(mode="rendering",updated_at=at,expected_workers=16,cycle=200+i))))
        rows.append(dict(at=at,elapsed_seconds=elapsed,failures=[],local=local,pico=pico,
                         storage=good(dict(sessions=good(12)))))
    return rows


class SoakTests(unittest.TestCase):
    def test_clean_three_hours(self):
        result=m.audit(fixture())
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["duration_seconds"],10800)
        self.assertEqual(result["sample_count"],181)

    def test_gaps_short_interval_and_missing_samples_fail(self):
        for change in ("gap","short","duplicate"):
            with self.subTest(change=change):
                rows=fixture()
                if change=="gap": rows.pop(90)
                if change=="short": rows=rows[:-1]
                if change=="duplicate": rows.insert(90,deepcopy(rows[90]))
                self.assertFalse(m.audit(rows)["passed"])

    def test_ssh_failure_is_not_ignored_when_next_probe_recovers(self):
        rows=fixture();rows[90]["local"]=dict(ok=False,error="timeout")
        result=m.audit(rows)
        self.assertFalse(result["passed"])
        self.assertTrue(any(f.get("index")==90 for f in result["failures"]))

    def test_restart_boot_change_and_stale_monitor_fail(self):
        for defect in ("pid","boot","age","inner_probe"):
            with self.subTest(defect=defect):
                rows=fixture();local=rows[90]["local"]["value"]
                if defect=="pid":local["units"]["value"][0]["MainPID"]="99"
                if defect=="boot":local["monitor"]["value"]["boot_id"]="rebooted"
                if defect=="age":local["monitor"]["value"]["age_seconds"]=120
                if defect=="inner_probe":local["monitor"]["value"]["probes"]["livez"]["ok"]=False
                self.assertFalse(m.audit(rows)["passed"])

    def test_nodes_traffic_storage_and_pico_failures(self):
        for defect in ("nodes","workers","pod","storage","pico"):
            with self.subTest(defect=defect):
                rows=fixture();row=rows[90];local=row["local"]["value"]
                if defect=="nodes":local["monitor"]["value"]["probes"]["nodes"]["value"]["ready"]=12
                if defect=="workers":local["traffic"]["value"]["ready"]=11
                if defect=="pod":local["workloads"]["value"][0]["uid"]="replacement"
                if defect=="storage":row["storage"]["value"]["sessions"]["value"]=11
                if defect=="pico":row["pico"]["value"]["pico"]["value"]["mode"]="recovering"
                self.assertFalse(m.audit(rows)["passed"])

    def test_workload_that_never_advances_fails(self):
        for key in ("traffic","pico","vehicle"):
            with self.subTest(key=key):
                rows=fixture()
                for row in rows:
                    if key=="traffic":row["local"]["value"]["traffic"]["value"]["exhibition"]["cycle"]=100
                    if key=="pico":row["pico"]["value"]["pico"]["value"]["cycle"]=200
                    if key=="vehicle":row["local"]["value"]["vehicle"]["value"]["evaluated"]=0
                self.assertFalse(m.audit(rows)["passed"])

    def test_manual_new_vehicle_experiment_is_recorded_without_false_counter_regression(self):
        rows=fixture()
        for i,row in enumerate(rows[90:]):
            row["local"]["value"]["vehicle"]["value"].update(experiment="new",evaluated=i*100)
        self.assertTrue(m.audit(rows)["passed"])

    def test_cached_or_stale_exhibition_is_not_counted_as_live_load(self):
        rows=fixture()
        rows[90]["local"]["value"]["traffic"]["value"]["exhibition"]["updatedAt"]=rows[0]["at"]
        self.assertFalse(m.audit(rows)["passed"])

    def test_runner_rejects_short_or_busy_loop_before_ssh_or_output(self):
        runner=Path(__file__).with_name("run-pi4-management-soak.py")
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)
            marker=directory/"ssh-called"
            fake=directory/"ssh"
            fake.write_text('#!/bin/sh\nprintf called > "'+str(marker)+'"\nexit 99\n')
            fake.chmod(0o755)
            for seconds,interval in ((0,60),(10800,0)):
                output=directory/("out-"+str(seconds)+"-"+str(interval))
                args=[sys.executable,"-B",str(runner),"--mng","test@localhost", "--pico","test@localhost",
                      "--storage","test@localhost", "--probe","/probe.py", "--stop-file","/stop",
                      "--output",str(output),"--seconds",str(seconds),"--interval",str(interval)]
                result=subprocess.run(args,capture_output=True,text=True,timeout=3,
                                      env={**os.environ,"PATH":str(directory)+os.pathsep+os.environ["PATH"]})
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertFalse(marker.exists())
                self.assertFalse(output.exists())

    def test_guard_restores_only_matching_one_replica_deployment(self):
        guard=Path(__file__).with_name("guard-pi4-traffic-soak.py")
        template={"metadata":{"labels":{"app":"test-traffic"}}}
        digest=hashlib.sha256(json.dumps(template,sort_keys=True).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root);state=directory/"state.json";marker=directory/"scaled"
            fake=directory/"k3s"
            fake.write_text("#!"+sys.executable+"\n"+"""import json,pathlib,sys,os
p=pathlib.Path(os.environ['GUARD_STATE'])
d=json.loads(p.read_text())
if 'scale' in sys.argv:
 pathlib.Path(os.environ['GUARD_SCALED']).write_text('yes')
 d['spec']['replicas']=0;p.write_text(json.dumps(d));print('scaled')
else:print(json.dumps(d))
""")
            fake.chmod(0o755)
            env={**os.environ,"PATH":str(directory)+os.pathsep+os.environ["PATH"],
                 "GUARD_STATE":str(state),"GUARD_SCALED":str(marker),"PYTHONOPTIMIZE":"1"}
            args=[sys.executable,"-B",str(guard),"--uid","expected", "--template-sha",digest,
                  "--seconds","0", "--stop-file",str(directory/"stop")]
            for uid,replicas,success in (("expected",1,True),("replacement",1,False),("expected",2,False)):
                state.write_text(json.dumps(dict(metadata=dict(uid=uid),spec=dict(replicas=replicas,template=template))))
                marker.unlink(missing_ok=True)
                result=subprocess.run(args,capture_output=True,text=True,timeout=4,env=env)
                self.assertEqual(result.returncode==0,success,result.stderr)
                self.assertEqual(marker.exists(),success)
                if success:self.assertEqual(json.loads(state.read_text())["spec"]["replicas"],0)
            state.write_text(json.dumps(dict(metadata=dict(uid="expected"),spec=dict(replicas=1,template=template))))
            marker.unlink(missing_ok=True)
            bad_args=list(args);bad_args[bad_args.index("--template-sha")+1]="0"*64
            result=subprocess.run(bad_args,capture_output=True,text=True,timeout=4,env=env)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(marker.exists())

    def test_truncated_input_is_rejected_without_report(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"samples.jsonl";output=Path(directory)/"result.json"
            source.write_text('{"elapsed_seconds":')
            result=subprocess.run([sys.executable,"-B",str(Path(m.__file__)),str(source),"--output",str(output)],
                                  capture_output=True,text=True,timeout=3)
            self.assertEqual(result.returncode,1)
            self.assertIn("監査できません",result.stderr)
            self.assertFalse(output.exists())

    def test_full_monitor_catches_failure_between_sixty_second_snapshots(self):
        rows=fixture()
        start=rows[0]["at"];end=rows[-1]["at"]
        origin=datetime.fromisoformat(start)
        records=[dict(at=(origin+timedelta(seconds=i*30)).isoformat(),mode="local",boot_id="boot",
                      monotonic_seconds=1000+i*30,status="ok",failures=[],probes=dict(health=good("ok")))
                 for i in range(361)]
        self.assertTrue(m.audit_monitor(records,start,end,"local")["passed"])
        records[1]["failures"]=["transient_livez"]
        self.assertFalse(m.audit_monitor(records,start,end,"local")["passed"])
        records[1]["failures"]=[];records.pop(100)
        self.assertFalse(m.audit_monitor(records,start,end,"local")["passed"])

    def test_rotated_monitor_files_are_merged_without_inflating_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            a=dict(at="2026-10-17T13:00:00+00:00",boot_id="boot",monotonic_seconds=1)
            b=dict(at="2026-10-17T13:00:30+00:00",boot_id="boot",monotonic_seconds=31)
            (root/"samples.jsonl.1").write_text(json.dumps(a)+"\n"+json.dumps(b)+"\n")
            (root/"samples.jsonl").write_text(json.dumps(b)+"\n")
            self.assertEqual(len(m.monitor_records(root)),2)
            b["changed"]=True;(root/"samples.jsonl").write_text(json.dumps(b)+"\n")
            with self.assertRaises(ValueError):m.monitor_records(root)


if __name__ == "__main__":
    unittest.main()
