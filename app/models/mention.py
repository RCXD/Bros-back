from ..extensions import db
from datetime import datetime


class Mention(db.Model):
    __tablename__ = "mentions"

    mention_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mentioned_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=True
    )
    reply_id = db.Column(
        db.Integer, db.ForeignKey("replies.reply_id", ondelete="CASCADE"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=datetime.now)
    is_checked = db.Column(db.Boolean, default=False)

    user = db.relationship(
        "User",
        backref=db.backref("mentions", lazy="dynamic", cascade="all, delete-orphan"),
        foreign_keys=[mentioned_user_id],
    )
    post = db.relationship(
        "Post",
        backref=db.backref("mentions", lazy="dynamic", cascade="all, delete-orphan"),
    )
    reply = db.relationship(
        "Reply",
        backref=db.backref("mentions", lazy="dynamic", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        db.CheckConstraint(
            "(post_id IS NOT NULL AND reply_id IS NULL) OR (post_id IS NULL AND reply_id IS NOT NULL)",
            name="check_one_target",
        ),
        db.UniqueConstraint(
            "mentioned_user_id", "post_id", "reply_id", name="unique_mention_target"
        ),
    )
