"""
User models - Follow, Friend relationships
"""

from apps.config.server import db
from datetime import datetime


class Follow(db.Model):
    """Follow relationship model"""

    __tablename__ = "follow"

    follow_id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    to_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("from_user_id", "to_user_id", name="unique_follow"),
    )


class Friend(db.Model):
    """Super-follow (friend) relationship model used to implement bookmarked following."""

    __tablename__ = "friend"

    friend_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    friend_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("user_id", "friend_user_id", name="unique_friend"),
    )
