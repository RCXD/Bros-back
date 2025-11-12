from ..extensions import db
from datetime import datetime

class History(db.Model):
    __tablename__ = "histories"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    path_id = db.Column(
        db.Integer, db.ForeignKey("my_paths.path_id", ondelete="CASCADE"), primary_key=True
    )
    created_at = db.Column(db.DateTime, default=datetime.now)

    # MyPath가 import 되어 있어야 함
    path = db.relationship(
        "MyPath",
        primaryjoin="History.path_id == MyPath.path_id",
        backref=db.backref("histories", lazy="dynamic")
    )
