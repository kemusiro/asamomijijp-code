"""Fetch and freeze the Pi 4 all-evaluated ranked car once per vehicle job."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from vehicle_scene import SCHEMA, core, load_snapshot
from course_scene import COURSE_PROFILES


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("vehicle API redirect is not allowed")


def validate_api_url(url):
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or p.query or p.fragment or p.path != "/api/state":
        raise ValueError("vehicle API must be an http(s) /api/state URL without credentials/query")
    return url


def fetch_state(url, timeout=2.0):
    validate_api_url(url)
    with build_opener(NoRedirect()).open(Request(url, headers={"Accept": "application/json"}), timeout=timeout) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError("vehicle API response exceeds 256KiB")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _integer(value, label, maximum=2147483647):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("invalid " + label)
    return value


SELECTIONS = {'best':'ranking-best-v1', 'worst':'ranking-worst-nonzero-v1'}
ROLE_LABELS = {'best':'ベスト1', 'worst':'ワースト1（0.0m除外）'}


def snapshot_from_state(data, api_url, digest, fetched_at, selection='best'):
    if selection not in SELECTIONS:
        raise ValueError('selection must be best or worst')
    if not isinstance(data, dict) or data.get("version") not in ("vehicle-1", "vehicle-2"):
        raise ValueError("unsupported Pi 4 model version")
    duration = data.get('durationSeconds',16 if data['version']=='vehicle-1' else None)
    if type(duration) not in (int,float) or duration != (16 if data['version']=='vehicle-1' else 30):
        raise ValueError('Pi 4 simulation duration/version mismatch')
    if not isinstance(data.get("comparison"), dict) or not isinstance(data.get("ranking"), dict):
        raise ValueError("missing experiment/ranking")
    experiment = data["comparison"].get("id")
    if not isinstance(experiment, str) or not 1 <= len(experiment) <= 128:
        raise ValueError("invalid experiment ID")
    ranking = data['ranking']
    candidates = ranking.get(selection)
    if not isinstance(candidates,list) or not candidates or any(not isinstance(c,dict) for c in candidates):
        raise ValueError('Pi 4 has no evaluated '+selection+' car yet')
    if selection == 'worst':
        if ranking.get('worstPolicy') != 'nonzero-display-v1':
            raise ValueError('unsupported Pi 4 worst selection policy')
        eligible=[]
        for candidate in candidates:
            distance=candidate.get('distance')
            if type(distance) not in (int,float) or not math.isfinite(distance) or not 0<=distance<=160:
                raise ValueError('invalid worst distance')
            if distance>=.05:eligible.append(candidate)
        if not eligible:raise ValueError('Pi 4 has no nonzero-display worst car yet')
        car=min(eligible,key=lambda c:c['distance'])
    else:
        car=candidates[0]
    core.validate_genome(car.get("genome"))
    course = _integer(car.get("courseSeed"), "courseSeed")
    population = _integer(car.get("populationSeed"), "populationSeed")
    generation = _integer(car.get("generation"), "generation", 999)
    profile = car.get("courseProfile", "rolling-v1")
    if course != data.get("courseSeed") or profile != data.get("courseProfile", "rolling-v1") or profile not in COURSE_PROFILES:
        raise ValueError("ranked car course provenance mismatch")
    car_id = car.get("id")
    if not isinstance(car_id, str) or len(car_id) > 256 or not car_id.startswith(experiment + ":"):
        raise ValueError("ranked car belongs to a different experiment")
    distance = car.get("distance")
    if type(distance) not in (int, float) or not math.isfinite(distance) or not 0 <= distance <= 160:
        raise ValueError("invalid ranked distance")
    return {"schema": SCHEMA, "modelVersion": core.MODEL_VERSION, "genome": list(car["genome"]),
            "source": {"simulationVersion":data["version"],"durationSeconds":duration,"selection": SELECTIONS[selection], "apiUrl": api_url, "apiSha256": digest,
                       "experimentId": experiment, "carId": car_id, "fetchedAt": fetched_at,
                       "courseSeed": course, "courseProfile": profile, "populationSeed": population,
                       "generation": generation, "distanceM": distance},
            "approximation": "2D輪郭を押し出した静止模型。車幅と左右4輪は近似。3D走行性能は示さない。"}


class LiveVehicle:
    def __init__(self, url, cache_path, timeout=2.0, fetcher=fetch_state, selection='best'):
        if selection not in SELECTIONS:raise ValueError('selection must be best or worst')
        self.selection=selection
        self.url = validate_api_url(url)
        if not 0 < timeout <= 10:
            raise ValueError("vehicle API timeout must be in (0, 10]")
        self.cache_path = Path(cache_path)
        self.timeout = timeout
        self.fetcher = fetcher
        self.last_good = None
        try:
            cached = load_snapshot(self.cache_path)
            if cached["source"].get("selection") == SELECTIONS[self.selection] and cached["source"].get("apiUrl") == self.url:
                if self.selection!='worst' or cached['source']['distanceM']>=.05:
                    self.last_good = cached
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def select(self):
        try:
            data, digest = self.fetcher(self.url, self.timeout)
            snapshot = snapshot_from_state(data, self.url, digest, datetime.now(timezone.utc).isoformat(), self.selection)
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
            temporary.replace(self.cache_path)
            self.last_good = snapshot
            return copy.deepcopy(snapshot), None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            error = "Pi 4の" + ROLE_LABELS[self.selection] + "を取得できません: " + str(exc)
            return copy.deepcopy(self.last_good), error
