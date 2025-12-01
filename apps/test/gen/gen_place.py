"""
Place 데이터 생성 스크립트
place_data.json에서 위치 정보를 로드하여 데이터베이스에 생성
"""

import os
import sys

# 프로젝트 루트 경로 설정
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from sqlalchemy import func

try:
    from logger import get_logger
    from gen_place_helper import (
        load_place_data_from_json,
        ensure_place_categories,
        ensure_place_types,
        create_point_place,
        create_polygon_place,
        get_category_for_type,
    )
except ImportError:
    from apps.common.logger import get_logger
    from apps.test.gen.gen_place_helper import (
        load_place_data_from_json,
        ensure_place_categories,
        ensure_place_types,
        create_point_place,
        create_polygon_place,
        get_category_for_type,
    )


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _maybe_build_hazard(HazardModel, place_item, existing_coords):
    danger = _to_float(place_item.get("danger_level"))
    lat = _to_float(place_item.get("lat"))
    lon = _to_float(place_item.get("lon"))

    if lat is None or lon is None or not danger or danger <= 0:
        return None

    coord_key = (round(lat, 7), round(lon, 7))
    if coord_key in existing_coords:
        return None

    existing = HazardModel.query.filter_by(lat=lat, lon=lon).first()
    if existing:
        existing_coords.add(coord_key)
        return None

    weight_penalty = _to_float(place_item.get("weight_penalty")) or 0.0

    existing_coords.add(coord_key)

    return HazardModel(
        lat=lat,
        lon=lon,
        danger_score=danger,
        weight_penalty=weight_penalty,
    )


@pytest.mark.no_cleanup
def test_generate_places(fixture_app):
    """place_data.json 파일에서 위치 데이터를 로드하여 데이터베이스에 생성"""
    from apps.config.server import db
    from apps.place.models import Place, PlaceCategory, PlaceType
    from apps.hazard.models import Hazard

    log = get_logger()

    with fixture_app.app_context():
        log.info("\n[Place] 위치 데이터 생성")

        # JSON 데이터 로드
        json_dir = os.path.join(os.path.dirname(__file__), "..", "json")
        place_data = load_place_data_from_json(json_dir)

        if not place_data:
            log.warning("  place_data.json 파일을 찾을 수 없습니다!")
            pytest.skip("위치 데이터 파일이 없습니다")

        # 카테고리 생성/조회
        categories_data = place_data.get("categories", [])
        category_map = ensure_place_categories(db, PlaceCategory, categories_data)
        log.debug(f"  {len(category_map)}개 카테고리 준비 완료")

        # 타입 생성/조회
        types_data = place_data.get("types", [])
        type_map = ensure_place_types(db, PlaceType, types_data, category_map)
        log.debug(f"  {len(type_map)}개 타입 준비 완료")

        hazard_created = 0
        hazard_coords = {
            (round(lat, 7), round(lon, 7))
            for lat, lon in Hazard.query.with_entities(Hazard.lat, Hazard.lon).all()
            if lat is not None and lon is not None
        }

        # 포인트 데이터 생성
        points_data = place_data.get("points", {})
        point_count = 0

        for type_name, places_list in points_data.items():
            type_id = type_map.get(type_name)
            category_name = get_category_for_type(type_name, types_data)
            category_id = category_map.get(category_name)

            if not type_id:
                log.warning(f"  타입 '{type_name}'을 찾을 수 없습니다")
                continue

            for place_item in places_list:
                # 중복 체크
                existing = Place.query.filter_by(name=place_item["name"]).first()
                if existing:
                    continue

                place = create_point_place(
                    db, Place, func, place_item, type_id, category_id
                )
                db.session.add(place)
                point_count += 1

                hazard = _maybe_build_hazard(Hazard, place_item, hazard_coords)
                if hazard:
                    db.session.add(hazard)
                    hazard_created += 1

        db.session.commit()
        log.debug(f"  {point_count}개 포인트 위치 생성")

        # 폴리곤 데이터 생성
        polygons_data = place_data.get("polygons", {})
        polygon_count = 0

        for type_name, places_list in polygons_data.items():
            type_id = type_map.get(type_name)
            category_name = get_category_for_type(type_name, types_data)
            category_id = category_map.get(category_name)

            if not type_id:
                log.warning(f"  타입 '{type_name}'을 찾을 수 없습니다")
                continue

            for place_item in places_list:
                # 중복 체크
                existing = Place.query.filter_by(name=place_item["name"]).first()
                if existing:
                    continue

                place = create_polygon_place(
                    db, Place, func, place_item, type_id, category_id
                )
                db.session.add(place)
                polygon_count += 1

                hazard = _maybe_build_hazard(Hazard, place_item, hazard_coords)
                if hazard:
                    db.session.add(hazard)
                    hazard_created += 1

        db.session.commit()
        log.debug(f"  {polygon_count}개 폴리곤 위치 생성")

        # 최종 결과
        total_places = Place.query.count()
        log.success(
            f"  총 {point_count + polygon_count}개 위치 생성 완료 (DB 총: {total_places}개)"
        )

        total_hazards = Hazard.query.count()
        if hazard_created:
            log.success(
                f"  총 {hazard_created}개 Hazard 생성 완료 (DB 총: {total_hazards}개)"
            )
        else:
            log.debug(f"  Hazard 추가 없음 (DB 총: {total_hazards}개)")


@pytest.mark.no_cleanup
def test_clear_places(fixture_app):
    """Place 테이블 초기화 (테스트용)"""
    from apps.config.server import db
    from apps.place.models import Place, PlaceCategory, PlaceType

    log = get_logger()

    with fixture_app.app_context():
        log.info("\n[Place] 위치 데이터 초기화")

        # Place 삭제
        place_count = Place.query.count()
        Place.query.delete()

        # Type 삭제
        type_count = PlaceType.query.count()
        PlaceType.query.delete()

        # Category 삭제
        cat_count = PlaceCategory.query.count()
        PlaceCategory.query.delete()

        db.session.commit()

        log.success(
            f"  {place_count}개 Place, {type_count}개 Type, {cat_count}개 Category 삭제 완료"
        )


if __name__ == "__main__":
    # 직접 실행 시 - 필요한 것만 import (서버 시작 없이)
    from flask import Flask
    from apps.config.common import config
    from apps.config.server import db

    # 모든 관련 모델 import (의존성 해결을 위해)
    from apps.auth.models import User
    from apps.place.models import Place, PlaceCategory, PlaceType
    from sqlalchemy import func

    # 간단한 앱 생성 (서버 시작 없이)
    app = Flask(__name__)
    app.config.from_object(config["development"])
    db.init_app(app)

    with app.app_context():
        print("\n[Place] 위치 데이터 생성 시작...")

        # JSON 데이터 로드
        json_dir = os.path.join(os.path.dirname(__file__), "..", "json")
        place_data = load_place_data_from_json(json_dir)

        if not place_data:
            print("  place_data.json 파일을 찾을 수 없습니다!")
            sys.exit(1)

        # 카테고리 생성/조회
        categories_data = place_data.get("categories", [])
        category_map = ensure_place_categories(db, PlaceCategory, categories_data)
        print(f"  {len(category_map)}개 카테고리 준비 완료")

        # 타입 생성/조회
        types_data = place_data.get("types", [])
        type_map = ensure_place_types(db, PlaceType, types_data, category_map)
        print(f"  {len(type_map)}개 타입 준비 완료")

        # 포인트 데이터 생성
        points_data = place_data.get("points", {})
        point_count = 0

        for type_name, places_list in points_data.items():
            type_id = type_map.get(type_name)
            category_name = get_category_for_type(type_name, types_data)
            category_id = category_map.get(category_name)

            if not type_id:
                print(f"  타입 '{type_name}'을 찾을 수 없습니다")
                continue

            for place_item in places_list:
                existing = Place.query.filter_by(name=place_item["name"]).first()
                if existing:
                    continue

                place = create_point_place(
                    db, Place, func, place_item, type_id, category_id
                )
                db.session.add(place)
                point_count += 1

        db.session.commit()
        print(f"  {point_count}개 포인트 위치 생성")

        # 폴리곤 데이터 생성
        polygons_data = place_data.get("polygons", {})
        polygon_count = 0

        for type_name, places_list in polygons_data.items():
            type_id = type_map.get(type_name)
            category_name = get_category_for_type(type_name, types_data)
            category_id = category_map.get(category_name)

            if not type_id:
                print(f"  타입 '{type_name}'을 찾을 수 없습니다")
                continue

            for place_item in places_list:
                existing = Place.query.filter_by(name=place_item["name"]).first()
                if existing:
                    continue

                place = create_polygon_place(
                    db, Place, func, place_item, type_id, category_id
                )
                db.session.add(place)
                polygon_count += 1

        db.session.commit()
        print(f"  {polygon_count}개 폴리곤 위치 생성")

        total = Place.query.count()
        print(
            f"\n  ✅ 총 {point_count + polygon_count}개 위치 생성 완료 (DB 총: {total}개)"
        )
