"""Validated host snapshot/job contract for a single immutable vehicle."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

PICO = Path(__file__).resolve().parents[1] / 'pico'
if str(PICO) not in sys.path:
    sys.path.insert(0, str(PICO))
import vehicle_raytracer as core

SCHEMA = 'vehicle-showcase-v1'
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / 'vehicle' / 'champion-2026.json'
PRESETS = {
    'preview': (160, 90, 1, 1, 1),
    'recovery': (64, 36, 1, 1, 1),
    'exhibition': (320, 180, 1, 1, 1),
    'smooth': (320, 180, 2, 1, 1),
    'high-quality': (384, 216, 4, 2, 2),
}


def load_snapshot(path):
    with Path(path).open(encoding='utf-8') as stream:
        snapshot = json.load(stream)
    if not isinstance(snapshot, dict):
        raise ValueError('vehicle snapshot must be an object')
    if snapshot.get('schema') != SCHEMA or snapshot.get('modelVersion') != core.MODEL_VERSION:
        raise ValueError('unsupported vehicle snapshot schema/modelVersion')
    core.validate_genome(snapshot.get('genome'))
    source = snapshot.get('source', {})
    if not isinstance(source, dict):
        raise ValueError('vehicle source must be an object')
    for key in ('courseSeed', 'populationSeed', 'generation'):
        value = source.get(key)
        if type(value) is not int or not 0 <= value <= 2147483647:
            raise ValueError('invalid vehicle source ' + key)
    distance = source.get('distanceM')
    if type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0:
        raise ValueError('invalid vehicle source distanceM')
    return snapshot


def model_id(snapshot):
    data = {'modelVersion': snapshot['modelVersion'], 'genome': snapshot['genome']}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def make_job(snapshot, preset='preview', terrain=False):
    width, height, samples, shadows, bounces = PRESETS[preset]
    job = {'name': 'vehicle-' + model_id(snapshot)[:16] + '-' + preset,
           'model_version': core.MODEL_VERSION, 'vehicle': list(snapshot['genome']),
           'width': width, 'height': height, 'samples': samples,
           'shadow_samples': shadows, 'max_bounces': bounces}
    if terrain:
        from course_scene import terrain_for_source
        job['terrain'] = terrain_for_source(snapshot['source'])
        job['name'] += '-course-diorama-v1'
    core.validate_job(job)
    return job


def from_comparison(path):
    """Explicit offline export; never fetch or poll a live Pi 4 service."""
    data = json.loads(Path(path).read_text())
    results = data.get('results')
    if results is None:
        results = data.get('comparison', {}).get('results')
    if not results:
        raise ValueError('comparison has no completed results')
    for result in results:
        core.validate_genome(result['champion']['genome'])
        distance = result['champion']['distance']
        if type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0:
            raise ValueError('invalid champion distance')
    result = max(results, key=lambda row: row['champion']['distance'])
    champion = result['champion']
    snapshot = {'schema': SCHEMA, 'modelVersion': core.MODEL_VERSION,
                'genome': champion['genome'],
                'source': {'comparisonFile': Path(path).name,
                           'comparisonSha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                           'sourceRevision': data.get('sourceRevision'),
                           'courseSeed': result['courseSeed'],
                           'populationSeed': result['populationSeed'],
                           'generation': champion['generation'],
                           'distanceM': champion['distance']},
                'approximation': '2D輪郭を幅0.96で押し出し、左右に4輪を配置。車幅・アーム・ホイール意匠は展示用の仮定。3Dの走行性能を示さない。'}
    return snapshot
