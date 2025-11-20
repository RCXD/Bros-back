from datetime import datetime
import json

from sqlalchemy import func
from geoalchemy2 import Geometry
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import reconstructor
from sqlalchemy.types import JSON

from apps.config.server import db


class Place(db.Model):
    __tablename__ = "place"
    __table_args__ = (
        db.Index("idx_place_point", "point"),
        db.Index("idx_place_geom_spatial", "geom", mysql_prefix="SPATIAL"),
    )

    place_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    alt_name = db.Column(db.String(255))
    point = db.Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    geom = db.Column(Geometry(geometry_type="POLYGON", srid=4326))
    description = db.Column(db.Text)
    tags = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __init__(self, **kwargs):
        lat = kwargs.pop("lat", None)
        lon = kwargs.pop("lon", None)
        point = kwargs.pop("point", None)
        self._lat_cache = None
        self._lon_cache = None
        super().__init__(**kwargs)
        if point is not None:
            self.point = point
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
        return func.ST_GeomFromText(f"POINT({float(lon)} {float(lat)})", 4326)

    def set_lat_lon(self, lat, lon):
        if lat is None or lon is None:
            raise ValueError("lat and lon are required")
        lat_f = float(lat)
        lon_f = float(lon)
        self.point = self._point_from_latlon(lat_f, lon_f)
        self._lat_cache = lat_f
        self._lon_cache = lon_f

    @hybrid_property
    def lat(self):
        if self.point is None:
            return None
        if self._lat_cache is not None:
            return self._lat_cache
        value = db.session.scalar(func.ST_Y(self.point))
        self._lat_cache = float(value) if value is not None else None
        return self._lat_cache

    @lat.expression
    def lat(cls):
        return func.ST_Y(cls.point)

    @hybrid_property
    def lon(self):
        if self.point is None:
            return None
        if self._lon_cache is not None:
            return self._lon_cache
        value = db.session.scalar(func.ST_X(self.point))
        self._lon_cache = float(value) if value is not None else None
        return self._lon_cache

    @lon.expression
    def lon(cls):
        return func.ST_X(cls.point)

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
            "tags": self.tags,
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
            if other.point is not None and self.point is None:
                self.point = other.point
            session.delete(other)
            return True
        except Exception:
            session.rollback()
            return False
