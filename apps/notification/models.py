"""
알림 모델
"""

import enum
from datetime import datetime
from apps.config.server import db


class NotificationType(enum.Enum):
    """알림 유형"""

    # === LEGACY: app/models/notification.py에서 가져온 타입 ===
    MENTION = "MENTION"  # 멘션 (레거시)
    POST_LIKE = "POST_LIKE"  # 게시글 좋아요 (레거시)
    REPLY_LIKE = "REPLY_LIKE"  # 댓글 좋아요 (레거시)
    COMMENT = "COMMENT"  # 새 댓글 (레거시: REPLY와 동일 개념)
    FOLLOW = "FOLLOW"  # 팔로우 (레거시)
    # === END LEGACY ===

    # === 기존 apps/notification 타입 (레거시와 중복되지 않는 것만 유지) ===
    FRIEND_REQUEST = "FRIEND_REQUEST"  # 친구 등록
    REPLY = "REPLY"  # 댓글 (COMMENT와 동일, 호환성 유지)
    REPLY_TO_REPLY = "REPLY_TO_REPLY"  # 대댓글
    PRODUCT_RECOMMENDATION = "PRODUCT_RECOMMENDATION"  # 상품 추천
    # === END 기존 타입 ===


class Notification(db.Model):
    """알림 모델"""

    __tablename__ = "notifications"

    notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

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

    # 관련 대상 (선택적)
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=True
    )
    reply_id = db.Column(
        db.Integer, db.ForeignKey("replies.reply_id", ondelete="CASCADE"), nullable=True
    )
    mention_id = db.Column(
        db.Integer,
        db.ForeignKey("mentions.mention_id", ondelete="CASCADE"),
        nullable=True,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=True,
    )

    # 읽음 여부
    is_checked = db.Column(db.Boolean, default=False)

    # 생성 시각
    created_at = db.Column(db.DateTime, default=datetime.now)

    # === 관계 설정 (LEGACY와 동일) ===
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

    post = db.relationship(
        "Post",
        backref=db.backref(
            "post_notifications", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    reply = db.relationship(
        "Reply",
        backref=db.backref(
            "reply_notifications", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )
    # === REMOVED from LEGACY: mention relationship (레거시에 있었으나 apps에서 제거됨) ===
    # mention = db.relationship("Mention", backref=db.backref("mention_notifications", ...))
    # === END REMOVED ===

    def to_dict(self):
        """
        알림 정보를 딕셔너리로 변환

        === LEGACY vs 기존 비교 ===
        - LEGACY (serialize): from_user 정보 없이 단순 필드만 반환
        - 기존 (to_dict): from_user 상세 정보 포함
        - 선택: 기존 apps 버전 유지 (더 많은 정보 제공)
        === 변경사항 ===
        - profile_image -> profile_img (필드명 통일)
        - nickname 필드 추가
        === END ===
        """
        return {
            "notification_id": self.notification_id,
            "type": self.type.value,
            "from_user_id": self.from_user_id,
            "from_user": (
                {
                    "user_id": self.from_user.user_id,
                    "username": self.from_user.username,
                    "nickname": getattr(self.from_user, "nickname", None),
                    "profile_img": getattr(
                        self.from_user, "profile_img", None
                    ),  # LEGACY: profile_image -> profile_img
                }
                if self.from_user
                else None
            ),
            "to_user_id": self.to_user_id,
            "post_id": self.post_id,
            "reply_id": self.reply_id,
            "mention_id": self.mention_id,
            "product_id": self.product_id,  # LEGACY에 없던 필드 (apps에서 추가)
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
