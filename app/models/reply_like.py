from ..extensions import db


class ReplyLike(db.Model):
    __tablename__ = "reply_likes"

    # 복합 기본 키 설정
    reply_id = db.Column(
        db.Integer, db.ForeignKey("replies.reply_id"), primary_key=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)
