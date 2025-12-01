from datetime import datetime
from sqlalchemy.types import JSON

from apps.config.server import db


class KSLink(db.Model):
    """국토부 KS 도로 링크 정보를 보관하는 정적 테이블"""

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
    """실시간/단기 교통 위험(예: 사고) 가중치를 저장"""

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


class Route(db.Model):
    """사용자가 직접 저장한 경로(즐겨찾기 경로). Post/Place 모두 route_id를 통해 참조한다."""

    __tablename__ = "routes"

    route_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    points = db.Column(JSON, nullable=False)  # [{"lat":..,"lon":..}, ...]
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Place 연동 (1:1)
    place = db.relationship("Place", back_populates="route", uselist=False)

    def serialize(self):
        return {
            "route_id": self.route_id,
            "user_id": self.user_id,
            "name": self.name,
            "points": self.points,
            "place_id": self.place.place_id if self.place else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
