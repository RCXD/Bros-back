from datetime import datetime
from sqlalchemy.types import JSON

from apps.config.server import db


class KSLink(db.Model):
    __tablename__ = "ks_links"
    # __table_args__ = (
    #     db.Index("idx_kslink_link_osm", "link_id", "osm_edges"),
    # ) 호환성문제 발생해서 주석처리

    link_id = db.Column(db.String(32), primary_key=True, index=True)
    f_node = db.Column(db.String(32))
    t_node = db.Column(db.String(32))
    geom = db.Column(JSON, nullable=False)
    osm_edges = db.Column(JSON)


class TrafficHazard(db.Model):
    __tablename__ = "traffic_hazards"
    __table_args__ = (
        db.Index("idx_traffic_hazard_link", "link_id"),
        db.Index("idx_traffic_hazard_edge", "osm_edge_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.String(32), index=True)
    osm_edge_id = db.Column(db.String(64), index=True)
    penalty = db.Column(db.Float, nullable=False, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class MyPath(db.Model):
    __tablename__ = "my_paths"

    path_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )
    path_name = db.Column(db.String(100), nullable=False)
    points = db.Column(JSON, nullable=False)  # [{"lat":..,"lon":..}, ...]
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def serialize(self):
        return {
            "path_id": self.path_id,
            "user_id": self.user_id,
            "name": self.path_name,
            "points": self.points,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Hazard(db.Model):
    __tablename__ = "hazards"
    __table_args__ = (
        db.Index("idx_hazard_active_edge", "is_active", "edge_id"),
        db.Index("idx_hazard_active_osm_edge", "is_active", "osm_edge_id"),
        db.Index("idx_hazard_location", "lat", "lon"),
    )

    hazard_id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False, index=True)
    lon = db.Column(db.Float, nullable=False, index=True)
    danger_score = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    edge_id = db.Column(db.String(64), index=True)
    osm_edge_id = db.Column(db.String(64), index=True)
    weight_penalty = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def serialize(self):
        return {
            "hazard_id": self.hazard_id,
            "lat": self.lat,
            "lon": self.lon,
            "danger_score": self.danger_score,
            "is_active": self.is_active,
            "edge_id": self.edge_id,
            "osm_edge_id": self.osm_edge_id,
            "weight_penalty": self.weight_penalty,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
