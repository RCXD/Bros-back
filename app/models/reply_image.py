from ..extensions import db
from datetime import datetime
import uuid


class ReplyImage(db.Model):
    __tablename__ = "reply_images"

    image_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    directory = db.Column(db.Text, nullable=False)
    original_image_name = db.Column(db.String(255), nullable=False)
    ext = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    post = db.relationship("Post", back_populates="reply_images")
    user = db.relationship("User", back_populates="reply_images")

    def __repr__(self):
        return f"<ReplyImage {self.image_id} - {self.original_image_name}>"