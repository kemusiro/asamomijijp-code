"""Unified wire version with scene-specific image validation."""
from __future__ import annotations
import copy
from pathlib import Path
import sys

HOST = Path(__file__).resolve().parents[1] / "host"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
import ray_manager
import scene_raytracer as core
from vehicle_manager import VehicleResultAssembler
from vehicle_scene import make_job, model_id


def sphere_scene(recovery=False, preset="exhibition"):
    jobs = {"recovery": ray_manager.RECOVERY_JOB, "preview": ray_manager.PREVIEW_JOB, "exhibition": ray_manager.EXHIBITION_JOB, "detailed": ray_manager.DETAILED_JOB}
    job = dict(jobs["recovery" if recovery else preset], scene_type="sphere")
    return {"type": "sphere", "label": "球体のレイトレーシング", "job": job}


def vehicle_scene(snapshot, preset="preview", source_error=None):
    job = dict(make_job(snapshot, preset, terrain=True), scene_type="vehicle")
    role='worst' if snapshot['source'].get('selection')=='ranking-worst-nonzero-v1' else 'best'
    label='車体ワースト1（0.0m除外）' if role=='worst' else '車体ベスト1'
    return {"type": "vehicle", "role":role, "label":label, "job": job,
            "modelId": model_id(snapshot), "terrain": {k:v for k,v in job["terrain"].items() if k!="points"}, "source": copy.deepcopy(snapshot["source"]),
            "snapshot": copy.deepcopy(snapshot), "sourceError": source_error}


def public_scene(scene):
    return {k: copy.deepcopy(v) for k, v in scene.items() if k not in ("job", "snapshot")}


def choose_scene(cycle, source, preset="preview", sphere_preset="exhibition"):
    role=('worst','best','sphere')[(cycle-1)%3]
    if role=='sphere':
        return sphere_scene(preset=sphere_preset)
    snapshot, error = source[role].select()
    if snapshot is None:
        scene = sphere_scene(preset=sphere_preset)
        scene["sourceError"] = error
        scene["requestedRole"]=role
        scene["label"] = "球体（" + ("ワースト1" if role=="worst" else "ベスト1") + "の取得待ち）"
        return scene
    return vehicle_scene(snapshot, preset, error)


class SceneVehicleAssembler(VehicleResultAssembler):
    def finish(self):
        result = super().finish()
        result["total_tiles"] = len(self.tiles)
        return result


class SceneWorkload(ray_manager.RayTracingWorkload):
    algorithm_version = core.ALGORITHM_VERSION

    def __init__(self, output_path, job):
        super().__init__(output_path)
        core.validate_job(job)
        self.job = copy.deepcopy(job)

    def create_assembler(self, job, tiles, job_id):
        if job != self.job:
            raise ValueError("scene job changed after selection")
        cls = SceneVehicleAssembler if job["scene_type"] == "vehicle" else ray_manager.RayResultAssembler
        return cls(job, tiles, job_id, self.output_path)
