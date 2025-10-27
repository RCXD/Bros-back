from ..extensions import db


class UserReplyLike(db.Model):
    __tablename__ = "user_reply_likes"

    reply_id = db.Column(
        db.Integer, db.ForeignKey("replies.reply_id"), primary_key=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)
