import uuid
from datetime import datetime
from ..extensions import db


class Image(db.Model):
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
    user = db.relationship(
        "User", backref=db.backref("uploaded_images", lazy="dynamic")
    )
