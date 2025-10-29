from ..extensions import db
from datetime import datetime


class Emoji(db.Model):
    __tablename__ = "emojis"

    emoji_id = db.Column(db.Integer, primary_key=True)

    # ✅ 파일 경로 또는 base64 문자열 저장
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
