"""
Reply model
"""
from datetime import datetime
from apps.config.server import db


class Reply(db.Model):
    __tablename__ = "replies"

    reply_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    children = db.relationship(
        "Reply", backref=db.backref("parent", remote_side=[reply_id]), lazy=True
    )
    author = db.relationship("User", backref="replies", lazy=True, foreign_keys=[user_id])
    post = db.relationship("Post", backref="replies", lazy=True)

    def __repr__(self):
        return f'<Reply {self.reply_id}>'


class ReplyLike(db.Model):
    """Reply likes"""
    __tablename__ = "reply_likes"

    reply_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)

    reply = db.relationship("Reply", backref=db.backref("likes", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("liked_replies", lazy="dynamic"))
