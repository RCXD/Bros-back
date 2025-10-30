from ..extensions import db
from datetime import datetime


class Reply(db.Model):
    __tablename__ = "replies"

    reply_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    content = db.Column(db.String(200))
    parent_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    children = db.relationship("Reply", backref=db.backref("parent", remote_side=[reply_id]), lazy=True)
    likes = db.relationship("ReplyLike", backref="reply", lazy=True)
