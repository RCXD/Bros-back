"""
알림 모델
"""

import enum
from datetime import datetime
from apps.config.server import db


class NotificationType(enum.Enum):
    """알림 유형"""

    MENTION = "MENTION"  # 멘션
    POST_LIKE = "POST_LIKE"  # 게시글 좋아요
    REPLY_LIKE = "REPLY_LIKE"  # 댓글 좋아요
    FOLLOW = "FOLLOW"  # 팔로우
    UNFOLLOW = "UNFOLLOW"  # 언팔로우
    FRIEND_REQUEST = "FRIEND_REQUEST"  # 친구 등록
    REPLY = "REPLY"  # 댓글
    REPLY_TO_REPLY = "REPLY_TO_REPLY"  # 대댓글
    PRODUCT_RECOMMENDATION = "PRODUCT_RECOMMENDATION"  # 상품 추천


class NotificationItemType(enum.Enum):
    """알림 대상 아이템 타입"""

    POST = "POST"
    REPLY = "REPLY"
    MENTION = "MENTION"
    PRODUCT = "PRODUCT"
    FOLLOW = "FOLLOW"
    USER = "USER"


class Notification(db.Model):
    """알림 모델"""

    __tablename__ = "notifications"

    notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 알림 메시지
    message = db.Column(db.String(255), nullable=True)

    # 알림 유형
    type = db.Column(db.Enum(NotificationType), nullable=False)

    # 알림 발생자
    from_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    # 알림 수신자
    to_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    # 관련 대상 (Favorite 모델과 동일한 방식)
    item_type = db.Column(db.Enum(NotificationItemType), nullable=True)
    item_id = db.Column(db.Integer, nullable=True)

    # 바로가기 URL (추후 DB 업데이트 시 활성화)
    # url = db.Column(db.String(500), nullable=True)

    # 읽음 여부
    is_checked = db.Column(db.Boolean, default=False)

    # 생성 시각
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 관계 설정
    from_user = db.relationship(
        "User",
        foreign_keys=[from_user_id],
        backref=db.backref(
            "notifications_sent", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    to_user = db.relationship(
        "User",
        foreign_keys=[to_user_id],
        backref=db.backref(
            "notifications_received", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    __table_args__ = (
        db.Index("idx_notification_receiver", "to_user_id", "is_checked"),
        db.Index("idx_notification_item", "item_type", "item_id"),
    )

    def to_dict(self, follow_state_map=None):
        """
        알림 정보를 직렬화
        """
        if self.from_user:
            from_user_info = {
                "user_id": self.from_user.user_id,
                "username": self.from_user.username,
                "nickname": getattr(self.from_user, "nickname", None),
                "profile_img": getattr(self.from_user, "profile_img", None),
            }
        else:
            from_user_info = None

        if from_user_info and follow_state_map:
            follow_state = follow_state_map.get(self.from_user_id)
            if follow_state:
                from_user_info["follow_state"] = follow_state

        return {
            "notification_id": self.notification_id,
            "type": self.type.value,
            "message": self.message,
            "from_user_id": self.from_user_id,
            "from_user": from_user_info,
            "to_user_id": self.to_user_id,
            "item_type": self.item_type.value if self.item_type else None,
            "item_id": self.item_id,
            "url": getattr(self, "url", None),  # 추후 DB 컬럼 추가 시 활성화
            "is_checked": self.is_checked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    # === LEGACY: app/models/notification.py의 serialize() 메서드 (호환성) ===
    def serialize(self):
        """레거시 호환용 serialize 메서드 - to_dict()와 동일"""
        return self.to_dict()

    # === END LEGACY ===

    def __repr__(self):
        return f"<Notification {self.notification_id} - {self.type.value} from {self.from_user_id} to {self.to_user_id}>"
