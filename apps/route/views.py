"""
Route module - Navigation and routing
"""

import json
import math
import os
import time
import requests
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from apps.config.server import db
from apps.config.common import Config
from apps.hazard.models import Hazard
from apps.hazard.score_util import calculate_danger_score_from_detection
from apps.route.hazard_pipeline import penalty_from_danger, schedule_osrm_customize
from apps.route.models import Route, TrafficHazard
from apps.detector.detection_utils import get_ai_server_client
from apps.roadview.models import RoadviewProvider, RoadviewStatus, init_models

# Initialize roadview models (will be set up when app context is available)
Roadview = None
RoadviewCache = None
RoadviewRequest = None
RoadviewAPIUsage = None


def init_roadview_models_for_route(db):
    """Initialize roadview models with db instance"""
    global Roadview, RoadviewCache, RoadviewRequest, RoadviewAPIUsage
    Roadview, RoadviewCache, RoadviewRequest, RoadviewAPIUsage = init_models(db)


bp = Blueprint("route", __name__)


@bp.get("/api_info")
def api_info():
    """
    경로 API 정보 제공 (개발용)
    """
    info_path = os.path.join(os.path.dirname(__file__), "info.json")
    with open(info_path, "r", encoding="utf-8") as f:
        info = json.load(f)
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

        # Only trigger OSRM customize if we have a valid edge mapping
        customize_started = False
        if osm_edge_id:
            customize_started = schedule_osrm_customize()

        return (
            jsonify(
                {
                    "message": "hazard ingested",
                    "hazard": hazard.serialize(),
                    "pin": _hazard_to_pin(hazard),
                    "osrm_customizing": customize_started,
                    "osm_edge_matched": bool(osm_edge_id),
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


@bp.post("/safe")
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
def get_saved_routes():
    """현재 로그인한 사용자의 저장 경로 목록을 반환"""

    user_id = get_jwt_identity()
    routes = (
        Route.query.filter_by(user_id=user_id).order_by(Route.created_at.desc()).all()
    )
    payload = [route.serialize() for route in routes]
    # paths 키는 기존 클라이언트 호환을 위해 유지한다.
    return jsonify({"routes": payload, "paths": payload}), 200


@bp.post("/paths")
@jwt_required()
def save_route():
    """새 경로 저장 (이전 paths API 호환 유지)."""

    data = request.get_json() or {}
    user_id = get_jwt_identity()

    name = (data.get("name") or "").strip()
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
        route = Route(user_id=user_id, name=name, points=points)
        db.session.add(route)
        db.session.commit()
        serialized = route.serialize()
        return (
            jsonify(
                {"message": "Route saved", "route": serialized, "path": serialized}
            ),
            201,
        )
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to save route: {str(e)}"}), 400


@bp.get("/paths/<int:route_id>")
@jwt_required()
def get_route(route_id):
    """저장된 단일 경로 상세 조회"""

    user_id = get_jwt_identity()
    route = Route.query.filter_by(route_id=route_id, user_id=user_id).first()
    if not route:
        return jsonify({"error": "Route not found"}), 404
    serialized = route.serialize()
    return jsonify({"route": serialized, "path": serialized}), 200


@bp.put("/paths/<int:route_id>")
@jwt_required()
def update_route(route_id):
    """저장된 경로 수정"""

    user_id = get_jwt_identity()
    route = Route.query.filter_by(route_id=route_id, user_id=user_id).first()
    if not route:
        return jsonify({"error": "Route not found"}), 404

    data = request.get_json() or {}
    name = (data.get("name") or route.name).strip()

    update_points = any(
        key in data for key in ["start_location", "end_location", "waypoints"]
    )
    points = route.points

    if update_points:
        start_point = _parse_point(data.get("start_location")) or route.points[0]
        end_point = _parse_point(data.get("end_location")) or route.points[-1]
        waypoint_data = data.get("waypoints", route.points[1:-1]) or []

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
        route.name = name
        route.points = points
        db.session.commit()
        serialized = route.serialize()
        return (
            jsonify(
                {"message": "Route updated", "route": serialized, "path": serialized}
            ),
            200,
        )
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update route: {str(e)}"}), 400


@bp.delete("/paths/<int:route_id>")
@jwt_required()
def delete_route(route_id):
    """저장된 경로 삭제"""

    user_id = get_jwt_identity()
    route = Route.query.filter_by(route_id=route_id, user_id=user_id).first()
    if not route:
        return jsonify({"error": "Route not found"}), 404

    try:
        db.session.delete(route)
        db.session.commit()
        return jsonify({"message": "Route deleted"}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete route: {str(e)}"}), 400


# ============================================================================
# Route Analysis Utilities
# ============================================================================


def _calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate bearing (heading) from point 1 to point 2 in degrees (0-360).

    Args:
        lat1, lon1: Starting point coordinates
        lat2, lon2: Ending point coordinates

    Returns:
        Bearing in degrees (0-360, where 0 is North)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    diff_lon = math.radians(lon2 - lon1)

    x = math.sin(diff_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(diff_lon)

    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    bearing = (initial_bearing + 360) % 360

    return bearing


def _haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on earth in meters.

    Args:
        lat1, lon1: Starting point coordinates
        lat2, lon2: Ending point coordinates

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def _interpolate_segment(start_lat, start_lon, end_lat, end_lon, interval_meters=50):
    """
    Generate intermediate points between start and end at regular intervals.

    Args:
        start_lat, start_lon: Starting point coordinates
        end_lat, end_lon: Ending point coordinates
        interval_meters: Distance between points in meters (default 50m)

    Returns:
        List of (lat, lon, heading) tuples
    """
    points = []

    # Calculate total distance
    total_distance = _haversine_distance(start_lat, start_lon, end_lat, end_lon)

    # Calculate number of segments
    if total_distance <= interval_meters:
        # If segment is shorter than interval, just use start and end
        heading = _calculate_bearing(start_lat, start_lon, end_lat, end_lon)
        return [(start_lat, start_lon, heading), (end_lat, end_lon, heading)]

    num_points = int(total_distance / interval_meters) + 1

    # Generate points
    for i in range(num_points):
        ratio = i / (num_points - 1) if num_points > 1 else 0

        # Linear interpolation (good enough for short distances)
        lat = start_lat + (end_lat - start_lat) * ratio
        lon = start_lon + (end_lon - start_lon) * ratio

        # Calculate heading
        heading = _calculate_bearing(start_lat, start_lon, end_lat, end_lon)

        points.append((lat, lon, heading))

    return points


def _get_roadview_image(
    lat,
    lon,
    heading,
    tag="default",
    image_age_years=10,
    request_age_years=1,
    force_refresh=False,
):
    """
    Download roadview image from Google Street View API with caching.

    Caching Strategy:
    - Check if roadview exists in database for this location (rounded to ~10m precision)
    - If cached and recent enough, reuse existing image file
    - If cached but old (image > 10 years or last request > 1 year), refresh
    - If not cached or force_refresh, fetch from API

    Args:
        lat: Latitude
        lon: Longitude
        heading: Direction in degrees (0-360)
        tag: Tag for organizing images (default "default")
        image_age_years: Max age of captured image before refresh (default 10 years)
        request_age_years: Max age of last request before refresh (default 1 year)
        force_refresh: Force API call even if cached (default False)

    Returns:
        dict: {
            "success": bool,
            "file_path": str,
            "error": str,
            "cached": bool,
            "cache_age_days": int
        }
    """
    api_key = Config.GOOGLE_MAPS_API_KEY
    if not api_key:
        return {"success": False, "error": "Google Maps API key not configured"}

    # Create directory
    save_dir = os.path.join("static", "roadviews", tag)
    os.makedirs(save_dir, exist_ok=True)

    # Generate filename
    filename = f"roadview_{lat:.6f}_{lon:.6f}_{int(heading)}.jpg"
    file_path = os.path.join(save_dir, filename)

    # Round coordinates for cache lookup (~10m precision)
    lat_rounded = round(lat, 4)
    lon_rounded = round(lon, 4)
    heading_rounded = int(heading)

    # Check cache if not forcing refresh
    if not force_refresh:
        try:
            cached_roadview = (
                Roadview.query.filter(
                    Roadview.latitude.between(
                        lat_rounded - 0.0001, lat_rounded + 0.0001
                    ),
                    Roadview.longitude.between(
                        lon_rounded - 0.0001, lon_rounded + 0.0001
                    ),
                    Roadview.heading.between(heading_rounded - 5, heading_rounded + 5),
                    Roadview.provider == RoadviewProvider.GOOGLE_STREET_VIEW,
                    Roadview.status == RoadviewStatus.AVAILABLE,
                )
                .order_by(Roadview.created_at.desc())
                .first()
            )

            if cached_roadview:
                # Check if cache needs refresh
                needs_refresh = Roadview.needs_refresh(
                    cached_roadview.image_date,
                    cached_roadview.created_at,
                    image_age_years=image_age_years,
                    request_age_years=request_age_years,
                )

                if not needs_refresh:
                    # Check if file still exists
                    cached_file = None
                    if cached_roadview.thumbnail_url:
                        # Extract file path from URL (format: /static/roadviews/...)
                        cached_file = cached_roadview.thumbnail_url.lstrip("/")

                    if cached_file and os.path.exists(cached_file):
                        # Use cached file
                        cache_age = (datetime.now() - cached_roadview.created_at).days
                        return {
                            "success": True,
                            "file_path": cached_file,
                            "size": os.path.getsize(cached_file),
                            "cached": True,
                            "cache_age_days": cache_age,
                            "roadview_id": cached_roadview.roadview_id,
                        }
        except Exception as cache_error:
            # If cache check fails, continue to API call
            pass

    # Fetch from Google Street View API
    # First, get metadata to check availability and image date
    metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    metadata_params = {"location": f"{lat},{lon}", "key": api_key, "source": "outdoor"}

    try:
        metadata_response = requests.get(
            metadata_url, params=metadata_params, timeout=10
        )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()

        if metadata.get("status") != "OK":
            # Save negative cache result
            try:
                roadview_record = Roadview(
                    latitude=lat,
                    longitude=lon,
                    heading=heading,
                    provider=RoadviewProvider.GOOGLE_STREET_VIEW,
                    status=RoadviewStatus.NOT_AVAILABLE,
                    error_message=f"Street View not available: {metadata.get('status')}",
                )
                db.session.add(roadview_record)
                db.session.commit()
            except:
                db.session.rollback()

            return {
                "success": False,
                "error": "No Street View available at this location",
                "cached": False,
            }

        # Extract metadata
        pano_id = metadata.get("pano_id")
        image_date_str = metadata.get("date")  # Format: YYYY-MM
        actual_location = metadata.get("location", {})

        # Parse image date
        image_date = None
        if image_date_str:
            try:
                # Parse YYYY-MM format
                image_date = datetime.strptime(
                    image_date_str + "-01", "%Y-%m-%d"
                ).date()
            except:
                pass

        # Download image
        image_url = "https://maps.googleapis.com/maps/api/streetview"
        image_params = {
            "size": "640x640",
            "location": f"{lat},{lon}",
            "heading": int(heading),
            "pitch": 0,
            "fov": 90,
            "key": api_key,
        }

        image_response = requests.get(image_url, params=image_params, timeout=10)

        if image_response.status_code == 200 and len(image_response.content) > 5000:
            # Save image
            with open(file_path, "wb") as f:
                f.write(image_response.content)

            # Save to database cache
            try:
                roadview_record = Roadview(
                    latitude=actual_location.get("lat", lat),
                    longitude=actual_location.get("lng", lon),
                    heading=heading,
                    pitch=0,
                    fov=90,
                    provider=RoadviewProvider.GOOGLE_STREET_VIEW,
                    status=RoadviewStatus.AVAILABLE,
                    pano_id=pano_id,
                    image_date=image_date,
                    thumbnail_url=f"/{file_path}",
                    image_width=640,
                    image_height=640,
                    provider_data=metadata,
                )
                db.session.add(roadview_record)
                db.session.commit()
            except Exception as db_error:
                db.session.rollback()
                # Continue even if DB save fails

            return {
                "success": True,
                "file_path": file_path,
                "size": len(image_response.content),
                "cached": False,
                "image_date": image_date_str,
                "pano_id": pano_id,
            }
        else:
            return {
                "success": False,
                "error": f"Failed to download image: HTTP {image_response.status_code}",
                "cached": False,
            }

    except Exception as e:
        return {"success": False, "error": str(e), "cached": False}


def _analyze_roadview_with_detector(image_path):
    """
    Send roadview image to detector service for analysis.

    Args:
        image_path: Path to the roadview image

    Returns:
        dict: {"success": bool, "result": dict, "result_image_path": str, "error": str}
    """
    import base64
    import requests as http_requests

    # AI 서버 URL
    AI_SERVER_URL = os.getenv("AI_SERVER_OBJECT_URL", "http://192.168.1.79:8888")

    try:
        # Read image
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Get detector client
        ai_client = get_ai_server_client("object")

        # Perform detection
        result = ai_client.detect_objects(image_data, confidence=0.5)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        # Save analyzed image if detector returns it
        result_image_path = None

        # Check for annotated_img in response (new format: path to fetch from /image endpoint)
        annotated_img = result.get("annotated_img")
        if annotated_img and isinstance(annotated_img, dict):
            # annotated_img = {"image.jpg": "static/result/image.jpg"}
            # Get the first value (there's only one image)
            remote_path = list(annotated_img.values())[0] if annotated_img else None

            if remote_path:
                try:
                    # Fetch annotated image from AI server
                    img_response = http_requests.get(
                        f"{AI_SERVER_URL}/image",
                        params={"filename": remote_path},
                        timeout=30,
                    )

                    if img_response.status_code == 200 and img_response.headers.get(
                        "Content-Type", ""
                    ).startswith("image"):
                        # Generate analyzed image path
                        dir_path = os.path.dirname(image_path)
                        filename = os.path.basename(image_path)
                        analyzed_filename = filename.replace("roadview_", "analyzed_")
                        result_image_path = os.path.join(dir_path, analyzed_filename)

                        # Save analyzed image
                        with open(result_image_path, "wb") as f:
                            f.write(img_response.content)
                except Exception as img_fetch_error:
                    # Log but don't fail the whole operation
                    current_app.logger.warning(
                        f"Failed to fetch annotated image: {img_fetch_error}"
                    )

        # Fallback: check for base64 encoded image (old format)
        if not result_image_path:
            annotated_image_b64 = result.get("annotated_image") or result.get(
                "result_image"
            )
            if annotated_image_b64:
                try:
                    # Decode base64 image
                    image_bytes = base64.b64decode(annotated_image_b64)

                    # Generate analyzed image path
                    dir_path = os.path.dirname(image_path)
                    filename = os.path.basename(image_path)
                    analyzed_filename = filename.replace("roadview_", "analyzed_")
                    result_image_path = os.path.join(dir_path, analyzed_filename)

                    # Save analyzed image
                    with open(result_image_path, "wb") as f:
                        f.write(image_bytes)
                except Exception as img_save_error:
                    # Log but don't fail the whole operation
                    current_app.logger.warning(
                        f"Failed to save base64 annotated image: {img_save_error}"
                    )

        # Convert AI server response format to standard detections format
        # AI server returns: {"results": {"image.jpg": [{"box": [...], "confidence": float, "label": str}]}}
        # We need: {"detections": [{"class": str, "confidence": float, "bbox": {...}}]}
        detections = []
        results_data = result.get("results", {})
        if isinstance(results_data, dict):
            for filename, objects in results_data.items():
                if isinstance(objects, list):
                    for obj in objects:
                        box = obj.get("box", [])
                        detection = {
                            "class": obj.get("label", "unknown"),
                            "confidence": obj.get("confidence", 0.5),
                        }
                        if len(box) >= 4:
                            detection["bbox"] = {
                                "x": box[0],
                                "y": box[1],
                                "width": box[2] - box[0],
                                "height": box[3] - box[1],
                            }
                        detections.append(detection)

        # Add detections to result for danger score calculation
        result["detections"] = detections

        return {
            "success": True,
            "result": result,
            "result_image_path": f"/{result_image_path}" if result_image_path else None,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@bp.post("/analyze")
@jwt_required()
def analyze_route():
    """
    Analyze route by generating roadview images and detecting objects.

    Request JSON:
        {
            "points": [
                {"lat": 37.5665, "lon": 126.9780},
                {"lat": 37.5670, "lon": 126.9785},
                ...
            ],
            "interval_meters": 50,  // Optional, default 50
            "tag": "route_001"  // Optional, for organizing images
        }

    Response:
        {
            "route_id": "uuid",
            "osrm_route": {...},
            "analyzed_points": [
                {
                    "index": 0,
                    "lat": 37.5665,
                    "lon": 126.9780,
                    "heading": 45.0,
                    "roadview_image": "/static/roadviews/tag/file.jpg",
                    "roadview_success": true,
                    "detection_result": {...},
                    "detection_image": "/static/roadviews/tag/result_file.jpg",
                    "detection_success": true
                },
                ...
            ],
            "summary": {
                "total_points": 10,
                "successful_roadviews": 8,
                "successful_detections": 7
            }
        }
    """
    data = request.get_json() or {}
    user_id = get_jwt_identity()

    # Parse input
    points_raw = data.get("points", [])
    if not points_raw or len(points_raw) < 2:
        return jsonify({"error": "At least 2 points are required"}), 400

    points = []
    for pt in points_raw:
        parsed = _parse_point(pt)
        if not parsed:
            return jsonify({"error": "Invalid point format"}), 400
        points.append(parsed)

    interval_meters = float(data.get("interval_meters", 50))
    tag = data.get("tag") or str(uuid.uuid4())[:8]

    # Step 1: Call OSRM to get route segments
    osrm_base = os.getenv("OSRM_BASE_URL", "http://192.168.1.79:8890")
    osrm_profile = data.get("profile", "driving")

    coords_str = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    osrm_url = f"{osrm_base}/route/v1/{osrm_profile}/{coords_str}"
    params = {"overview": "full", "geometries": "geojson", "steps": "true"}

    try:
        osrm_response = requests.get(osrm_url, params=params, timeout=10)
        osrm_response.raise_for_status()
        osrm_data = osrm_response.json()
    except Exception as e:
        return jsonify({"error": f"OSRM request failed: {str(e)}"}), 502

    routes = osrm_data.get("routes", [])
    if not routes:
        return jsonify({"error": "No route found"}), 404

    route_geometry = routes[0].get("geometry", {}).get("coordinates", [])
    legs = routes[0].get("legs", [])

    # Step 2: Generate intermediate points with headings
    all_points = []

    for leg in legs:
        steps = leg.get("steps", [])
        for step in steps:
            maneuver = step.get("maneuver", {})
            location = maneuver.get("location", [])

            if len(location) == 2:
                lon, lat = location

                # Find next point to calculate heading
                step_geom = step.get("geometry", {}).get("coordinates", [])
                if len(step_geom) >= 2:
                    next_lon, next_lat = step_geom[1]
                    heading = _calculate_bearing(lat, lon, next_lat, next_lon)
                else:
                    heading = 0

                all_points.append((lat, lon, heading))

        # Add intermediate points between steps
        if len(all_points) >= 2:
            last_point = all_points[-2]
            current_point = all_points[-1]

            interpolated = _interpolate_segment(
                last_point[0],
                last_point[1],
                current_point[0],
                current_point[1],
                interval_meters,
            )

            # Add interpolated points (skip first and last as they're already in all_points)
            for pt in interpolated[1:-1]:
                all_points.append(pt)

    # Remove duplicates while preserving order
    seen = set()
    unique_points = []
    for pt in all_points:
        # Round to 6 decimal places for comparison (~0.1m precision)
        key = (round(pt[0], 6), round(pt[1], 6))
        if key not in seen:
            seen.add(key)
            unique_points.append(pt)

    # Step 3: Download roadview images and analyze
    analyzed_points = []
    created_hazards = []
    successful_roadviews = 0
    successful_detections = 0

    for idx, (lat, lon, heading) in enumerate(unique_points):
        point_result = {
            "index": idx,
            "lat": lat,
            "lon": lon,
            "heading": heading,
            "roadview_image": None,
            "roadview_success": False,
            "detection_result": None,
            "detection_image": None,
            "detection_success": False,
            "danger_score": None,
            "hazard_id": None,
        }

        # Get roadview image
        roadview_result = _get_roadview_image(lat, lon, heading, tag)

        if roadview_result.get("success"):
            point_result["roadview_success"] = True
            point_result["roadview_image"] = f"/{roadview_result['file_path']}"
            successful_roadviews += 1

            # Analyze with detector
            detection_result = _analyze_roadview_with_detector(
                roadview_result["file_path"]
            )

            if detection_result.get("success"):
                point_result["detection_success"] = True
                detection_data = detection_result.get("result")
                point_result["detection_result"] = detection_data
                point_result["detection_image"] = detection_result.get(
                    "result_image_path"
                )
                successful_detections += 1

                # Calculate danger score from detection results
                danger_score, score_analysis = calculate_danger_score_from_detection(
                    detection_data
                )
                point_result["danger_score"] = danger_score
                point_result["score_analysis"] = score_analysis

                # Create Hazard record if danger score is significant (>= 3.0)
                if danger_score >= 3.0:
                    try:
                        # Get OSM edge ID for the location
                        osm_edge_id = _match_osm_edge(
                            lat, lon, base_url=osrm_base, profile=osrm_profile
                        )

                        # Calculate weight penalty
                        weight_penalty = penalty_from_danger(danger_score)

                        # Create Hazard record
                        hazard = Hazard(
                            lat=lat,
                            lon=lon,
                            danger_score=danger_score,
                            is_active=True,
                            edge_id=osm_edge_id,
                            osm_edge_id=osm_edge_id,
                            weight_penalty=weight_penalty,
                        )
                        db.session.add(hazard)
                        db.session.flush()  # Get hazard_id without committing

                        point_result["hazard_id"] = hazard.hazard_id
                        created_hazards.append(hazard.serialize())

                    except Exception as hazard_error:
                        point_result["hazard_error"] = str(hazard_error)
            else:
                point_result["detection_error"] = detection_result.get("error")
        else:
            point_result["roadview_error"] = roadview_result.get("error")

        analyzed_points.append(point_result)

    # Commit all hazards at once
    try:
        if created_hazards:
            db.session.commit()
            # Refresh hazard cache and schedule OSRM customize
            _hazard_cache(force=True)
            schedule_osrm_customize()
    except Exception as commit_error:
        db.session.rollback()

    # Step 4: Build response
    response_data = {
        "route_id": tag,
        "tag": tag,  # 명시적 태그 (images 조회 시 사용)
        "osrm_route": {
            "distance": routes[0].get("distance"),
            "duration": routes[0].get("duration"),
            "legs_count": len(legs),
        },
        "analyzed_points": analyzed_points,
        "hazards": created_hazards,
        "summary": {
            "total_points": len(unique_points),
            "successful_roadviews": successful_roadviews,
            "successful_detections": successful_detections,
            "hazards_created": len(created_hazards),
            "interval_meters": interval_meters,
        },
        "images": {
            "tag": tag,
            "list_url": f"/route/analyze/{tag}/images",
            "base_path": f"/static/roadviews/{tag}",
        },
    }

    return jsonify(response_data), 200


@bp.get("/analyze/<tag>/images")
def get_analysis_images(tag):
    """
    분석 결과 이미지 조회 - 분석 전/후 이미지 목록 반환

    Args:
        tag: 분석 시 사용된 태그 (route_id)

    Response:
        {
            "tag": "route_001",
            "images": [
                {
                    "index": 0,
                    "lat": 37.5665,
                    "lon": 126.9780,
                    "heading": 45.0,
                    "original": "/static/roadviews/route_001/roadview_37.566500_126.978000_45.jpg",
                    "analyzed": "/static/roadviews/route_001/analyzed_37.566500_126.978000_45.jpg"
                },
                ...
            ],
            "summary": {
                "total": 10,
                "with_original": 10,
                "with_analyzed": 8
            }
        }
    """
    import glob

    # Validate tag format (prevent path traversal)
    if not tag or ".." in tag or "/" in tag or "\\" in tag:
        return jsonify({"error": "Invalid tag format"}), 400

    # Find roadview images directory
    roadview_dir = os.path.join("static", "roadviews", tag)

    if not os.path.exists(roadview_dir):
        return jsonify({"error": "Analysis not found", "tag": tag}), 404

    # Collect images
    images = []
    original_pattern = os.path.join(roadview_dir, "roadview_*.jpg")
    original_files = glob.glob(original_pattern)

    with_original = 0
    with_analyzed = 0

    for idx, original_path in enumerate(sorted(original_files)):
        filename = os.path.basename(original_path)
        # Parse filename: roadview_37.566500_126.978000_45.jpg
        parts = filename.replace("roadview_", "").replace(".jpg", "").split("_")

        if len(parts) >= 3:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                heading = float(parts[2])
            except (ValueError, IndexError):
                lat, lon, heading = None, None, None
        else:
            lat, lon, heading = None, None, None

        # Check for analyzed image
        analyzed_filename = filename.replace("roadview_", "analyzed_")
        analyzed_path = os.path.join(roadview_dir, analyzed_filename)

        image_data = {
            "index": idx,
            "lat": lat,
            "lon": lon,
            "heading": heading,
            "original": f"/{original_path.replace(os.sep, '/')}",
            "analyzed": None,
        }

        with_original += 1

        if os.path.exists(analyzed_path):
            image_data["analyzed"] = f"/{analyzed_path.replace(os.sep, '/')}"
            with_analyzed += 1

        images.append(image_data)

    return (
        jsonify(
            {
                "tag": tag,
                "images": images,
                "summary": {
                    "total": len(images),
                    "with_original": with_original,
                    "with_analyzed": with_analyzed,
                },
            }
        ),
        200,
    )


@bp.get("/analyze/<tag>/images/<int:index>")
def get_analysis_image_detail(tag, index):
    """
    특정 분석 이미지 상세 조회

    Args:
        tag: 분석 시 사용된 태그 (route_id)
        index: 이미지 인덱스

    Response:
        {
            "tag": "route_001",
            "index": 0,
            "lat": 37.5665,
            "lon": 126.9780,
            "heading": 45.0,
            "original": {
                "url": "/static/roadviews/route_001/roadview_37.566500_126.978000_45.jpg",
                "exists": true,
                "size_bytes": 12345
            },
            "analyzed": {
                "url": "/static/roadviews/route_001/analyzed_37.566500_126.978000_45.jpg",
                "exists": false,
                "size_bytes": null
            }
        }
    """
    import glob

    # Validate tag format
    if not tag or ".." in tag or "/" in tag or "\\" in tag:
        return jsonify({"error": "Invalid tag format"}), 400

    roadview_dir = os.path.join("static", "roadviews", tag)

    if not os.path.exists(roadview_dir):
        return jsonify({"error": "Analysis not found", "tag": tag}), 404

    # Get sorted list of original files
    original_pattern = os.path.join(roadview_dir, "roadview_*.jpg")
    original_files = sorted(glob.glob(original_pattern))

    if index < 0 or index >= len(original_files):
        return (
            jsonify(
                {
                    "error": "Image index out of range",
                    "tag": tag,
                    "index": index,
                    "max_index": len(original_files) - 1,
                }
            ),
            404,
        )

    original_path = original_files[index]
    filename = os.path.basename(original_path)

    # Parse coordinates from filename
    parts = filename.replace("roadview_", "").replace(".jpg", "").split("_")
    try:
        lat = float(parts[0])
        lon = float(parts[1])
        heading = float(parts[2])
    except (ValueError, IndexError):
        lat, lon, heading = None, None, None

    # Check analyzed image
    analyzed_filename = filename.replace("roadview_", "analyzed_")
    analyzed_path = os.path.join(roadview_dir, analyzed_filename)

    original_info = {
        "url": f"/{original_path.replace(os.sep, '/')}",
        "exists": True,
        "size_bytes": os.path.getsize(original_path),
    }

    analyzed_info = {
        "url": f"/{analyzed_path.replace(os.sep, '/')}",
        "exists": os.path.exists(analyzed_path),
        "size_bytes": (
            os.path.getsize(analyzed_path) if os.path.exists(analyzed_path) else None
        ),
    }

    return (
        jsonify(
            {
                "tag": tag,
                "index": index,
                "lat": lat,
                "lon": lon,
                "heading": heading,
                "original": original_info,
                "analyzed": analyzed_info,
            }
        ),
        200,
    )
