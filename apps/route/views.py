"""
Route module - Navigation and routing
"""

import math
import os
import time
import requests
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from apps.config.server import db
from apps.route.hazard_pipeline import penalty_from_danger, schedule_osrm_customize
from apps.route.models import Hazard, MyPath, TrafficHazard

bp = Blueprint("route", __name__)


@bp.get("/api_info")
def api_info():
    """
    경로 API 정보 제공 (개발용)
    """
    info = {
        "module": "route",
        "base_path": "/route",
        "description": "경로 탐색 및 위험 지역 관리",
        "endpoints": [
            {
                "path": "/route",
                "method": "POST",
                "auth_required": False,
                "description": "경로 탐색",
                "json_body": {
                    "start": "시작 좌표 [lat, lon]",
                    "end": "종료 좌표 [lat, lon]",
                    "vias": "경유지 좌표 배열 (선택)",
                },
            },
            {
                "path": "/route/hazard",
                "method": "POST",
                "auth_required": True,
                "description": "위험 지역 등록",
            },
            {
                "path": "/route/hazard",
                "method": "GET",
                "auth_required": False,
                "description": "위험 지역 목록 조회",
            },
            {
                "path": "/route/mypath",
                "method": "POST",
                "auth_required": True,
                "description": "내 경로 저장",
            },
            {
                "path": "/route/mypath",
                "method": "GET",
                "auth_required": True,
                "description": "내 경로 목록 조회",
            },
            {
                "path": "/route/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


def _split_points(s):
    pts = [
        list(map(float, p.split(","))) for p in s.strip("()").split(";") if p.strip()
    ]

    if not pts:
        return {"start": None, "end": None, "vias": []}

    start = pts[0]
    end = pts[-1] if len(pts) > 1 else None
    vias = pts[1:-1] if len(pts) > 2 else []

    return {"start": start, "end": end, "vias": vias}


def _match_osm_edge(lat, lon, session=None, base_url=None, profile=None):
    """
    Resolve the nearest OSM edge for a hazard point using OSRM `nearest`.
    Falls back to None if OSRM is unavailable.
    """
    http = session or requests.Session()
    base = (base_url or os.getenv("OSRM_BASE_URL") or "http://localhost:5000").rstrip(
        "/"
    )
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
        edge = _match_osm_edge(
            hazard.lat, hazard.lon, session=session, base_url=base_url, profile=profile
        )
        if not edge:
            misses += 1
            continue
        current_edge = hazard.osm_edge_id or hazard.edge_id
        if current_edge != edge:
            updates.append(
                {"hazard_id": hazard.hazard_id, "edge_id": edge, "osm_edge_id": edge}
            )

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
    parser.add_argument(
        "--limit", type=int, default=1000, help="Maximum hazards to process"
    )
    parser.add_argument(
        "--osrm-base-url", dest="osrm_base_url", help="Override OSRM base URL"
    )
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
    print(
        f"attempted={summary['attempted']} updated={summary['updated']} missed={summary['missed']}"
    )
    return summary


if __name__ == "__main__":
    hazard_edge_matcher_cli()


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
_HAZARD_DEFAULT_PAGE = 1
_HAZARD_DEFAULT_PER_PAGE = 50
_HAZARD_MAX_PER_PAGE = 200


def _rate_limited(key):
    """Cheap sliding-window limiter keyed by IP or user."""
    now = time.time()
    window = [
        ts for ts in _RATE_LIMIT_BUCKET.get(key, []) if now - ts < _RATE_LIMIT_WINDOW
    ]
    if len(window) >= _RATE_LIMIT_MAX:
        _RATE_LIMIT_BUCKET[key] = window
        return True
    window.append(now)
    _RATE_LIMIT_BUCKET[key] = window
    return False


def _hazard_edge_id(hazard):
    return hazard.osm_edge_id or hazard.edge_id


def _collapse_hazards(hazards, traffic_entries=None):
    cache = {}
    for hazard in hazards:
        edge = _hazard_edge_id(hazard)
        if not edge:
            continue
        penalty = hazard.weight_penalty or penalty_from_danger(hazard.danger_score)
        if penalty > cache.get(edge, 0.0):
            cache[edge] = penalty
    if traffic_entries:
        for entry in traffic_entries:
            edge = entry.osm_edge_id
            if not edge:
                continue
            penalty = entry.penalty or 0.0
            if penalty > cache.get(edge, 0.0):
                cache[edge] = penalty
    return cache


def _hydrate_cache_from_db():
    hazards = Hazard.query.filter_by(is_active=True).all()
    cutoff = datetime.now() - timedelta(minutes=5)
    traffic_entries = TrafficHazard.query.filter(
        TrafficHazard.updated_at >= cutoff
    ).all()
    _HAZARD_CACHE["by_edge"] = _collapse_hazards(hazards, traffic_entries)
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
    penalty = hazard.weight_penalty or penalty_from_danger(hazard.danger_score)
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
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _segment_edges(p1, p2, session=None, base_url=None, profile=None):
    edges = set()
    http = session or requests.Session()
    for step in range(_INTERPOLATE_STEPS + 1):
        t = step / _INTERPOLATE_STEPS
        lat = p1["lat"] + (p2["lat"] - p1["lat"]) * t
        lon = p1["lon"] + (p2["lon"] - p1["lon"]) * t
        edge = _match_osm_edge(
            lat, lon, session=http, base_url=base_url, profile=profile
        )
        if edge:
            edges.add(edge)
    return edges


def _collect_route_edges(points, base_url=None, profile=None):
    edges = set()
    if len(points) < 2:
        return edges
    session = requests.Session()
    for idx in range(len(points) - 1):
        edges.update(
            _segment_edges(
                points[idx],
                points[idx + 1],
                session=session,
                base_url=base_url,
                profile=profile,
            )
        )
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


def _hazard_to_pin(hazard):
    raw = hazard.serialize() if hasattr(hazard, "serialize") else {}
    hazard_type = (
        getattr(hazard, "hazard_type", None) or raw.get("hazard_type") or "hazard"
    )
    return {
        "id": (
            hazard.hazard_id if hasattr(hazard, "hazard_id") else raw.get("hazard_id")
        ),
        "hazardId": (
            hazard.hazard_id if hasattr(hazard, "hazard_id") else raw.get("hazard_id")
        ),
        "lat": getattr(hazard, "lat", None),
        "lng": getattr(hazard, "lon", None),
        "description": raw.get("description"),
        "type": hazard_type,
        "dangerScore": raw.get("danger_score"),
        "source": "hazard",
        "createdAt": raw.get("created_at"),
        "updatedAt": raw.get("updated_at"),
        "raw": raw,
    }


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
    weight_penalty = penalty_from_danger(danger_score)

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
        return (
            jsonify(
                {
                    "message": "hazard ingested",
                    "hazard": hazard.serialize(),
                    "pin": _hazard_to_pin(hazard),
                    "osrm_customizing": customize_started,
                }
            ),
            201,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to persist hazard: {str(exc)}"}), 400


@bp.get("/hazards")
def list_hazards():
    """Return normalized hazard pins with min_score filtering."""
    try:
        min_score = float(request.args.get("min_score", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "min_score must be a number"}), 400
    try:
        page = max(int(request.args.get("page", _HAZARD_DEFAULT_PAGE)), 1)
    except (TypeError, ValueError):
        page = _HAZARD_DEFAULT_PAGE
    try:
        per_page = int(request.args.get("per_page", _HAZARD_DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = _HAZARD_DEFAULT_PER_PAGE
    per_page = max(1, min(per_page, _HAZARD_MAX_PER_PAGE))

    query = Hazard.query.filter(Hazard.is_active.is_(True))
    if min_score > 0:
        query = query.filter(Hazard.danger_score >= min_score)

    total = query.count()
    hazards = (
        query.order_by(Hazard.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    results = [_hazard_to_pin(h) for h in hazards]
    meta = {"page": page, "per_page": per_page, "total": total}
    return jsonify({"results": results, "meta": meta}), 200


@bp.put("/hazards/<int:hazard_id>")
def update_hazard(hazard_id):
    """Update an existing hazard record and refresh caches."""
    hazard = Hazard.query.get(hazard_id)
    if not hazard:
        return jsonify({"error": "hazard_not_found"}), 404

    data = request.get_json(silent=True) or {}
    updated = False

    if "danger_score" in data:
        try:
            danger_score = float(data.get("danger_score"))
        except (TypeError, ValueError):
            return jsonify({"error": "danger_score must be numeric"}), 400
        if not (0 <= danger_score <= 10):
            return jsonify({"error": "danger_score must be between 0 and 10"}), 400
        hazard.danger_score = danger_score
        hazard.weight_penalty = penalty_from_danger(danger_score)
        updated = True

    if "is_active" in data:
        hazard.is_active = bool(data.get("is_active"))
        updated = True

    if not updated:
        return jsonify({"message": "no_changes"}), 200

    try:
        db.session.commit()
        _hazard_cache(force=True)
        schedule_osrm_customize()
        return (
            jsonify({"hazard": hazard.serialize(), "pin": _hazard_to_pin(hazard)}),
            200,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to update hazard: {str(exc)}"}), 400


@bp.delete("/hazards/<int:hazard_id>")
def delete_hazard(hazard_id):
    """Soft-delete a hazard by deactivating it."""
    hazard = Hazard.query.get(hazard_id)
    if not hazard:
        return jsonify({"error": "hazard_not_found"}), 404

    if not hazard.is_active:
        return jsonify({"message": "already_inactive"}), 200

    hazard.is_active = False
    try:
        db.session.commit()
        _hazard_cache(force=True)
        schedule_osrm_customize()
        return (
            jsonify(
                {
                    "message": "hazard_deactivated",
                    "hazard": hazard.serialize(),
                    "pin": _hazard_to_pin(hazard),
                }
            ),
            200,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to deactivate hazard: {str(exc)}"}), 400


@bp.get("/hazard/active")
def list_active_hazards():
    hazards = (
        Hazard.query.filter_by(is_active=True)
        .order_by(Hazard.updated_at.desc())
        .limit(500)
        .all()
    )
    pins = [_hazard_to_pin(h) for h in hazards]
    return jsonify({"results": pins, "total": len(pins)}), 200


@bp.post("/hazard/refresh")
def refresh_hazard_cache():
    cache = _hazard_cache(force=True)
    return (
        jsonify({"message": "hazard cache refreshed", "active_edges": len(cache)}),
        200,
    )


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
        base = (
            base_url or os.getenv("OSRM_BASE_URL") or "http://localhost:5000"
        ).rstrip("/")
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
            edge = _match_osm_edge(
                lat, lon, session=session, base_url=base_url, profile=profile
            )
            if edge:
                edges.add(edge)
        return edges

    points = [start, *vias, end]
    osrm_meta = _osrm_route(
        points, base_url=data.get("osrm_base_url"), profile=data.get("profile")
    )
    if not osrm_meta:
        return jsonify({"error": "OSRM route unavailable"}), 502

    coords = osrm_meta["coords"]
    edges = _edges_from_geometry(
        coords,
        base_url=data.get("osrm_base_url"),
        profile=data.get("profile"),
        max_samples=60,
    )
    cache = _hazard_cache()
    hazard_penalty = sum(cache.get(edge, 0.0) for edge in edges)
    distance_km = (osrm_meta["distance_m"] or 0.0) / 1000.0
    travel_weight = distance_km + hazard_penalty

    return (
        jsonify(
            {
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
            }
        ),
        200,
    )


@bp.post("/navigate")
def navigate():
    try:
        data = request.get_json()

        start, end, vias = _split_points(data)
        profile = data.get("profile", "driving")

        if not all([start, end, vias]):
            return (
                jsonify(
                    {"message": "start_lat, start_lon, end_lat, end_lon are required"}
                ),
                400,
            )

        # TODO: Integrate with OSRM or other routing service
        return (
            jsonify(
                {
                    "message": "OSRM integration pending",
                    "route": {
                        "start": {"lat": start[0], "lon": start[1]},
                        "end": {"lat": end[0], "lon": end[1]},
                        "profile": profile,
                    },
                }
            ),
            501,
        )

    except Exception as e:
        return jsonify({"message": str(e)}), 400


@bp.get("/paths")
@jwt_required()
def get_my_paths():
    """Get current user's saved paths"""
    user_id = get_jwt_identity()
    paths = (
        MyPath.query.filter_by(user_id=user_id).order_by(MyPath.created_at.desc()).all()
    )
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

    update_points = any(
        key in data for key in ["start_location", "end_location", "waypoints"]
    )
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
