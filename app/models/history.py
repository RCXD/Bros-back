from ..extensions import db
from datetime import datetime
from sqlalchemy import event


class History(db.Model):
    __tablename__ = "histories"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    path_id = db.Column(
        db.Integer, db.ForeignKey("paths.path_id", ondelete="CASCADE"), primary_key=True
    )
    created_at = db.Column(db.DateTime, default=datetime.now)

    path = db.relationship("Path", backref=db.backref("histories", lazy="dynamic"))


@event.listens_for(History, "before_insert")
def check_duplicate_history(mapper, connection, target):
    existing_history = (
        db.session.query(History)
        .filter_by(user_id=target.user_id, path_id=target.path_id)
        .first()
    )
    if existing_history:
        raise ValueError("이미 저장된 경로입니다.")
