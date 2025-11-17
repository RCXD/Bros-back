"""
즐겨찾기 모델
"""
import enum
from datetime import datetime
from apps.config.server import db


class FavoriteType(enum.Enum):
    """즐겨찾기 아이템 타입"""
    STORY = "STORY"      # Post 카테고리
    ROUTE = "ROUTE"      # Post 카테고리
    REVIEW = "REVIEW"    # Post 카테고리
    REPORT = "REPORT"    # Post 카테고리
    PRODUCT = "PRODUCT"  # 상품


class Favorite(db.Model):
    """즐겨찾기 모델"""
    __tablename__ = "favorites"
    
    favorite_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    item_type = db.Column(db.Enum(FavoriteType), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 복합 인덱스: 같은 사용자가 같은 아이템을 중복으로 즐겨찾기하지 못하도록
    __table_args__ = (
        db.UniqueConstraint('user_id', 'item_type', 'item_id', name='unique_user_favorite'),
        db.Index('idx_user_favorites', 'user_id', 'item_type'),
    )
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "favorite_id": self.favorite_id,
            "user_id": self.user_id,
            "item_type": self.item_type.name,
            "item_id": self.item_id,
            "created_at": self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f"<Favorite(id={self.favorite_id}, user_id={self.user_id}, item_type='{self.item_type.name}', item_id={self.item_id})>"
