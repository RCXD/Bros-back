from datetime import datetime
import json
from sqlalchemy import func
# from sqlalchemy.dialects.mysql import GEOMETRY
from sqlalchemy.types import JSON

from apps.config.server import db


class Place(db.Model):
    __tablename__ = "place"
    __table_args__ = (
        db.Index("idx_place_lat_lon", "lat", "lon"),
        # db.Index("idx_place_geom_spatial", "geom", mysql_prefix="SPATIAL"),
    )

    place_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    alt_name = db.Column(db.String(255))
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    edges = db.Column(JSON)  # for storing area boundary edges if needed
    # geom = db.Column(GEOMETRY(srid=4326))
    description = db.Column(db.Text)
    tags = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        # geom_json = None
        # if self.geom is not None:
        #     try:
        #         geo_str = db.session.scalar(func.ST_AsGeoJSON(self.geom))
        #         geom_json = json.loads(geo_str) if geo_str else None
        #     except Exception:
        #         try:
        #             db.session.rollback()
        #         except Exception:
        #             pass
        #         geom_json = None
        return {
            "place_id": self.place_id,
            "name": self.name,
            "alt_name": self.alt_name,
            "lat": self.lat,
            "lon": self.lon,
            # "geom": geom_json,
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
        """
        Minimal merge: prefer richer metadata/tags and remove duplicate record.
        """
        session = session or db.session
        try:
            if other.alt_name and not self.alt_name:
                self.alt_name = other.alt_name
            if other.description and (
                not self.description or len(other.description) > len(self.description)
            ):
                self.description = other.description
            if other.tags:
                if not self.tags:
                    self.tags = other.tags
                elif isinstance(self.tags, dict) and isinstance(other.tags, dict):
                    merged = self.tags.copy()
                    merged.update(other.tags)
                    self.tags = merged
                elif isinstance(self.tags, list) and isinstance(other.tags, list):
                    self.tags = list({json.dumps(t): t for t in (self.tags + other.tags)}.values())
            # if other.geom and not self.geom:
            #     self.geom = other.geom
            session.delete(other)
            return True
        except Exception:
            session.rollback()
            return False
