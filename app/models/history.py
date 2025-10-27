from ..extensions import db
from datetime import datetime

class History(db.Model):
    __tablename__ = "histories"

    history_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    path_id = db.Column(db.Integer, db.ForeignKey("paths.path_id"))
    created_at = db.Column(db.DateTime, default=datetime.now)
