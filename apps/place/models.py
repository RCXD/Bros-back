from datetime import datetime
import json

from sqlalchemy import func
from geoalchemy2 import Geometry
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import reconstructor
import struct
from sqlalchemy import func
from geoalchemy2 import Geometry
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


class Place(db.Model):
    __tablename__ = "place"
    __table_args__ = (
        db.Index("idx_place_point", "coordinate"),
        db.Index("idx_place_geom_spatial", "geom", mysql_prefix="SPATIAL"),
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
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

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
        value = db.session.scalar(func.ST_Y(self.coordinate))
        self._lat_cache = float(value) if value is not None else None
        return self._lat_cache

    @lat.expression
    def lat(cls):
        return func.ST_Y(cls.coordinate)

    @hybrid_property
    def lon(self):
        if self.coordinate is None:
            return None
        if self._lon_cache is not None:
            return self._lon_cache
        value = db.session.scalar(func.ST_X(self.coordinate))
        self._lon_cache = float(value) if value is not None else None
        return self._lon_cache

    @lon.expression
    def lon(cls):
        return func.ST_X(cls.coordinate)

    def to_dict(self, include_geom=True):
        geom_json = None
        if include_geom and self.geom is not None:
            try:
                geo_str = db.session.scalar(func.ST_AsGeoJSON(self.geom))
                geom_json = json.loads(geo_str) if geo_str else None
            except Exception:
                geom_json = None
        return {
            "place_id": self.place_id,
            "name": self.name,
            "alt_name": self.alt_name,
            "lat": self.lat,
            "lon": self.lon,
            "geom": geom_json,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

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
