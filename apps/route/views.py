"""
Route module - Navigation and routing
"""
import csv
import math
import os
import subprocess
import time
import threading
import requests
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from apps.route.nav_utils import split_points
from sqlalchemy.exc import SQLAlchemyError
from apps.config.server import db
from apps.route.models import Hazard, MyPath

bp = Blueprint("route", __name__)

def _match_osm_edge(lat, lon, session=None, base_url=None, profile=None):
    """
    Resolve the nearest OSM edge for a hazard point using OSRM `nearest`.
    Falls back to None if OSRM is unavailable.
    """
    http = session or requests.Session()
    base = (base_url or os.getenv("OSRM_BASE_URL") or "http://localhost:5000").rstrip("/")
    prof = profile or os.getenv("OSRM_PROFILE") or "driving"
    url = f"{base}/nearest/v1/{prof}/{lon},{lat}?number=1"
    try:
        resp = http.get(url, timeout=1.5)
        if resp.status_code != 200:
            return None
        payload = resp.json()
    except Exception:
        return None

    waypoints = payload.get("waypoints") or []
    if not waypoints:
        return None
    nodes = waypoints[0].get("nodes") or []
    if len(nodes) >= 2:
        a, b = sorted(nodes[:2])
        return f"osm:{a}-{b}"
    location = waypoints[0].get("location") or []
    if len(location) == 2:
        return f"osrm:{location[1]:.5f}:{location[0]:.5f}"
    return None


def build_hazard_osm_edge_mapping(limit=1000, base_url=None, profile=None):
    """
    Map active hazards to their nearest OSM edge IDs and persist updates.
    Returns a summary dict describing the run.
    """
    query = Hazard.query.filter_by(is_active=True).order_by(Hazard.updated_at.desc())
    if limit:
        query = query.limit(int(limit))
    hazards = query.all()
    if not hazards:
        return {"attempted": 0, "updated": 0, "missed": 0}

    session = requests.Session()
    updates = []
    misses = 0
    for hazard in hazards:
        edge = _match_osm_edge(hazard.lat, hazard.lon, session=session, base_url=base_url, profile=profile)
        if not edge:
            misses += 1
            continue
        current_edge = hazard.osm_edge_id or hazard.edge_id
        if current_edge != edge:
            updates.append({"hazard_id": hazard.hazard_id, "edge_id": edge, "osm_edge_id": edge})

    if updates:
        db.session.bulk_update_mappings(Hazard, updates)
        db.session.commit()
        _hazard_cache(force=True)
    return {"attempted": len(hazards), "updated": len(updates), "missed": misses}

def hazard_edge_matcher_cli(argv=None):
    """
    CLI helper to backfill hazard osm_edge_id values via OSRM nearest lookups.
    Intended for quick one-off runs: python -m apps.route.views --limit 500
    """
    import argparse
    parser = argparse.ArgumentParser(description="Map hazards to nearest OSM edges")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum hazards to process")
    parser.add_argument("--osrm-base-url", dest="osrm_base_url", help="Override OSRM base URL")
    parser.add_argument("--profile", help="OSRM profile (default from env)")
    args = parser.parse_args(argv)

    from apps.app import create_app

    app = create_app(os.getenv("FLASK_CONFIG", "default"))
    with app.app_context():
        summary = build_hazard_osm_edge_mapping(
            limit=args.limit,
            base_url=args.osrm_base_url,
            profile=args.profile,
        )
    print(f"attempted={summary['attempted']} updated={summary['updated']} missed={summary['missed']}")
    return summary


if __name__ == "__main__":
    hazard_edge_matcher_cli()

_OSRM_ARTIFACT_DIR = os.getenv("OSRM_DATA_DIR") or os.path.join(os.getcwd(), "osrm")
_OSRM_HAZARD_CSV = os.getenv("OSRM_HAZARD_CSV") or os.path.join(_OSRM_ARTIFACT_DIR, "hazard_penalties.csv")
_OSRM_HAZARD_LUA = os.getenv("OSRM_HAZARD_LUA") or os.path.join(_OSRM_ARTIFACT_DIR, "hazard_penalties.lua")


def _osrm_artifact_path(path_hint, fallback):
    path = os.path.abspath(path_hint or fallback)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    return path


def export_hazard_penalties_csv(csv_path=None):
    """
    Collapse active hazards into a CSV: edge_id,penalty
    Optimized for OSRM's customize step where Lua loads penalties from disk.
    """
    path = _osrm_artifact_path(csv_path, _OSRM_HAZARD_CSV)
    hazards = Hazard.query.filter_by(is_active=True).with_entities(
        Hazard.osm_edge_id, Hazard.edge_id, Hazard.weight_penalty, Hazard.danger_score
    ).all()

    penalties = {}
    for osm_edge_id, edge_id, weight_penalty, danger_score in hazards:
        edge = osm_edge_id or edge_id
        if not edge:
            continue
        penalty = weight_penalty or _penalty_from_danger(danger_score)
        if penalty > penalties.get(edge, 0.0):
            penalties[edge] = penalty

    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["edge_id", "penalty"])
        for edge, penalty in penalties.items():
            writer.writerow([edge, f"{penalty:.6f}"])
    return {"csv_path": path, "rows": len(penalties)}


def _hazard_lua_template(csv_path):
    csv_escaped = csv_path.replace("\\", "\\\\")
    return f"""-- Auto-generated by apps.route.views.export_hazard_penalties_csv
-- Loads hazard penalties from CSV for use inside a custom OSRM profile.
local hazard_penalties = {{}}
local csv_path = "{csv_escaped}"

local function load_from_csv()
  local fh = io.open(csv_path, "r")
  if not fh then
    return
  end
  fh:read("*l") -- skip header
  for line in fh:lines() do
    local edge, penalty = line:match("([^,]+),([^,]+)")
    if edge and penalty then
      hazard_penalties[edge] = tonumber(penalty) or 0
    end
  end
  fh:close()
end

load_from_csv()

-- Usage inside your OSRM Lua profile:
--   local hazards = require("hazard_penalties").penalties
--   local p = hazards[edge_id]
--   if p and result.weight then result.weight = result.weight * p end
return {{
  penalties = hazard_penalties,
  apply = function(edge_id, weight, duration)
    local p = hazard_penalties[edge_id]
    if not p then
      return weight, duration
    end
    if weight then weight = weight * p end
    if duration then duration = duration * p end
    return weight, duration
  end
}}
"""


def render_osrm_hazard_profile(csv_path=None, lua_path=None):
    """
    Emit a Lua helper that reads the hazard CSV and exposes penalty lookups.
    This file can be `require`d from a custom OSRM profile.
    """
    csv_abs = _osrm_artifact_path(csv_path, _OSRM_HAZARD_CSV)
    lua_abs = _osrm_artifact_path(lua_path, _OSRM_HAZARD_LUA)
    with open(lua_abs, "w") as fh:
        fh.write(_hazard_lua_template(csv_abs))
    return {"lua_path": lua_abs, "csv_path": csv_abs}


def export_osrm_hazard_artifacts(csv_path=None, lua_path=None):
    """
    Convenience helper to regenerate both the CSV and Lua helper together.
    """
    csv_meta = export_hazard_penalties_csv(csv_path)
    lua_meta = render_osrm_hazard_profile(csv_meta["csv_path"], lua_path)
    payload = {"hazard_rows": csv_meta["rows"], **csv_meta, **lua_meta}
    return payload
_OSRM_PROFILE_LUA = os.getenv("OSRM_PROFILE_LUA") or os.path.join(_OSRM_ARTIFACT_DIR, "car.lua")
_OSRM_PBF_PATH = os.getenv("OSRM_PBF_PATH") or os.path.join(_OSRM_ARTIFACT_DIR, "map.osm.pbf")
_OSRM_OSRM_PATH = os.getenv("OSRM_OSRM_PATH") or os.path.join(_OSRM_ARTIFACT_DIR, "map.osrm")
_OSRM_THREADS = int(os.getenv("OSRM_THREADS", "8"))
_OSRM_CUSTOMIZE_LOCK = threading.Lock()
_OSRM_CUSTOMIZE_RUNNING = False


def _run_osrm(cmd):
    proc = subprocess.run(
        cmd,
        cwd=_OSRM_ARTIFACT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def build_osrm_pipeline(pbf_path=None, profile_path=None, osrm_path=None, threads=None):
    """
    Run osrm-extract → osrm-partition → osrm-customize using current hazard data.
    """
    export_osrm_hazard_artifacts()
    profile = _osrm_artifact_path(profile_path, _OSRM_PROFILE_LUA)
    pbf = _osrm_artifact_path(pbf_path, _OSRM_PBF_PATH)
    osrm_file = _osrm_artifact_path(osrm_path, _OSRM_OSRM_PATH)
    t = threads or _OSRM_THREADS
    _run_osrm(["osrm-extract", "-p", profile, pbf])
    _run_osrm(["osrm-partition", osrm_file])
    _run_osrm(["osrm-customize", "-t", str(t), osrm_file])
    return {"pbf": pbf, "profile": profile, "osrm": osrm_file, "threads": t}


def trigger_osrm_customize(osrm_path=None, threads=None):
    """
    Fire-and-forget osrm-customize after regenerating hazard artifacts.
    Skips when a customize run is already in-flight.
    """
    osrm_file = _osrm_artifact_path(osrm_path, _OSRM_OSRM_PATH)
    if not os.path.exists(osrm_file):
        return False

    def _worker():
        global _OSRM_CUSTOMIZE_RUNNING
        with _OSRM_CUSTOMIZE_LOCK:
            if _OSRM_CUSTOMIZE_RUNNING:
                return
            _OSRM_CUSTOMIZE_RUNNING = True
        try:
            export_osrm_hazard_artifacts()
            _run_osrm([
                "osrm-customize",
                "-t",
                str(threads or _OSRM_THREADS),
                osrm_file,
            ])
        except Exception:
            pass
        finally:
            _OSRM_CUSTOMIZE_RUNNING = False

    threading.Thread(target=_worker, daemon=True).start()
    return True

class _CustomizeWorker:
    """
    Debounced background worker that coalesces hazard ingests and
    runs CSV regeneration + osrm-customize without overlapping runs.
    """
    def __init__(self, cooldown_sec=None):
        self.cooldown = float(cooldown_sec or os.getenv("OSRM_CUSTOMIZE_DEBOUNCE", "2.0"))
        self._event = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def poke(self):
        # Signal that new hazard data arrived; returns immediately.
        self._event.set()
        return True

    def _loop(self):
        while not self._stop.is_set():
            # Wait for a signal; poll so we can notice stop requests.
            if not self._event.wait(timeout=0.5):
                continue

            # Debounce: wait for a quiet period before running customize.
            self._event.clear()
            deadline = time.time() + self.cooldown
            while time.time() < deadline and not self._stop.is_set():
                if self._event.wait(timeout=0.1):
                    # Another poke arrived; extend quiet window.
                    self._event.clear()
                    deadline = time.time() + self.cooldown

            osrm_file = _osrm_artifact_path(None, _OSRM_OSRM_PATH)
            if not os.path.exists(osrm_file):
                continue

            try:
                # Refresh hazard artifacts before customize
                export_osrm_hazard_artifacts()

                # Ensure single customize at a time across processes
                global _OSRM_CUSTOMIZE_RUNNING
                with _OSRM_CUSTOMIZE_LOCK:
                    if _OSRM_CUSTOMIZE_RUNNING:
                        continue
                    _OSRM_CUSTOMIZE_RUNNING = True
                try:
                    _run_osrm(["osrm-customize", "-t", str(_OSRM_THREADS), osrm_file])
                finally:
                    _OSRM_CUSTOMIZE_RUNNING = False
            except Exception:
                # Intentionally swallow to keep worker alive
                pass

    def stop(self):
        self._stop.set()
        self._event.set()


# Eagerly start a singleton worker on import
_CUSTOMIZE_WORKER = _CustomizeWorker()


def schedule_osrm_customize():
    """Public helper to request a debounced customize run."""
    try:
        return _CUSTOMIZE_WORKER.poke()
    except Exception:
        return False


def _parse_point(point):
    """Convert incoming lat/lon dict to a normalized point."""
    if not isinstance(point, dict):
        return None
    lat = point.get("lat")
    lon = point.get("lon", point.get("lng"))
    if lat is None or lon is None:
        return None
    try:
        return {"lat": float(lat), "lon": float(lon)}
    except (TypeError, ValueError):
        return None

_HAZARD_CACHE = {"by_edge": {}, "last_refresh": 0.0}
_HAZARD_CACHE_TTL = 30  # seconds before reloading from DB
_RATE_LIMIT_BUCKET = {}
_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 20
_INTERPOLATE_STEPS = 12


def _rate_limited(key):
    """Cheap sliding-window limiter keyed by IP or user."""
    now = time.time()
    window = [ts for ts in _RATE_LIMIT_BUCKET.get(key, []) if now - ts < _RATE_LIMIT_WINDOW]
    if len(window) >= _RATE_LIMIT_MAX:
        _RATE_LIMIT_BUCKET[key] = window
        return True
    window.append(now)
    _RATE_LIMIT_BUCKET[key] = window
    return False


def _hazard_edge_id(hazard):
    return hazard.osm_edge_id or hazard.edge_id


def _penalty_from_danger(danger_score):
    """Map a danger score (0-10) into a weight penalty."""
    score = max(0.0, min(float(danger_score), 10.0))
    return 1.0 + score * score * 0.1


def _collapse_hazards(hazards):
    cache = {}
    for hazard in hazards:
        edge = _hazard_edge_id(hazard)
        if not edge:
            continue
        penalty = hazard.weight_penalty or _penalty_from_danger(hazard.danger_score)
        if penalty > cache.get(edge, 0.0):
            cache[edge] = penalty
    return cache


def _hydrate_cache_from_db():
    hazards = Hazard.query.filter_by(is_active=True).all()
    _HAZARD_CACHE["by_edge"] = _collapse_hazards(hazards)
    _HAZARD_CACHE["last_refresh"] = time.time()
    return _HAZARD_CACHE["by_edge"]


def _hazard_cache(force=False):
    if force or (time.time() - _HAZARD_CACHE["last_refresh"] > _HAZARD_CACHE_TTL):
        return _hydrate_cache_from_db()
    return _HAZARD_CACHE["by_edge"]


def _register_hazard_in_cache(hazard):
    edge = _hazard_edge_id(hazard)
    if not edge:
        return
    penalty = hazard.weight_penalty or _penalty_from_danger(hazard.danger_score)
    cache = _hazard_cache()
    if penalty > cache.get(edge, 0.0):
        cache[edge] = penalty
    _HAZARD_CACHE["by_edge"] = cache
    _HAZARD_CACHE["last_refresh"] = time.time()


def _haversine_km(p1, p2):
    radius_km = 6371.0088
    lat1, lon1 = math.radians(p1["lat"]), math.radians(p1["lon"])
    lat2, lon2 = math.radians(p2["lat"]), math.radians(p2["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _segment_edges(p1, p2, session=None, base_url=None, profile=None):
    edges = set()
    http = session or requests.Session()
    for step in range(_INTERPOLATE_STEPS + 1):
        t = step / _INTERPOLATE_STEPS
        lat = p1["lat"] + (p2["lat"] - p1["lat"]) * t
        lon = p1["lon"] + (p2["lon"] - p1["lon"]) * t
        edge = _match_osm_edge(lat, lon, session=http, base_url=base_url, profile=profile)
        if edge:
            edges.add(edge)
    return edges


def _collect_route_edges(points, base_url=None, profile=None):
    edges = set()
    if len(points) < 2:
        return edges
    session = requests.Session()
    for idx in range(len(points) - 1):
        edges.update(_segment_edges(points[idx], points[idx + 1], session=session, base_url=base_url, profile=profile))
    return edges


def _route_distance(points):
    return sum(_haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def _route_penalty(points, base_url=None, profile=None):
    edges = _collect_route_edges(points, base_url=base_url, profile=profile)
    cache = _hazard_cache()
    penalty = sum(cache.get(edge, 0.0) for edge in edges)
    return penalty, edges


def _parse_points_payload(data):
    start = _parse_point(data.get("start") or data.get("start_location"))
    end = _parse_point(data.get("end") or data.get("end_location"))
    raw_vias = data.get("vias") or data.get("waypoints") or []
    if raw_vias and not isinstance(raw_vias, list):
        return None, None, None

    vias = []
    for wp in raw_vias:
        parsed = _parse_point(wp)
        if not parsed:
            return None, None, None
        vias.append(parsed)

    return start, end, vias


@bp.post("/hazards")
def ingest_hazard():
    """Ingest a hazard point and keep active cache updated."""
    data = request.get_json(silent=True) or {}
    requester = request.remote_addr or "anon"
    if _rate_limited(requester):
        return jsonify({"error": "Rate limit exceeded"}), 429

    point = _parse_point(data)
    if not point:
        return jsonify({"error": "lat and lon are required"}), 400
    lat, lon = point["lat"], point["lon"]
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "lat/lon out of range"}), 400

    try:
        danger_score = float(data.get("danger_score", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "danger_score must be numeric"}), 400
    if not (0 <= danger_score <= 10):
        return jsonify({"error": "danger_score must be between 0 and 10"}), 400

    is_active = bool(data.get("is_active", True))
    osm_edge_id = _match_osm_edge(lat, lon)
    if not osm_edge_id:
        return jsonify({"error": "Unable to resolve hazard to an OSM edge"}), 503
    weight_penalty = _penalty_from_danger(danger_score)

    try:
        hazard = Hazard(
            lat=lat,
            lon=lon,
            danger_score=danger_score,
            is_active=is_active,
            edge_id=osm_edge_id,
            osm_edge_id=osm_edge_id,
            weight_penalty=weight_penalty,
        )
        db.session.add(hazard)
        db.session.commit()
        _register_hazard_in_cache(hazard)
        customize_started = schedule_osrm_customize()
        return jsonify({
            "message": "hazard ingested",
            "hazard": hazard.serialize(),
            "osrm_customizing": customize_started,
        }), 201
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to persist hazard: {str(exc)}"}), 400


@bp.get("/hazard/active")
def list_active_hazards():
    hazards = Hazard.query.filter_by(is_active=True).order_by(Hazard.updated_at.desc()).limit(500).all()
    return jsonify({"hazards": [h.serialize() for h in hazards]}), 200


@bp.post("/hazard/refresh")
def refresh_hazard_cache():
    cache = _hazard_cache(force=True)
    return jsonify({"message": "hazard cache refreshed", "active_edges": len(cache)}), 200


@bp.post("/hazard/map-osm-edges")
def map_hazards_to_osm_edges():
    """Backfill or refresh hazard edge IDs using OSRM nearest lookups."""
    payload = request.get_json(silent=True) or {}
    limit = payload.get("limit") or 1000
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

    summary = build_hazard_osm_edge_mapping(
        limit=limit,
        base_url=payload.get("osrm_base_url"),
        profile=payload.get("profile"),
    )
    return jsonify({"message": "hazard edges mapped", **summary}), 200


@bp.post("/route/safe")
def safe_route():
    """Compute a hazard-aware route by querying OSRM, decoding geometry, mapping to edges, and applying penalties."""
    data = request.get_json(silent=True) or {}
    start, end, vias = _parse_points_payload(data)
    if not start or not end:
        return jsonify({"error": "start and end are required"}), 400

    def _osrm_route(points, base_url=None, profile=None):
        base = (base_url or os.getenv("OSRM_BASE_URL") or "http://localhost:5000").rstrip("/")
        prof = profile or os.getenv("OSRM_PROFILE") or "driving"
        coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
        url = f"{base}/route/v1/{prof}/{coords}"
        params = {"overview": "full", "geometries": "geojson"}
        try:
            resp = requests.get(url, params=params, timeout=3.0)
            if resp.status_code != 200:
                return None
            payload = resp.json()
        except Exception:
            return None
        routes = payload.get("routes") or []
        if not routes:
            return None
        r0 = routes[0]
        geom = (r0.get("geometry") or {}).get("coordinates") or []
        return {
            "distance_m": float(r0.get("distance") or 0.0),
            "duration_s": float(r0.get("duration") or 0.0),
            "coords": geom,  # list of [lon, lat]
        }

    def _sample_indices(n, max_samples=60):
        if n <= 0:
            return []
        if n <= max_samples:
            return list(range(n))
        step = max(1, n // max_samples)
        idx = list(range(0, n, step))
        if idx[-1] != n - 1:
            idx.append(n - 1)
        return idx

    def _edges_from_geometry(coords, base_url=None, profile=None, max_samples=60):
        if not coords:
            return set()
        session = requests.Session()
        edges = set()
        for i in _sample_indices(len(coords), max_samples=max_samples):
            lon, lat = coords[i][0], coords[i][1]
            edge = _match_osm_edge(lat, lon, session=session, base_url=base_url, profile=profile)
            if edge:
                edges.add(edge)
        return edges

    points = [start, *vias, end]
    osrm_meta = _osrm_route(points, base_url=data.get("osrm_base_url"), profile=data.get("profile"))
    if not osrm_meta:
        return jsonify({"error": "OSRM route unavailable"}), 502

    coords = osrm_meta["coords"]
    edges = _edges_from_geometry(coords, base_url=data.get("osrm_base_url"), profile=data.get("profile"), max_samples=60)
    cache = _hazard_cache()
    hazard_penalty = sum(cache.get(edge, 0.0) for edge in edges)
    distance_km = (osrm_meta["distance_m"] or 0.0) / 1000.0
    travel_weight = distance_km + hazard_penalty

    return jsonify({
        "route": {
            "points": points,
            "distance_km": round(distance_km, 4),
            "duration_s": round(osrm_meta["duration_s"], 2),
            "hazard_penalty": round(hazard_penalty, 4),
            "travel_weight": round(travel_weight, 4),
            "edges_considered": len(edges),
            "mode": data.get("mode", "safe"),
        },
        "hazard_overlay": [
            {"edge_id": edge, "penalty": cache.get(edge, 0.0)}
            for edge in edges
            if cache.get(edge, 0.0) > 0
        ],
    }), 200

@bp.post("/navigate")
def navigate():
    try:
        data = request.get_json()
        
        start, end, vias = split_points(data)
        profile = data.get("profile", "driving")

        if not all([start, end, vias]):
            return jsonify({"error": "start_lat, start_lon, end_lat, end_lon are required"}), 400
        
        # TODO: Integrate with OSRM or other routing service
        return jsonify({
            "message": "OSRM integration pending",
            "route": {
                "start": {"lat": start[0], "lon": start[1]},
                "end": {"lat": end[0], "lon": end[1]},
                "profile": profile
            }
        }), 501
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/paths")
@jwt_required()
def get_my_paths():
    """Get current user's saved paths"""
    user_id = get_jwt_identity()
    paths = MyPath.query.filter_by(user_id=user_id).order_by(MyPath.created_at.desc()).all()
    return jsonify({"paths": [p.serialize() for p in paths]}), 200


@bp.post("/paths")
@jwt_required()
def save_path():
    """
    Save a navigation path
    JSON body:
        - name: Required
        - start_location: Required {lat, lon}
        - end_location: Required {lat, lon}
        - waypoints: Optional array of {lat, lon}
    """
    data = request.get_json() or {}
    user_id = get_jwt_identity()

    name = data.get("name")
    start_point = _parse_point(data.get("start_location"))
    end_point = _parse_point(data.get("end_location"))
    waypoints_raw = data.get("waypoints") or []

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not start_point or not end_point:
        return jsonify({"error": "start_location and end_location are required"}), 400
    if waypoints_raw and not isinstance(waypoints_raw, list):
        return jsonify({"error": "waypoints must be a list"}), 400

    waypoints = []
    for wp in waypoints_raw:
        parsed = _parse_point(wp)
        if not parsed:
            return jsonify({"error": "Invalid waypoint format"}), 400
        waypoints.append(parsed)

    points = [start_point, *waypoints, end_point]

    try:
        path = MyPath(user_id=user_id, path_name=name, points=points)
        db.session.add(path)
        db.session.commit()
        return jsonify({"message": "Path saved", "path": path.serialize()}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to save path: {str(e)}"}), 400


@bp.get("/paths/<int:path_id>")
@jwt_required()
def get_path(path_id):
    """Get specific saved path details"""
    user_id = get_jwt_identity()
    path = MyPath.query.filter_by(path_id=path_id, user_id=user_id).first()
    if not path:
        return jsonify({"error": "Path not found"}), 404
    return jsonify({"path": path.serialize()}), 200


@bp.put("/paths/<int:path_id>")
@jwt_required()
def update_path(path_id):
    """Update a saved path"""
    user_id = get_jwt_identity()
    path = MyPath.query.filter_by(path_id=path_id, user_id=user_id).first()
    if not path:
        return jsonify({"error": "Path not found"}), 404

    data = request.get_json() or {}
    name = data.get("name", path.path_name)

    update_points = any(key in data for key in ["start_location", "end_location", "waypoints"])
    points = path.points

    if update_points:
        start_point = _parse_point(data.get("start_location")) or path.points[0]
        end_point = _parse_point(data.get("end_location")) or path.points[-1]
        waypoint_data = data.get("waypoints", path.points[1:-1]) or []

        if not isinstance(waypoint_data, list):
            return jsonify({"error": "waypoints must be a list"}), 400

        waypoints = []
        for wp in waypoint_data:
            parsed = _parse_point(wp)
            if not parsed:
                return jsonify({"error": "Invalid waypoint format"}), 400
            waypoints.append(parsed)

        points = [start_point, *waypoints, end_point]

    try:
        path.path_name = name
        path.points = points
        db.session.commit()
        return jsonify({"message": "Path updated", "path": path.serialize()}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update path: {str(e)}"}), 400


@bp.delete("/paths/<int:path_id>")
@jwt_required()
def delete_path(path_id):
    """Delete a saved path"""
    user_id = get_jwt_identity()
    path = MyPath.query.filter_by(path_id=path_id, user_id=user_id).first()
    if not path:
        return jsonify({"error": "Path not found"}), 404

    try:
        db.session.delete(path)
        db.session.commit()
        return jsonify({"message": "Path deleted"}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete path: {str(e)}"}), 400
