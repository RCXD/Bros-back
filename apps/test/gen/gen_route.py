"""Route 데이터 생성 스크립트.

route_data.json에서 사용자 경로를 로드하여 DB에 저장하고,
각 Route에 대응하는 Place 레코드(route_id 링크)를 보장합니다.
"""

import json
import os
import random
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

import pytest
from sqlalchemy import func

from apps.auth.models import AccountType, User
from apps.config.server import db
from apps.place.models import Place, PlaceCategory, PlaceType
from apps.route.models import Route

try:
    from logger import get_logger
except ImportError:  # pragma: no cover - pytest 실행 시 경로 문제 대비
    from apps.common.logger import get_logger

ROUTE_JSON_FILE = "route_data.json"
ROUTE_PLACE_TYPE_NAME = "route"
ROUTE_PLACE_ICON = "route"
ROUTE_POLYGON_MIN_PADDING = 0.0003  # ~30m padding to avoid zero-area polygons


def _json_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "json")


def _load_route_payload() -> List[Dict]:
    json_dir = _json_dir()
    file_path = os.path.join(json_dir, ROUTE_JSON_FILE)
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    routes = data.get("routes")
    return routes if isinstance(routes, list) else []


def _normalize_point(point) -> Optional[Dict[str, float]]:
    if isinstance(point, dict):
        lat = point.get("lat") or point.get("latitude")
        lon = point.get("lon") or point.get("lng") or point.get("longitude")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        lat, lon = point[0], point[1]
    else:
        return None

    try:
        return {"lat": float(lat), "lon": float(lon)}
    except (TypeError, ValueError):
        return None


def extract_route_points(route_item: Dict) -> List[Dict[str, float]]:
    if not isinstance(route_item, dict):
        return []

    # 1) points 배열이 직접 주어진 경우
    raw_points = route_item.get("points")
    if isinstance(raw_points, list) and raw_points:
        normalized = [_normalize_point(p) for p in raw_points]
        return [p for p in normalized if p]

    # 2) start/end/waypoints 조합 지원
    start = _normalize_point(route_item.get("start"))
    end = _normalize_point(route_item.get("end"))
    if not (start and end):
        return []

    waypoints = []
    raw_waypoints = route_item.get("waypoints") or []
    if isinstance(raw_waypoints, list):
        for wp in raw_waypoints:
            point = _normalize_point(wp)
            if point:
                waypoints.append(point)

    return [start, *waypoints, end]


def ensure_route_place_type() -> PlaceType:
    place_type = PlaceType.query.filter_by(name=ROUTE_PLACE_TYPE_NAME).first()
    if place_type:
        return place_type

    category = PlaceCategory.query.filter_by(name="positive").first()
    if not category:
        category = PlaceCategory(name="positive", description="사용자 추천 경로")
        db.session.add(category)
        db.session.flush()

    place_type = PlaceType(
        name=ROUTE_PLACE_TYPE_NAME,
        display_name="경로",
        category_id=category.category_id,
        icon=ROUTE_PLACE_ICON,
    )
    db.session.add(place_type)
    db.session.flush()
    return place_type


def _route_polygon_wkt(points: Sequence[Dict[str, float]]) -> Optional[str]:
    """Generate a padded bounding polygon WKT around the given route points."""

    if not points:
        return None

    valid: List[Tuple[float, float]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        lat = point.get("lat") or point.get("latitude")
        lon = point.get("lon") or point.get("lng") or point.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            valid.append((float(lat), float(lon)))
        except (TypeError, ValueError):
            continue

    if not valid:
        return None

    lats = [lat for lat, _ in valid]
    lons = [lon for _, lon in valid]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    lat_pad = max((max_lat - min_lat) * 0.1, ROUTE_POLYGON_MIN_PADDING)
    lon_pad = max((max_lon - min_lon) * 0.1, ROUTE_POLYGON_MIN_PADDING)

    min_lat -= lat_pad
    max_lat += lat_pad
    min_lon -= lon_pad
    max_lon += lon_pad

    polygon_points = [
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, max_lon),
        (max_lat, min_lon),
        (min_lat, min_lon),
    ]
    coords_str = ", ".join(f"{lat} {lon}" for lat, lon in polygon_points)
    return f"POLYGON(({coords_str}))"


def ensure_place_for_route(route: Route, place_type: PlaceType) -> Optional[Place]:
    if not route or not route.points:
        return None

    first = route.points[0]
    lat = first.get("lat")
    lon = first.get("lon") or first.get("lng") or first.get("longitude")
    if lat is None or lon is None:
        return None

    polygon_wkt = _route_polygon_wkt(route.points)
    if polygon_wkt is None:
        return None

    coordinate = func.ST_GeomFromText(f"POINT({float(lat)} {float(lon)})", 4326)
    geom = func.ST_GeomFromText(polygon_wkt, 4326)

    if route.place:
        if route.place.geom is None:
            route.place.geom = geom
            route.place.geometry_type = "polygon"
            existing_tags = (
                route.place.tags if isinstance(route.place.tags, dict) else {}
            )
            updated_tags = dict(existing_tags)
            updated_tags["route_points"] = len(route.points)
            updated_tags.setdefault("generator", "gen_route")
            route.place.tags = updated_tags
        return route.place

    place = Place(
        name=route.name,
        alt_name=f"{route.name} (경로)",
        description=f"{route.name} 경로 (자동 생성)",
        coordinate=coordinate,
        geom=geom,
        type_id=place_type.type_id,
        category_id=place_type.category_id,
        geometry_type="polygon",
        recommendation_score=Decimal("4.0"),
        danger_level=Decimal("0.0"),
        tags={"generator": "gen_route", "route_points": len(route.points)},
        route_id=route.route_id,
    )
    place.route = route
    db.session.add(place)
    db.session.flush()
    return place


def _build_username_map(users: List[User]) -> Dict[str, int]:
    return {u.username: u.user_id for u in users}


@pytest.mark.no_cleanup
def test_generate_routes(fixture_app):
    """route_data.json을 기반으로 Route(MyPath) 데이터를 생성"""

    log = get_logger()

    with fixture_app.app_context():
        log.info("\n[Route] 사용자 경로 생성")

        users = User.query.filter_by(account_type=AccountType.USER).all()
        if not users:
            log.warning(
                "  생성 가능한 사용자가 없습니다. gen_user.py를 먼저 실행하세요!"
            )
            pytest.skip("사용자 데이터 없음")

        username_map = _build_username_map(users)
        payload = _load_route_payload()
        if not payload:
            log.warning("  route_data.json을 찾을 수 없거나 비어 있습니다")
            pytest.skip("route 데이터 없음")

        place_type = ensure_route_place_type()

        created = 0
        skipped = 0

        for item in payload:
            if not isinstance(item, dict):
                skipped += 1
                continue

            name = item.get("name") or item.get("route_name")
            if not name:
                skipped += 1
                continue

            points = extract_route_points(item)
            if len(points) < 2:
                skipped += 1
                continue

            user_id = username_map.get(item.get("username"))
            if not user_id:
                user_id = random.choice(users).user_id

            existing = Route.query.filter_by(user_id=user_id, name=name).first()
            if existing:
                ensure_place_for_route(existing, place_type)
                continue

            route = Route(user_id=user_id, name=name, points=points)
            db.session.add(route)
            db.session.flush()  # route_id 확보
            ensure_place_for_route(route, place_type)
            created += 1

        if created:
            db.session.commit()

        # 누락된 경로에 대해서도 Place 보장
        missing_places = Route.query.filter(
            ~Route.place.has()
        ).all()  # type: ignore[attr-defined]
        ensured = 0
        for route in missing_places:
            if ensure_place_for_route(route, place_type):
                ensured += 1
        if ensured:
            db.session.commit()

        total_routes = Route.query.count()
        total_route_places = Place.query.filter(Place.route_id.isnot(None)).count()
        log.success(
            f"  {created}개 경로 생성 완료 (건너뜀 {skipped}개, DB 총: {total_routes}개, 경로 Place {total_route_places}개)"
        )
