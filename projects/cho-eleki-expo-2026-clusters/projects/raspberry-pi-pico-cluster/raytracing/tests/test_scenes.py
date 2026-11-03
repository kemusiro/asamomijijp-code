"""Live best-car provenance, failure fallback and alternating render invariants."""
import binascii
import copy
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for directory in ("host", "pico", "network"):
    sys.path.insert(0, str(ROOT / directory))
import live_vehicle
import vehicle_scene
import scene_manager
import scene_raytracer as router
import ray_manager
import network_protocol as protocol


def api_state():
    car = vehicle_scene.load_snapshot(vehicle_scene.DEFAULT_SNAPSHOT)
    state = {"version":"vehicle-1", "courseSeed":2026, "courseProfile":"obstacles-v1",
            "comparison":{"id":"experiment-1"}, "ranking":{"best":[{
                "id":"experiment-1:2:8:3", "genome":car["genome"], "generation":8,
                "populationSeed":2028,"courseSeed":2026,"courseProfile":"obstacles-v1","distance":105.5}]}}
    worst=copy.deepcopy(state['ranking']['best'][0]);worst.update(distance=.05,populationSeed=2029,generation=3,id='experiment-1:3:3:1')
    worst['genome'][0]=.4
    state['ranking'].update(worst=[worst],worstPolicy='nonzero-display-v1')
    return state



class SceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name) / "car.json"
        self.state = api_state()
        self.url = "http://127.0.0.1:30096/api/state"

    def source(self, fetcher=None, selection='best'):
        path=self.cache if selection=='best' else self.cache.with_name('worst.json')
        return live_vehicle.LiveVehicle(self.url, path, fetcher=fetcher or (lambda *_:(self.state,"sha256")),selection=selection)

    def test_snapshot_is_all_time_best_and_does_not_change_with_api(self):
        source=self.source();first,error=source.select();self.assertIsNone(error)
        spec=scene_manager.vehicle_scene(first,"recovery")
        self.state["ranking"]["best"][0]["genome"][0]=.3
        self.state["ranking"]["best"][0]["distance"]=110
        self.assertEqual(spec["source"]["distanceM"],105.5)
        self.assertEqual(spec["job"]["vehicle"],first["genome"])
        second,error=source.select();self.assertNotEqual(first["genome"],second["genome"])
        self.assertEqual(first["source"]["populationSeed"],2028)
        self.assertEqual(first["source"]["courseProfile"],"obstacles-v1")

    def test_new_course_keeps_ranked_provenance_and_geometry(self):
        self.state['courseProfile']='obstacles-55-7p5-v1'
        for role in ('best','worst'):
            self.state['ranking'][role][0]['courseProfile']=self.state['courseProfile']
            snapshot,error=self.source(selection=role).select();self.assertIsNone(error)
            scene=scene_manager.vehicle_scene(snapshot,'smooth')
            self.assertEqual(scene['source']['courseProfile'],self.state['courseProfile'])
            self.assertEqual(scene['job']['terrain']['courseProfile'],self.state['courseProfile'])
            router.validate_job(scene['job'])

    def test_thirty_second_simulation_keeps_static_model_compatible(self):
        self.state.update(version='vehicle-2',durationSeconds=30)
        snapshot,error=self.source().select();self.assertIsNone(error)
        self.assertEqual(snapshot['source']['simulationVersion'],'vehicle-2')
        self.assertEqual(snapshot['source']['durationSeconds'],30)
        scene=scene_manager.vehicle_scene(snapshot,'smooth');router.validate_job(scene['job'])
        self.assertEqual(scene['job']['model_version'],vehicle_scene.core.MODEL_VERSION)
        self.state['durationSeconds']=16
        retained,error=self.source().select();self.assertIsNotNone(error);self.assertEqual(retained,snapshot)

    def test_offline_cache_survives_restart_and_keeps_original_source(self):
        first,_=self.source().select();before=self.cache.read_bytes()
        fail=lambda *_:(_ for _ in ()).throw(TimeoutError("offline"))
        cached,error=self.source(fail).select();self.assertIsNotNone(error);self.assertEqual(first,cached)
        self.assertEqual(self.cache.read_bytes(),before)
        scene=scene_manager.choose_scene(2,{'best':self.source(fail)},"recovery")
        self.assertEqual(scene["type"],"vehicle");self.assertIn("offline",scene["sourceError"])
        self.cache.unlink();fallback=scene_manager.choose_scene(2,{'best':self.source(fail)})
        self.assertEqual(fallback["type"],"sphere");self.assertIsNotNone(fallback["sourceError"])

    def test_malformed_data_does_not_replace_last_good(self):
        first,_=self.source().select();before=self.cache.read_bytes()
        for change in [lambda d:d.update(version="wrong"),lambda d:d.update(comparison=[]),lambda d:d.update(ranking=[]),lambda d:d["ranking"].update(best=[]),lambda d:d["ranking"]["best"][0].update(id="other:1"),lambda d:d["ranking"]["best"][0].update(genome=[True]*13),lambda d:d["ranking"]["best"][0].update(distance=float("nan")),lambda d:d["ranking"]["best"][0].update(generation=True),lambda d:d["ranking"]["best"][0].update(courseProfile="rolling-v1")]:
            data=copy.deepcopy(self.state);change(data)
            got,error=self.source(lambda *_:(data,"bad")).select();self.assertIsNotNone(error);self.assertEqual(got,first);self.assertEqual(before,self.cache.read_bytes())
        for url in ["file:///api/state","http://a:b@host/api/state","http://host/other","http://host/api/state?q=1"]:
            with self.assertRaises(ValueError):live_vehicle.validate_api_url(url)

    def test_worst_uses_minimum_nonzero_display_and_keeps_roles_separate(self):
        worst=self.state['ranking']['worst'][0]
        self.state['ranking']['worst']=[{**worst,'distance':d} for d in (0,.049999,.8,.05,.1)]
        snapshot,error=self.source(selection='worst').select();self.assertIsNone(error)
        self.assertEqual(snapshot['source']['distanceM'],.05)
        self.assertEqual(snapshot['source']['selection'],'ranking-worst-nonzero-v1')
        scene=scene_manager.vehicle_scene(snapshot,'recovery');self.assertEqual(scene['role'],'worst');self.assertIn('ワースト1',scene['label'])
        best,_=self.source().select();self.assertEqual(best['source']['distanceM'],105.5)
        self.assertNotEqual(best['genome'],snapshot['genome'])
        self.assertEqual(scene_manager.vehicle_scene(best,'recovery')['role'],'best')

    def test_missing_worst_falls_back_to_sphere_without_using_best(self):
        self.source().select()
        self.state['ranking']['worst']=[{**self.state['ranking']['worst'][0],'distance':.049}]
        sources={'best':self.source(),'worst':self.source(selection='worst')}
        fallback=scene_manager.choose_scene(1,sources,'recovery')
        self.assertEqual(fallback['type'],'sphere');self.assertEqual(fallback['requestedRole'],'worst');self.assertIn('ワースト1',fallback['label'])
        self.assertEqual(scene_manager.choose_scene(2,sources,'recovery')['role'],'best')
        self.assertEqual(scene_manager.choose_scene(3,{},'recovery')['type'],'sphere')

    def test_cache_role_and_zero_distance_are_checked_on_restart(self):
        fail=lambda *_:(_ for _ in ()).throw(TimeoutError('offline'))
        self.source().select()
        wrong=live_vehicle.LiveVehicle(self.url,self.cache,fetcher=fail,selection='worst')
        self.assertIsNone(wrong.select()[0])
        worst,_=self.source(selection='worst').select();path=self.cache.with_name('worst.json')
        cached,error=self.source(fail,selection='worst').select();self.assertEqual(cached,worst);self.assertIsNotNone(error)
        worst['source']['distanceM']=.049;path.write_text(json.dumps(worst))
        self.assertIsNone(self.source(fail,selection='worst').select()[0])
        wrong=live_vehicle.LiveVehicle(self.url,path,fetcher=fail,selection='best')
        self.assertIsNone(wrong.select()[0])
        self.state['ranking']['worstPolicy']='unknown'
        self.assertIsNone(self.source(selection='worst').select()[0])

    def test_core_switch_restores_exact_sphere_pixels_and_changes_vehicles(self):
        sphere=scene_manager.sphere_scene(True)["job"]
        first=router.compute_tile(sphere,0,0,8,8)
        car=scene_manager.vehicle_scene(self.source().select()[0],"recovery")["job"]
        body=router.compute_tile(car,0,0,8,8)
        self.assertNotEqual(first,body);self.assertEqual(router.compute_tile(sphere,0,0,8,8),first)
        self.assertNotEqual(router.ALGORITHM_VERSION,ray_manager.core.ALGORITHM_VERSION)
        with self.assertRaises(ValueError):router.validate_job(dict(sphere,scene_type="unknown"))
        output=bytearray(8*8*3);router.compute_tile_into(car,0,0,8,8,output);self.assertEqual(output,body)

    def test_real_three_worker_protocol_alternates_sphere_vehicle_sphere(self):
        snapshot=self.source().select()[0]
        for scene in [scene_manager.sphere_scene(True),scene_manager.vehicle_scene(snapshot,"recovery"),scene_manager.sphere_scene(True)]:
            job=scene["job"];tiles=ray_manager.build_full_frame_tiles(job,8)
            # A direct reference and streamed tile assembly must match byte for byte.
            reference=bytearray(job["width"]*job["height"]*3)
            for tile in tiles:
                payload=router.compute_tile(job,tile["x0"],tile["y0"],tile["width"],tile["height"])
                for y in range(tile["height"]):
                    start=((tile["y0"]+y)*job["width"]+tile["x0"])*3;row=tile["width"]*3;reference[start:start+row]=payload[y*row:(y+1)*row]
            pairs=[socket.socketpair() for _ in range(3)];received=[];errors=[]
            def worker(sock,i):
                try:
                    protocol.send_frame(sock,{"type":"hello","protocol_version":protocol.PROTOCOL_VERSION,"algorithm_version":router.ALGORITHM_VERSION,"output_version":router.OUTPUT_VERSION,"checksum_version":router.CHECKSUM_VERSION,"node_id":"mixed-%d"%i,"udp_port":42000+i,"start_transport":"tcp","watchdog_enabled":True,"watchdog_timeout_ms":8000})
                    msg,_=protocol.recv_frame(sock);received.append(copy.deepcopy(msg["job"]));router.validate_job(msg["job"])
                    protocol.send_frame(sock,{"type":"ready","job_id":msg["job_id"]});protocol.recv_frame(sock)
                    while True:
                        tile,_=protocol.recv_frame(sock)
                        if tile["type"]=="complete":return
                        payload=router.compute_tile(msg["job"],tile["x0"],tile["y0"],tile["width"],tile["height"])
                        protocol.send_frame(sock,{**tile,"type":"tile_result","payload_crc32":"%08x"%(binascii.crc32(payload)&0xffffffff),"compute_ms":1},payload)
                except BaseException as e:errors.append(e)
                finally:sock.close()
            threads=[threading.Thread(target=worker,args=(p[1],i),daemon=True) for i,p in enumerate(pairs)]
            for t in threads:t.start()
            output=Path(self.tmp.name)/(scene["type"]+".png")
            session=ray_manager.cluster_manager.ManagerSession(job,8,"mixed-job",request_window=1,workload=scene_manager.SceneWorkload(output,job))
            summary=session.run_workers([(p[0],lambda *_:None) for p in pairs])
            for p in pairs:p[0].close()
            for t in threads:t.join(5)
            self.assertFalse(errors,errors);self.assertEqual(received,[job]*3)
            self.assertEqual(summary["checksum32"],"%08x"%(binascii.crc32(reference)&0xffffffff));self.assertEqual(summary["tiles_completed"],len(tiles))
            if scene["type"]=="vehicle":
                self.assertIsNone(summary["checksum_matches"]);self.assertIsNone(summary["known_pixels_match"]);self.assertEqual(summary["total_tiles"],len(tiles))
                spec=importlib.util.spec_from_file_location("mixed_integration_runner",ROOT.parents[2]/"scripts/run-pico-raytracing-exhibition.py")
                runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
                self.assertEqual(runner.validate_summary(dict(summary,scene_type="vehicle"),3),[])
            else:self.assertTrue(summary["checksum_matches"]);self.assertTrue(summary["known_pixels_match"])

    def test_runner_scene_order_fallback_and_summary_rules(self):
        spec=importlib.util.spec_from_file_location("mixed_runner",ROOT.parents[2]/"scripts/run-pico-raytracing-exhibition.py")
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        args=types.SimpleNamespace(scene_mode="alternating",vehicle_api=self.url,vehicle_api_timeout=1,vehicle_preset="recovery",sphere_preset="recovery",output_dir=Path(self.tmp.name),job_prefix="alternating",cycles=6,cycle_seconds=2,recovery_cycle_seconds=3,minimum_display_seconds=1)
        seen=[]
        def job(suffix,scene_spec=None,**kwargs):
            seen.append(scene_spec.get("role",scene_spec["type"]))
            return {"job_id":suffix,"checksum32":"12345678","output_path":"/tmp/"+suffix+".png","e2e_ms":1,"startup_ready_ms":1,"worker_timeouts":[],"requeued_tiles":0}
        real_source=live_vehicle.LiveVehicle
        constructor=lambda url,path,timeout,selection:real_source(url,path,timeout,fetcher=lambda *_:(self.state,'sha256'),selection=selection)
        with mock.patch.object(live_vehicle,"LiveVehicle",side_effect=constructor),mock.patch.object(runner.time,"sleep"):
            result=runner.run_cycles(args,job_runner=job)
        self.assertEqual(seen,["worst","best","sphere","worst","best","sphere"]);self.assertEqual(len(result),6)
        final=json.loads((Path(self.tmp.name)/"alternating-display-state.json").read_text());self.assertEqual(final["held_result"]["scene"]["type"],"sphere");self.assertEqual(result[1]["scene"]["source"]["generation"],8);self.assertEqual(result[0]["scene"]["source"]["generation"],3)
        summary={"scene_type":"vehicle","checksum_matches":None,"known_pixels_match":None,"tiles_completed":40,"total_tiles":40,"worker_count_started":1,"worker_count_active_at_completion":1,"workers":[{"node_id":"pico-01","watchdog_enabled":True,"watchdog_timeout_ms":8000}],"worker_timeouts":[],"requeued_tiles":0}
        self.assertEqual(runner.validate_summary(summary,1),[])
        for change in [{"tiles_completed":39},{"checksum_matches":True},{"known_pixels_match":True}]:
            with self.assertRaises(RuntimeError):runner.validate_summary(dict(summary,**change),1)


if __name__=="__main__":unittest.main()
