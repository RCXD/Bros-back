from ..extensions import db
from datetime import datetime
from sqlalchemy import event
from history import History

class History(db.Model):
    __tablename__ = "histories"

    # 저장한 유저의 아이디
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    # 경로 아이디
    path_id = db.Column(db.Integer, db.ForeignKey("paths.path_id"))
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship("User", backref=db.backref("histories", lazy="dynamic"))
    path = db.relationship("Path", backref=db.backref("histories", lazy="dynamic"))

    def __repr__(self):
        return f"<History history_id={self.history_id}, user_id={self.user_id}, path_id={self.path_id}>"

    __table_args__ = (
        db.UniqueConstraint("user_id", "path_id", name="unique_user_path_history"),
    )

    @event.listens_for(History, "before_insert")
    def check_duplicate_history(mapper, connection, target):
        """
        유저가 동일한 경로를 여러 번 저장하지 못하도록 방지
        """
        existing_history = (
            db.session.query(History)
            .filter_by(user_id=target.user_id, path_id=target.path_id)
            .first()
        )
        if existing_history:
            raise ValueError("이미 저장된 경로입니다.")
