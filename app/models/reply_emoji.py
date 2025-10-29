from ..extensions import db
from datetime import datetime


class ReplyEmoji(db.Model):
    __tablename__ = "reply_emojis"

    emoji_id = db.Column(db.Integer, primary_key=True)
    reply_id = db.Column(db.Integer, db.ForeignKey("replies.reply_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

    # ✅ 파일 경로 또는 base64 문자열 저장
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
