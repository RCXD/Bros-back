from ..extensions import db
from datetime import datetime


class Reply(db.Model):
    __tablename__ = "replies"

    reply_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    content = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    likes = db.relationship("ReplyLike", backref="reply", lazy=True)
