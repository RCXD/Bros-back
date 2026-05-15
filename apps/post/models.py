"""
Post model
"""

import uuid
from datetime import datetime
from apps.config.server import db


class Category(db.Model):
    """Represents a post category."""

    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        """Returns string representation of the Category instance."""
        return f"<Category {self.category_name}>"


class Post(db.Model):
    """Represents a post authored by a user."""

    __tablename__ = "posts"

    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"))
    content = db.Column(db.Text, nullable=False)
    view_counts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    category = db.relationship("Category", backref="posts", lazy=True)
    author = db.relationship("User", backref="posts", lazy=True, foreign_keys=[user_id])

    def add_view_counts(self):
        """Increment view count"""
        self.view_counts = self.view_counts + 1

    def __repr__(self):
        """Returns string representation of the Post instance."""
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
