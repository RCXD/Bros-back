import math
from collections import defaultdict

from flask import Blueprint, jsonify, request

from apps.hazard.models import Hazard

bp = Blueprint("hazard", __name__)

_DEFAULT_RADIUS_KM = 2.0
_MIN_RADIUS_KM = 0.1
_MAX_RADIUS_KM = 15.0
_DEFAULT_GRID_M = 250.0
_MIN_GRID_M = 50.0
_MAX_GRID_M = 2000.0
_MAX_FETCH = 600
_MAX_POINTS_RESPONSE = 120
_MAX_NEARBY_RETURN = 200
_KM_PER_DEG_LAT = 110.574


def _parse_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def _meters_per_deg_lon(lat):
    meters = 111.320 * math.cos(math.radians(lat))
    return meters if abs(meters) > 1e-6 else 1e-6


def _haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    radius_km = 6371.0088
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _serialize_point(hazard, center_lat, center_lon):
    return {
        "id": hazard.hazard_id,
        "lat": hazard.lat,
        "lon": hazard.lon,
        "danger": hazard.danger_score,
        "weight": hazard.weight_penalty,
        "distance_km": round(
            _haversine_km(center_lat, center_lon, hazard.lat, hazard.lon), 4
        ),
        "updated_at": hazard.updated_at.isoformat() if hazard.updated_at else None,
    }


def _cluster_hazards(hazards, center_lat, center_lon, cell_meters):
    meters_per_deg_lat = _KM_PER_DEG_LAT * 1000.0
    meters_per_deg_lon = _meters_per_deg_lon(center_lat) * 1000.0
    grid = defaultdict(
        lambda: {"count": 0, "sum": 0.0, "max": 0.0, "lat": 0.0, "lon": 0.0}
    )

    for hazard in hazards:
        if hazard.lat is None or hazard.lon is None:
            continue
        lat_offset = (hazard.lat - center_lat) * meters_per_deg_lat
        lon_offset = (hazard.lon - center_lon) * meters_per_deg_lon
        lat_idx = int(math.floor(lat_offset / cell_meters))
        lon_idx = int(math.floor(lon_offset / cell_meters))
        cell = grid[(lat_idx, lon_idx)]
        cell["count"] += 1
        cell["sum"] += hazard.danger_score or 0.0
        cell["max"] = max(cell["max"], hazard.danger_score or 0.0)
        cell["lat"] += hazard.lat
        cell["lon"] += hazard.lon

    clusters = []
    for (lat_idx, lon_idx), data in grid.items():
        count = data["count"]
        clusters.append(
            {
                "count": count,
                "avg_danger": round(data["sum"] / count, 3) if count else 0.0,
                "max_danger": round(data["max"], 3),
                "center": {
                    "lat": data["lat"] / count,
                    "lon": data["lon"] / count,
                },
                "cell": {
                    "lat_index": lat_idx,
                    "lon_index": lon_idx,
                    "size_m": cell_meters,
                },
            }
        )

    clusters.sort(key=lambda item: item["max_danger"], reverse=True)
    return clusters


@bp.get("/api_info")
def api_info():
    """
    Hazard API 정보 제공 (개발용)
    """
    info = {
        "module": "hazard",
        "base_path": "/hazard",
        "description": "위험 지역 조회 및 히트맵 데이터 제공",
        "endpoints": [
            {
                "path": "/hazard/heatmap",
                "method": "GET",
                "auth_required": False,
                "description": "히트맵용 위험 지역 클러스터 데이터 조회",
                "query_params": {
                    "lat": "중심 위도 (필수)",
                    "lon": "중심 경도 (필수)",
                    "radius_km": f"반경(km, 기본값: {_DEFAULT_RADIUS_KM}, 범위: {_MIN_RADIUS_KM}-{_MAX_RADIUS_KM})",
                    "cell_m": f"그리드 셀 크기(m, 기본값: {_DEFAULT_GRID_M}, 범위: {_MIN_GRID_M}-{_MAX_GRID_M})",
                },
                "response": {
                    "center": {"lat": "float", "lon": "float"},
                    "radius_km": "float",
                    "grid_size_m": "float",
                    "counts": {
                        "clusters": "int",
                        "points": "int",
                        "total_candidates": "int",
                    },
                    "clusters": [
                        {
                            "count": "int",
                            "avg_danger": "float",
                            "max_danger": "float",
                            "center": {"lat": "float", "lon": "float"},
                            "cell": {
                                "lat_index": "int",
                                "lon_index": "int",
                                "size_m": "float",
                            },
                        }
                    ],
                    "points": [
                        {
                            "id": "int",
                            "lat": "float",
                            "lon": "float",
                            "danger": "float",
                            "weight": "float",
                            "distance_km": "float",
                            "updated_at": "string (ISO format)",
                        }
                    ],
                    "bbox": {
                        "lat": ["float", "float"],
                        "lon": ["float", "float"],
                    },
                },
            },
            {
                "path": "/hazard/nearby",
                "method": "GET",
                "auth_required": False,
                "description": "특정 위치 근처의 위험 지역 마커 조회",
                "query_params": {
                    "lat": "중심 위도 (필수)",
                    "lon": "중심 경도 (필수)",
                    "radius_km": f"반경(km, 기본값: {_DEFAULT_RADIUS_KM}, 범위: {_MIN_RADIUS_KM}-{_MAX_RADIUS_KM})",
                    "limit": f"최대 반환 개수 (기본값: {_MAX_NEARBY_RETURN}, 최대: {_MAX_NEARBY_RETURN})",
                },
                "response": {
                    "center": {"lat": "float", "lon": "float"},
                    "radius_km": "float",
                    "count": "int",
                    "hazards": [
                        {
                            "id": "int",
                            "lat": "float",
                            "lon": "float",
                            "danger": "float",
                            "weight": "float",
                            "distance_km": "float",
                            "updated_at": "string (ISO format)",
                        }
                    ],
                },
            },
        ],
        "notes": [
            "모든 거리 계산은 Haversine 공식 사용",
            "히트맵은 그리드 기반 클러스터링으로 집계",
            "nearby는 정확한 거리로 정렬된 개별 포인트 반환",
            "is_active=True인 위험 지역만 조회",
        ],
    }
    return jsonify(info)


@bp.get("/heatmap")
def get_hazard_heatmap():
    """Aggregate hazards around the requested point for heat-map rendering."""

    lat = _parse_float(request.args.get("lat"))
    lon = _parse_float(request.args.get("lon"))
    if lat is None or lon is None:
        return jsonify({"error": "lat_lon_required"}), 400

    radius_km = _parse_float(request.args.get("radius_km"), _DEFAULT_RADIUS_KM)
    radius_km = _clamp(radius_km, _MIN_RADIUS_KM, _MAX_RADIUS_KM)

    grid_m = _parse_float(request.args.get("cell_m"), _DEFAULT_GRID_M)
    grid_m = _clamp(grid_m, _MIN_GRID_M, _MAX_GRID_M)

    lat_delta = radius_km / _KM_PER_DEG_LAT
    lon_delta = radius_km / (_meters_per_deg_lon(lat) / 1000.0)

    hazards = (
        Hazard.query.filter(Hazard.is_active.is_(True))
        .filter(Hazard.lat.between(lat - lat_delta, lat + lat_delta))
        .filter(Hazard.lon.between(lon - lon_delta, lon + lon_delta))
        .order_by(Hazard.updated_at.desc())
        .limit(_MAX_FETCH)
        .all()
    )

    clusters = _cluster_hazards(hazards, lat, lon, grid_m)
    points = [
        _serialize_point(hazard, lat, lon) for hazard in hazards[:_MAX_POINTS_RESPONSE]
    ]

    return jsonify(
        {
            "center": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "grid_size_m": grid_m,
            "counts": {
                "clusters": len(clusters),
                "points": len(points),
                "total_candidates": len(hazards),
            },
            "clusters": clusters,
            "points": points,
            "bbox": {
                "lat": [lat - lat_delta, lat + lat_delta],
                "lon": [lon - lon_delta, lon + lon_delta],
            },
        }
    )


@bp.get("/nearby")
def get_nearby_hazards():
    """Return concrete hazard markers around a location for detail overlays."""

    lat = _parse_float(request.args.get("lat"))
    lon = _parse_float(request.args.get("lon"))
    if lat is None or lon is None:
        return jsonify({"error": "lat_lon_required"}), 400

    radius_km = _parse_float(request.args.get("radius_km"), _DEFAULT_RADIUS_KM)
    radius_km = _clamp(radius_km, _MIN_RADIUS_KM, _MAX_RADIUS_KM)

    limit = int(
        _clamp(
            float(request.args.get("limit", _MAX_NEARBY_RETURN)), 1, _MAX_NEARBY_RETURN
        )
    )

    lat_delta = radius_km / _KM_PER_DEG_LAT
    lon_delta = radius_km / (_meters_per_deg_lon(lat) / 1000.0)

    candidates = (
        Hazard.query.filter(Hazard.is_active.is_(True))
        .filter(Hazard.lat.between(lat - lat_delta, lat + lat_delta))
        .filter(Hazard.lon.between(lon - lon_delta, lon + lon_delta))
        .order_by(Hazard.updated_at.desc())
        .limit(_MAX_FETCH)
        .all()
    )

    points = [
        point
        for hazard in candidates
        if (point := _serialize_point(hazard, lat, lon))["distance_km"] <= radius_km
    ]
    points.sort(key=lambda p: (p["distance_km"], -p["danger"]))

    return jsonify(
        {
            "center": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "count": min(len(points), limit),
            "hazards": points[:limit],
        }
    )
