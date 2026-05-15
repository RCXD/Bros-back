"""
멘션 모델
"""

import enum
from datetime import datetime
from apps.config.server import db


class MentionItemType(enum.Enum):
    """Enumeration of content item types that can contain a mention."""

    POST = "POST"
    REPLY = "REPLY"


class Mention(db.Model):
    """SQLAlchemy model representing a user mention inside a post or reply."""

    __tablename__ = "mentions"

    mention_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 언급한 사람
    mentioner_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    # 언급당한 사람
    mentioned_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )

    # 대상: Favorite 모델과 동일한 방식
    item_type = db.Column(db.Enum(MentionItemType), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.now)
    is_checked = db.Column(db.Boolean, default=False)

    # 관계 설정
    mentioner = db.relationship(
        "User",
        foreign_keys=[mentioner_id],
        backref=db.backref(
            "mentions_sent", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )
    mentioned_user = db.relationship(
        "User",
        foreign_keys=[mentioned_user_id],
        backref=db.backref(
            "mentions_received", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "mentioned_user_id", "item_type", "item_id", name="unique_mention_target"
        ),
        db.Index("idx_mention_user", "mentioned_user_id", "is_checked"),
        db.Index("idx_mention_item", "item_type", "item_id"),
    )

    def to_dict(self):
        """Serialize the mention to a JSON-compatible dictionary.

        Returns:
            A dictionary containing all public mention fields.
        """
        return {
            "mention_id": self.mention_id,
            "mentioner_id": self.mentioner_id,
            "mentioned_user_id": self.mentioned_user_id,
            "item_type": self.item_type.value,
            "item_id": self.item_id,
            "is_checked": self.is_checked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        """Return a developer-readable representation of the mention."""
        return f"<Mention {self.mention_id}: {self.mentioner_id} → {self.mentioned_user_id} ({self.item_type.value}:{self.item_id})>"
