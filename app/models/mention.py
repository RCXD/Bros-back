from ..extensions import db
from datetime import datetime
import enum


class MentionType(enum.Enum):
    POST = "POST",
    REPLY = "REPLY",
    SUBREPLY = "SUBREPLY"
# post, reply, subreply id로 누가 멘션한건지 찾으면 됨

class Mention(db.Model):
    __tablename__ = "mentions"

    mention_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_type = db.Column(db.Enum(MentionType), nullable=False)
    object_id = db.Column(db.Integer, nullable=False)
    mentioned_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), nullable=True)
    is_checked = db.Column(db.Boolean, default=False)

    user = db.relationship(
        "User",
        backref=db.backref("mentions", lazy="dynamic"),
        foreign_keys=[mentioned_user_id]
    )


    __table_args__ = (
        db.UniqueConstraint(
            "content_type", "object_id", "mentioned_user_id", name="unique_mention"
        ),
    )
