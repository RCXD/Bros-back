"""
Reply model
"""
from datetime import datetime
from apps.config.server import db


class Reply(db.Model):
    __tablename__ = "replies"

    reply_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"))
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id", ondelete="CASCADE"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    children = db.relationship(
        "Reply", backref=db.backref("parent", remote_side=[reply_id]), lazy=True, cascade="all, delete-orphan"
    )
    author = db.relationship("User", backref="replies", lazy=True, foreign_keys=[user_id])
    post = db.relationship("Post", backref=db.backref("replies", lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Reply {self.reply_id}>'


class ReplyLike(db.Model):
    """Reply likes"""
    __tablename__ = "reply_likes"

    reply_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id", ondelete="CASCADE"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)

    reply = db.relationship("Reply", backref=db.backref("likes", lazy="dynamic", cascade="all, delete-orphan"))
    user = db.relationship("User", backref=db.backref("liked_replies", lazy="dynamic"))
