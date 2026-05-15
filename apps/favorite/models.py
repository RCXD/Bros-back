"""
즐겨찾기 모델
"""
import enum
from datetime import datetime
from apps.config.server import db


class FavoriteType(enum.Enum):
    """Enum of supported favorite item types."""
    STORY = "STORY"      # Post 카테고리
    ROUTE = "ROUTE"      # Post 카테고리
    REVIEW = "REVIEW"    # Post 카테고리
    REPORT = "REPORT"    # Post 카테고리
    PRODUCT = "PRODUCT"  # 상품
    PLACE = "PLACE"    # 장소


class Favorite(db.Model):
    """Represents a favorite item bookmarked by a user."""
    __tablename__ = "favorites"
    
    favorite_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    item_type = db.Column(db.Enum(FavoriteType), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    user = db.relationship("User", backref=db.backref("favorites", lazy="dynamic", cascade="all, delete-orphan"))
    
    # 복합 인덱스: 같은 사용자가 같은 아이템을 중복으로 즐겨찾기하지 못하도록
    __table_args__ = (
        db.UniqueConstraint('user_id', 'item_type', 'item_id', name='unique_user_favorite'),
        db.Index('idx_user_favorites', 'user_id', 'item_type'),
    )
    
    def to_dict(self):
        """Converts the favorite instance to a dictionary.

        Returns:
            A dict with favorite_id, user_id, item_type, item_id, and created_at fields.
        """
        return {
            "favorite_id": self.favorite_id,
            "user_id": self.user_id,
            "item_type": self.item_type.name,
            "item_id": self.item_id,
            "created_at": self.created_at.isoformat()
        }
    
    def __repr__(self):
        """Returns string representation of the Favorite instance."""
        return f"<Favorite(id={self.favorite_id}, user_id={self.user_id}, item_type='{self.item_type.name}', item_id={self.item_id})>"
