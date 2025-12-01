"""
Place 생성 헬퍼 함수
"""

import json
import os
import math
import random
from decimal import Decimal


def load_place_data_from_json(json_dir: str) -> dict:
    """place_data.json 파일 로드"""
    json_path = os.path.join(json_dir, "place_data.json")
    if not os.path.exists(json_path):
        return {}

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_place_categories(db, PlaceCategory, categories_data: list) -> dict:
    """카테고리 생성/조회하고 name -> category_id 매핑 반환"""
    category_map = {}

    for cat_data in categories_data:
        name = cat_data["name"]
        existing = PlaceCategory.query.filter_by(name=name).first()

        if existing:
            category_map[name] = existing.category_id
        else:
            category = PlaceCategory(
                name=name, description=cat_data.get("description", "")
            )
            db.session.add(category)
            db.session.flush()
            category_map[name] = category.category_id

    db.session.commit()
    return category_map


def ensure_place_types(db, PlaceType, types_data: list, category_map: dict) -> dict:
    """타입 생성/조회하고 name -> type_id 매핑 반환"""
    type_map = {}

    for type_data in types_data:
        name = type_data["name"]
        existing = PlaceType.query.filter_by(name=name).first()

        if existing:
            type_map[name] = existing.type_id
        else:
            category_name = type_data.get("category", "neutral")
            place_type = PlaceType(
                name=name,
                display_name=type_data.get("display_name", name),
                category_id=category_map.get(category_name),
                icon=type_data.get("icon", "place"),
            )
            db.session.add(place_type)
            db.session.flush()
            type_map[name] = place_type.type_id

    db.session.commit()
    return type_map


def create_point_place(
    db, Place, func, place_data: dict, type_id: int, category_id: int
):
    """포인트 형태의 Place 생성"""
    from decimal import Decimal

    lat = place_data["lat"]
    lon = place_data["lon"]

    # MySQL SRID 4326에서는 POINT(lat lon) 순서 사용 (위도, 경도)
    # geom도 설정 - 포인트를 중심으로 작은 불규칙 폴리곤 생성
    polygon_wkt = generate_irregular_polygon(
        lat,
        lon,
        min_radius=0.00005,  # 약 5m
        max_radius=0.0002,  # 약 20m
        num_vertices=random.randint(4, 6),
    )

    place = Place(
        name=place_data["name"],
        description=place_data.get("description", ""),
        coordinate=func.ST_GeomFromText(f"POINT({lat} {lon})", 4326),
        geom=func.ST_GeomFromText(polygon_wkt, 4326),
        type_id=type_id,
        category_id=category_id,
        geometry_type="point",
        recommendation_score=Decimal(str(place_data.get("recommendation_score", 3.0))),
        danger_level=Decimal(str(place_data.get("danger_level", 0.0))),
    )

    return place


def create_polygon_place(
    db, Place, func, place_data: dict, type_id: int, category_id: int
):
    """폴리곤 형태의 Place 생성"""
    from decimal import Decimal

    lat = place_data["lat"]
    lon = place_data["lon"]
    polygon_coords = place_data.get("polygon", [])

    # MySQL SRID 4326에서는 (lat, lon) 순서 사용
    # 폴리곤 WKT 생성
    if polygon_coords:
        # 폴리곤 닫힘 확인
        if polygon_coords[0] != polygon_coords[-1]:
            polygon_coords.append(polygon_coords[0])

        # 입력 coords는 [lon, lat] 형식이므로 [lat, lon]으로 변환
        coords_str = ", ".join([f"{p[1]} {p[0]}" for p in polygon_coords])
        polygon_wkt = f"POLYGON(({coords_str}))"
    else:
        # 자연스러운 불규칙 다각형 생성
        polygon_wkt = generate_irregular_polygon(lat, lon)

    place = Place(
        name=place_data["name"],
        description=place_data.get("description", ""),
        coordinate=func.ST_GeomFromText(f"POINT({lat} {lon})", 4326),
        geom=func.ST_GeomFromText(polygon_wkt, 4326),
        type_id=type_id,
        category_id=category_id,
        geometry_type="polygon",
        recommendation_score=Decimal(str(place_data.get("recommendation_score", 3.0))),
        danger_level=Decimal(str(place_data.get("danger_level", 0.0))),
    )

    return place


def generate_irregular_polygon(
    center_lat: float,
    center_lon: float,
    min_radius: float = 0.0005,
    max_radius: float = 0.002,
    num_vertices: int = None,
) -> str:
    """
    중심점을 기준으로 불규칙한 다각형 WKT 생성

    Args:
        center_lat: 중심 위도
        center_lon: 중심 경도
        min_radius: 최소 반경 (도 단위, 약 50m)
        max_radius: 최대 반경 (도 단위, 약 200m)
        num_vertices: 꼭짓점 수 (None이면 5~8개 랜덤)

    Returns:
        POLYGON WKT 문자열
    """
    if num_vertices is None:
        num_vertices = random.randint(5, 8)

    # 각 꼭짓점의 각도를 균등하게 배분하되 약간의 변화 추가
    base_angle = 360 / num_vertices
    vertices = []

    current_angle = random.uniform(0, 360)  # 시작 각도 랜덤

    for i in range(num_vertices):
        # 각도에 약간의 변화 추가 (±15도)
        angle_variation = random.uniform(-15, 15)
        angle = current_angle + angle_variation

        # 반경도 변화 추가
        radius = random.uniform(min_radius, max_radius)

        # 극좌표를 직교좌표로 변환
        angle_rad = math.radians(angle)

        # 위도/경도 오프셋 계산
        # 경도는 위도에 따라 보정 필요 (cos(lat))
        lat_offset = radius * math.cos(angle_rad)
        lon_offset = radius * math.sin(angle_rad) / math.cos(math.radians(center_lat))

        vertex_lat = center_lat + lat_offset
        vertex_lon = center_lon + lon_offset

        vertices.append((vertex_lat, vertex_lon))

        # 다음 꼭짓점 각도
        current_angle += base_angle

    # 폴리곤 닫기 (첫 번째 점 추가)
    vertices.append(vertices[0])

    # WKT 생성 (lat lon 순서)
    coords_str = ", ".join([f"{v[0]} {v[1]}" for v in vertices])
    return f"POLYGON(({coords_str}))"


def get_category_for_type(type_name: str, types_data: list) -> str:
    """타입 이름으로 카테고리 이름 조회"""
    for type_data in types_data:
        if type_data["name"] == type_name:
            return type_data.get("category", "neutral")
    return "neutral"
