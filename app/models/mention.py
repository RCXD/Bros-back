from ..extensions import db


class Mention(db.Model):
    __tablename__ = "mentions"

    mention_id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey("boards.board_id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
