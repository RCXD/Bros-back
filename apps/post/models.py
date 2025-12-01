"""
Post model
"""

import uuid
from datetime import datetime
from apps.config.server import db


class CategoryType:
    """Centralized category definitions replacing the categories table."""

    STORY = "STORY"
    ROUTE = "ROUTE"
    REVIEW = "REVIEW"
    REPORT = "REPORT"

    ALL = {STORY, ROUTE, REVIEW, REPORT}

    # ID to name mapping (for backward compatibility with numeric IDs)
    ID_MAP = {
        "1": STORY,
        "2": ROUTE,
        "3": REVIEW,
        "4": REPORT,
    }

    @classmethod
    def has(cls, value: str) -> bool:
        """Return True when value matches any supported category."""
        return value in cls.ALL

    @classmethod
    def from_id(cls, category_id: str) -> str | None:
        """Convert category ID to category name. Returns None if invalid."""
        return cls.ID_MAP.get(str(category_id))


class Post(db.Model):
    __tablename__ = "posts"

    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"))
    category = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    view_counts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    location_name = db.Column(db.String(255), nullable=True)
    thumbnail_id = db.Column(
        db.Integer, db.ForeignKey("images.image_id", ondelete="SET NULL"), nullable=True
    )

    # Place 연동 (선택적)
    place_id = db.Column(
        db.Integer, db.ForeignKey("place.place_id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    author = db.relationship("User", backref="posts", lazy=True, foreign_keys=[user_id])
    place = db.relationship(
        "Place", backref="linked_posts", lazy=True, foreign_keys=[place_id]
    )
    thumbnail = db.relationship(
        "Image", foreign_keys=[thumbnail_id], uselist=False, post_update=True
    )

    def add_view_counts(self):
        """Increment view count"""
        self.view_counts = self.view_counts + 1

    def __repr__(self):
        return f"<Post {self.post_id}>"


class PostLike(db.Model):
    """Post likes"""

    __tablename__ = "post_likes"

    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"), primary_key=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )

    post = db.relationship(
        "Post",
        backref=db.backref("likes", lazy="dynamic", cascade="all, delete-orphan"),
    )
    user = db.relationship("User", backref=db.backref("liked_posts", lazy="dynamic"))
