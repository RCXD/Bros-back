from ..extensions import db
from datetime import datetime


class Mention(db.Model):
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

    # 대상: 게시글 or 댓글
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.post_id", ondelete="CASCADE"), nullable=True
    )
    reply_id = db.Column(
        db.Integer, db.ForeignKey("replies.reply_id", ondelete="CASCADE"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_checked = db.Column(db.Boolean, default=False)

    # 관계 설정
    mentioner = db.relationship(
        "User",
        foreign_keys=[mentioner_id],
        backref=db.backref("mentions_sent", lazy="dynamic", cascade="all, delete-orphan"),
    )
    mentioned_user = db.relationship(
        "User",
        foreign_keys=[mentioned_user_id],
        backref=db.backref("mentions_received", lazy="dynamic", cascade="all, delete-orphan"),
    )
    post = db.relationship(
        "Post",
        backref=db.backref("post_mentions", lazy="dynamic", cascade="all, delete-orphan"),
    )
    reply = db.relationship(
        "Reply",
        backref=db.backref("reply_mentions", lazy="dynamic", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        db.CheckConstraint(
            "(post_id IS NOT NULL AND reply_id IS NULL) OR (post_id IS NULL AND reply_id IS NOT NULL)",
            name="check_one_target",
        ),
        db.UniqueConstraint(
            "mentioned_user_id", "post_id", "reply_id", name="unique_mention_target"
        ),
    )
