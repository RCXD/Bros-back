"""
Image model
프로필, 게시글, 상품 이미지를 통합 관리하는 모델
"""

import uuid
from datetime import datetime
from apps.config.server import db


class Image(db.Model):
    """Unified image management model for profiles, posts, and products."""

    __tablename__ = "images"

    image_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(
        db.String(255), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )

    # 외래 키 - nullable=True로 설정하여 프로필/게시글/상품 중 하나만 연결
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=True,
    )

    # 이미지 정보
    directory = db.Column(db.Text, nullable=False)
    original_image_name = db.Column(db.String(255), nullable=False)
    ext = db.Column(db.String(10), nullable=False)

    # 상품 이미지 전용 필드
    image_type = db.Column(
        db.String(20), nullable=True
    )  # 'main', 'detail' for products
    display_order = db.Column(db.Integer, nullable=True)  # 상품 이미지 정렬 순서

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    post = db.relationship(
        "Post",
        backref=db.backref("images", lazy="joined", cascade="all, delete-orphan"),
    )
    user = db.relationship(
        "User", backref=db.backref("uploaded_images", lazy="dynamic")
    )
    product = db.relationship(
        "Product",
        backref=db.backref("images", lazy="dynamic", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        """Returns string representation of the Image instance."""
        return f"<Image {self.image_id} uuid={self.uuid}>"
