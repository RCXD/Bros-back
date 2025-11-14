"""
Post model
"""
import uuid
from datetime import datetime
from apps.config.server import db


class Category(db.Model):
    """Post categories"""
    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f'<Category {self.category_name}>'


class Post(db.Model):
    __tablename__ = "posts"

    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
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
        return f'<Post {self.post_id}>'


class PostLike(db.Model):
    """Post likes"""
    __tablename__ = "post_likes"

    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)

    post = db.relationship("Post", backref=db.backref("likes", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("liked_posts", lazy="dynamic"))


class Image(db.Model):
    """Post images"""
    __tablename__ = "images"

    image_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(
        db.String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    directory = db.Column(db.Text, nullable=False)
    original_image_name = db.Column(db.String(255), nullable=False)
    ext = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    post = db.relationship("Post", backref=db.backref("images", lazy="joined"))
    user = db.relationship("User", backref=db.backref("uploaded_images", lazy="dynamic"))

    def __repr__(self):
        return f'<Image {self.image_id}>'
