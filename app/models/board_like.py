from ..extensions import db


class BoardLike(db.Model):
    __tablename__ = "board_likes"

    board_id = db.Column(db.Integer, db.ForeignKey("boards.board_id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)
