from ..extensions import db
from datetime import datetime
from sqlalchemy.types import JSON

class MyPath(db.Model):
    __tablename__ = "my_paths"

    path_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    path_name = db.Column(db.String(100), nullable=True)
    points = db.Column(JSON, nullable=False)  # [{"lat":..,"lng":..}, ...] 형태
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    user = db.relationship("User", backref=db.backref("my_paths", lazy=True))

    def serialize(self):
        return {
            "path_id": self.path_id,
            "user_id": self.user_id,
            "path_name": self.path_name,
            "points": self.points,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
