from ..extensions import db
from datetime import datetime

class Post(db.Model):
    __tablename__ = "posts"

    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"))
    content = db.Column(db.Text)
    location = db.Column(db.Text)
    style = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now
    )

    likes = db.relationship("postLike", backref="post", lazy=True)
    mentions = db.relationship("Mention", backref="post", lazy=True)
    replies = db.relationship("Reply", backref="post", lazy=True)
    images = db.relationship("Image", backref="post", lazy=True)
