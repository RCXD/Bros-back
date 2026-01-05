from datetime import datetime

from apps.config.server import db


class Hazard(db.Model):
    """사용자 신고나 센싱으로 수집된 위험 지점(장기 데이터)"""

    __tablename__ = "hazards"
    __table_args__ = (
        db.Index("idx_hazard_active_edge", "is_active", "edge_id"),
        db.Index("idx_hazard_active_osm_edge", "is_active", "osm_edge_id"),
        db.Index("idx_hazard_location", "lat", "lon"),
        {"extend_existing": True},
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
