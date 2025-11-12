from ..extensions import db
from datetime import datetime
import enum

class NotificationType(enum.Enum):
    MENTION = "MENTION"         # 멘션
    POST_LIKE = "POST_LIKE"     # 게시글 좋아요
    REPLY_LIKE = "REPLY_LIKE"   # 댓글 좋아요
    COMMENT = "COMMENT"         # 새 댓글
    FOLLOW = "FOLLOW"           # 팔로우

class Notification(db.Model):
    __tablename__ = "notifications"

    notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 알림 유형
    type = db.Column(db.Enum(NotificationType), nullable=False)  # 예: "MENTION", "LIKE", "COMMENT"

    # 알림 발생자
    from_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    # 알림 수신자
    to_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    # 관련 대상 (선택적)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=True)
    reply_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id", ondelete="CASCADE"), nullable=True)
    mention_id = db.Column(db.Integer, db.ForeignKey("mentions.mention_id", ondelete="CASCADE"), nullable=True)

    # 읽음 여부
    is_checked = db.Column(db.Boolean, default=False)

    # 생성 시각
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 관계 설정
    from_user = db.relationship(
        "User",
        foreign_keys=[from_user_id],
        backref=db.backref("notifications_sent", lazy="dynamic", cascade="all, delete-orphan")
    )

    to_user = db.relationship(
        "User",
        foreign_keys=[to_user_id],
        backref=db.backref("notifications_received", lazy="dynamic", cascade="all, delete-orphan")
    )

    post = db.relationship(
        "Post",
        backref=db.backref("post_notifications", lazy="dynamic", cascade="all, delete-orphan")
    )

    reply = db.relationship(
        "Reply",
        backref=db.backref("reply_notifications", lazy="dynamic", cascade="all, delete-orphan")
    )

    mention = db.relationship(
        "Mention",
        backref=db.backref("mention_notifications", lazy="dynamic", cascade="all, delete-orphan")
    )

    def serialize(self):
        return {
            "notification_id": self.notification_id,
            "type": self.type,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "post_id": self.post_id,
            "reply_id": self.reply_id,
            "mention_id": self.mention_id,
            "is_checked": self.is_checked,
            "created_at": self.created_at.isoformat(),
        }
