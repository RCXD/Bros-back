from datetime import datetime
import json

from sqlalchemy import func
from geoalchemy2 import Geometry
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import reconstructor
import struct
from geoalchemy2.elements import WKTElement
from sqlalchemy.types import JSON

from apps.config.server import db


def point_from_lat_lon(lat, lon):
    if lat is None or lon is None:
        return None
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def coordinate_to_lat_lon(value):
    if value is None:
        return (None, None)
    data = getattr(value, "data", None)
    if data is None:
        # accept tuples or dicts for flexibility
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (value[1], value[0])
        if isinstance(value, dict) and {"lat", "lon"}.issubset(value.keys()):
            return (value.get("lat"), value.get("lon"))
        return (None, None)
    buffer = bytes(data)
    if not buffer:
        return (None, None)
    endian_flag = buffer[0]
    fmt = "<" if endian_flag == 1 else ">"
    type_code = struct.unpack(fmt + "I", buffer[1:5])[0]
    has_srid = bool(type_code & 0x20000000)
    bbox_type = type_code & 0xFF
    offset = 5
    if has_srid:
        offset += 4
    if bbox_type != 1 or len(buffer) < offset + 16:
        return (None, None)
    x = struct.unpack(fmt + "d", buffer[offset : offset + 8])[0]
    y = struct.unpack(fmt + "d", buffer[offset + 8 : offset + 16])[0]
    return (y, x)


class PlaceCategory(db.Model):
    """Place 분류: positive/negative/neutral"""

    __tablename__ = "place_category"

    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(50), nullable=False, unique=True
    )  # positive, negative, neutral
    description = db.Column(db.String(255))

    places = db.relationship("Place", back_populates="category", lazy="dynamic")


class PlaceType(db.Model):
    """Place 세부 타입: pothole, restaurant, cafe, construction 등"""

    __tablename__ = "place_type"

    type_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    display_name = db.Column(db.String(100))  # 화면 표시용
    category_id = db.Column(db.Integer, db.ForeignKey("place_category.category_id"))
    icon = db.Column(db.String(50))  # 아이콘 이름

    category = db.relationship("PlaceCategory", backref="types")
    places = db.relationship("Place", back_populates="place_type", lazy="dynamic")


class Place(db.Model):
    __tablename__ = "place"
    __table_args__ = (
        db.Index("idx_place_point", "coordinate"),
        db.Index("idx_place_geom_spatial", "geom", mysql_prefix="SPATIAL"),
        db.Index("idx_place_category", "category_id"),
        db.Index("idx_place_type", "type_id"),
        db.Index("idx_place_route", "route_id"),
    )
    # 장소 아이디(저장용)
    place_id = db.Column(db.Integer, primary_key=True)
    # 장소 이름(없을 시 주소 저장)
    name = db.Column(db.String(255), nullable=False)
    # 대표 이름(ex)코엑스, 서울역, ...)
    alt_name = db.Column(db.String(255))
    # 좌표(위도, 경도, 자동으로 입력)
    coordinate = db.Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    # 장소 공간(차지하는)
    geom = db.Column(Geometry(srid=4326))
    # 설명
    description = db.Column(db.Text)
    # 원본 응답
    tags = db.Column(JSON)

    # 분류 정보
    category_id = db.Column(db.Integer, db.ForeignKey("place_category.category_id"))
    type_id = db.Column(db.Integer, db.ForeignKey("place_type.type_id"))

    # Route 연동 (Optional, 1:1)
    route_id = db.Column(
        db.Integer,
        db.ForeignKey("routes.route_id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    # 추천도/위험도
    recommendation_score = db.Column(db.Numeric(2, 1), default=3.0)  # 1.0~5.0
    danger_level = db.Column(db.Numeric(3, 1), default=0.0)  # 0.0~10.0

    # 형태 (point/polygon)
    geometry_type = db.Column(db.String(20), default="point")  # point, polygon

    # ========== Google Places API 수집 정보 ==========
    google_place_id = db.Column(db.String(255), unique=True, nullable=True)
    google_name = db.Column(db.String(255))
    google_address = db.Column(db.String(500))
    google_rating = db.Column(db.Numeric(2, 1))  # 1.0~5.0
    google_reviews_count = db.Column(db.Integer, default=0)
    google_price_level = db.Column(db.Integer)  # 0~4 (Google 기준)
    google_phone = db.Column(db.String(50))
    google_website = db.Column(db.String(500))
    google_opening_hours = db.Column(JSON)  # 영업시간 JSON
    google_photos = db.Column(JSON)  # 사진 URL 목록
    google_types = db.Column(JSON)  # Google 장소 타입 목록
    google_business_status = db.Column(
        db.String(50)
    )  # OPERATIONAL, CLOSED_TEMPORARILY 등
    google_last_synced = db.Column(db.DateTime)  # 마지막 동기화 시간

    # ========== Kakao Local API 수집 정보 ==========
    kakao_place_id = db.Column(db.String(255), unique=True, nullable=True)
    kakao_name = db.Column(db.String(255))
    kakao_address = db.Column(db.String(500))  # 지번 주소
    kakao_road_address = db.Column(db.String(500))  # 도로명 주소
    kakao_phone = db.Column(db.String(50))
    kakao_category_name = db.Column(db.String(255))  # 카테고리 전체 경로
    kakao_category_group_code = db.Column(db.String(20))  # FD6, CE7 등
    kakao_category_group_name = db.Column(db.String(50))  # 음식점, 카페 등
    kakao_url = db.Column(db.String(500))  # 카카오맵 URL
    kakao_last_synced = db.Column(db.DateTime)  # 마지막 동기화 시간

    # ========== 통합 정보 ==========
    verified = db.Column(db.Boolean, default=False)  # 정보 검증 여부
    data_source = db.Column(db.String(50))  # user, google, kakao, merged

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    category = db.relationship("PlaceCategory", back_populates="places")
    place_type = db.relationship("PlaceType", back_populates="places")
    # Route 참조 (경로형 Place)
    route = db.relationship("Route", back_populates="place", uselist=False)

    def __init__(self, **kwargs):
        lat = kwargs.pop("lat", None)
        lon = kwargs.pop("lon", None)
        coordinate = kwargs.pop("coordinate", None)
        self._lat_cache = None
        self._lon_cache = None
        super().__init__(**kwargs)
        if coordinate is not None:
            self.coordinate = coordinate
        elif lat is not None and lon is not None:
            self.set_lat_lon(lat, lon)
        elif lat is not None or lon is not None:
            raise ValueError("Both lat and lon are required to set point")

    @reconstructor
    def _on_load(self):
        self._lat_cache = None
        self._lon_cache = None

    @staticmethod
    def _point_from_latlon(lat, lon):
        if lat is None or lon is None:
            return None
        return func.ST_GeomFromText(f"POINT({float(lat)} {float(lon)})", 4326)

    def set_lat_lon(self, lat, lon):
        if lat is None or lon is None:
            raise ValueError("lat and lon are required")
        lat_f = float(lat)
        lon_f = float(lon)
        self.coordinate = self._point_from_latlon(lat_f, lon_f)
        self._lat_cache = lat_f
        self._lon_cache = lon_f

    @hybrid_property
    def lat(self):
        if self.coordinate is None:
            return None
        if self._lat_cache is not None:
            return self._lat_cache
        # MySQL SRID 4326: POINT(lat, lon) 저장됨 -> ST_X가 lat 반환
        value = db.session.scalar(func.ST_X(self.coordinate))
        self._lat_cache = float(value) if value is not None else None
        return self._lat_cache

    @lat.expression
    def lat(cls):
        return func.ST_X(cls.coordinate)

    @hybrid_property
    def lon(self):
        if self.coordinate is None:
            return None
        if self._lon_cache is not None:
            return self._lon_cache
        # MySQL SRID 4326: POINT(lat, lon) 저장됨 -> ST_Y가 lon 반환
        value = db.session.scalar(func.ST_Y(self.coordinate))
        self._lon_cache = float(value) if value is not None else None
        return self._lon_cache

    @lon.expression
    def lon(cls):
        return func.ST_Y(cls.coordinate)

    def get_coordinates(self):
        """
        Place의 중심 좌표 반환

        Returns:
            tuple: (lat, lon) 또는 (None, None)
        """
        return (self.lat, self.lon)

    def to_dict(self, include_geom=True, include_external=False):
        geom_json = None
        if include_geom and self.geom is not None:
            try:
                geo_str = db.session.scalar(func.ST_AsGeoJSON(self.geom))
                geom_json = json.loads(geo_str) if geo_str else None
            except Exception:
                geom_json = None

        result = {
            "place_id": self.place_id,
            "name": self.name,
            "alt_name": self.alt_name,
            "lat": self.lat,
            "lon": self.lon,
            "geom": geom_json,
            "geometry_type": self.geometry_type,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "type_id": self.type_id,
            "type_name": self.place_type.name if self.place_type else None,
            "type_display_name": (
                self.place_type.display_name if self.place_type else None
            ),
            "route_id": self.route_id,
            "recommendation_score": (
                float(self.recommendation_score) if self.recommendation_score else None
            ),
            "danger_level": float(self.danger_level) if self.danger_level else None,
            "tags": self.tags,
            "verified": self.verified,
            "data_source": self.data_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        # 외부 API 데이터 포함 옵션
        if include_external:
            result["google"] = self._get_google_data()
            result["kakao"] = self._get_kakao_data()

        return result

    def _get_google_data(self):
        """Google Places API 데이터 반환"""
        if not self.google_place_id:
            return None
        return {
            "place_id": self.google_place_id,
            "name": self.google_name,
            "address": self.google_address,
            "rating": float(self.google_rating) if self.google_rating else None,
            "reviews_count": self.google_reviews_count,
            "price_level": self.google_price_level,
            "phone": self.google_phone,
            "website": self.google_website,
            "opening_hours": self.google_opening_hours,
            "photos": self.google_photos,
            "types": self.google_types,
            "business_status": self.google_business_status,
            "last_synced": (
                self.google_last_synced.isoformat() if self.google_last_synced else None
            ),
        }

    def _get_kakao_data(self):
        """Kakao Local API 데이터 반환"""
        if not self.kakao_place_id:
            return None
        return {
            "place_id": self.kakao_place_id,
            "name": self.kakao_name,
            "address": self.kakao_address,
            "road_address": self.kakao_road_address,
            "phone": self.kakao_phone,
            "category_name": self.kakao_category_name,
            "category_group_code": self.kakao_category_group_code,
            "category_group_name": self.kakao_category_group_name,
            "url": self.kakao_url,
            "last_synced": (
                self.kakao_last_synced.isoformat() if self.kakao_last_synced else None
            ),
        }

    def update_from_google(self, google_data):
        """Google Places API 응답으로 데이터 업데이트"""
        from datetime import datetime

        if not google_data:
            return False

        self.google_place_id = google_data.get("place_id")
        self.google_name = google_data.get("name")
        self.google_address = google_data.get("formatted_address") or google_data.get(
            "vicinity"
        )
        self.google_rating = google_data.get("rating")
        self.google_reviews_count = google_data.get("user_ratings_total", 0)
        self.google_price_level = google_data.get("price_level")
        self.google_phone = google_data.get(
            "formatted_phone_number"
        ) or google_data.get("international_phone_number")
        self.google_website = google_data.get("website")
        self.google_business_status = google_data.get("business_status")
        self.google_types = google_data.get("types")

        # 영업시간 파싱
        opening_hours = google_data.get("opening_hours")
        if opening_hours:
            self.google_opening_hours = {
                "weekday_text": opening_hours.get("weekday_text"),
                "open_now": opening_hours.get("open_now"),
                "periods": opening_hours.get("periods"),
            }

        # 사진 URL 파싱 (photo_reference만 저장)
        photos = google_data.get("photos", [])
        if photos:
            self.google_photos = [
                {
                    "photo_reference": p.get("photo_reference"),
                    "width": p.get("width"),
                    "height": p.get("height"),
                }
                for p in photos[:5]  # 최대 5개
            ]

        self.google_last_synced = datetime.now()

        # 데이터 소스 업데이트
        if not self.data_source:
            self.data_source = "google"
        elif "google" not in self.data_source:
            self.data_source = "merged"

        return True

    def update_from_kakao(self, kakao_data):
        """Kakao Local API 응답으로 데이터 업데이트"""
        from datetime import datetime

        if not kakao_data:
            return False

        self.kakao_place_id = kakao_data.get("id")
        self.kakao_name = kakao_data.get("place_name")
        self.kakao_address = kakao_data.get("address_name")
        self.kakao_road_address = kakao_data.get("road_address_name")
        self.kakao_phone = kakao_data.get("phone")
        self.kakao_category_name = kakao_data.get("category_name")
        self.kakao_category_group_code = kakao_data.get("category_group_code")
        self.kakao_category_group_name = kakao_data.get("category_group_name")
        self.kakao_url = kakao_data.get("place_url")

        self.kakao_last_synced = datetime.now()

        # 데이터 소스 업데이트
        if not self.data_source:
            self.data_source = "kakao"
        elif "kakao" not in self.data_source:
            self.data_source = "merged"

        return True

    @staticmethod
    def find_similar(
        lat, lon, name, distance_threshold_m=50, name_threshold=0.75, limit=10
    ):
        from apps.place.utils import find_similar

        return find_similar(lat, lon, name, distance_threshold_m, name_threshold, limit)

    def merge_with(self, other, session=None):
        """Merge another Place instance into this one, preferring richer metadata."""
        if other is None or other is self:
            return False
        session = session or db.session
        try:
            if other.alt_name and not self.alt_name:
                self.alt_name = other.alt_name
            if other.description:
                self_len = len(self.description) if self.description else 0
                other_len = len(other.description)
                if not self.description or other_len > self_len:
                    self.description = other.description
            if other.tags:
                if not self.tags:
                    self.tags = other.tags
                elif isinstance(self.tags, dict) and isinstance(other.tags, dict):
                    merged = self.tags.copy()
                    merged.update(other.tags)
                    self.tags = merged
                elif isinstance(self.tags, list) and isinstance(other.tags, list):
                    existing = list(self.tags)
                    seen = set(existing)
                    for item in other.tags:
                        if item not in seen:
                            existing.append(item)
                            seen.add(item)
                    self.tags = existing
                else:
                    self.tags = other.tags
            if other.geom and not self.geom:
                self.geom = other.geom
            if other.coordinate is not None and self.coordinate is None:
                self.coordinate = other.coordinate
            session.delete(other)
            return True
        except Exception:
            session.rollback()
            return False
