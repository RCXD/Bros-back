from ..extensions import db
from datetime import datetime

class Board(db.Model):
    __tablename__ = "boards"

    board_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"))
    content = db.Column(db.Text)
    location = db.Column(db.Text)
    style = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now
    )

    likes = db.relationship("BoardLike", backref="board", lazy=True)
    mentions = db.relationship("Mention", backref="board", lazy=True)
    replies = db.relationship("Reply", backref="board", lazy=True)
    images = db.relationship("Image", backref="board", lazy=True)
