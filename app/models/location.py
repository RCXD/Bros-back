from ..extensions import db
from datetime import datetime

class Location(db.Model):
    __tablename__ = "locations"

    location_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)  # 점 순서
    location_name = db.Column(db.String(100), nullable=True)  # 선택
    recommend_point = db.Column(db.Integer, default=0)
    risk_point = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    post = db.relationship("Post", backref="locations")
