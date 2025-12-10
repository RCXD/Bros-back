"""
Place 생성 헬퍼 함수
"""

import json
import os
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
    place = Place(
        name=place_data["name"],
        description=place_data.get("description", ""),
        coordinate=func.ST_GeomFromText(f"POINT({lat} {lon})", 4326),
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
        # 기본 사각형 폴리곤 생성 (중심점에서 약 100m 반경)
        delta = 0.001  # 약 100m
        polygon_wkt = f"POLYGON(({lat-delta} {lon-delta}, {lat-delta} {lon+delta}, {lat+delta} {lon+delta}, {lat+delta} {lon-delta}, {lat-delta} {lon-delta}))"

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


def get_category_for_type(type_name: str, types_data: list) -> str:
    """타입 이름으로 카테고리 이름 조회"""
    for type_data in types_data:
        if type_data["name"] == type_name:
            return type_data.get("category", "neutral")
    return "neutral"
