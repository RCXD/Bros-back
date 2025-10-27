from ..extensions import db


class Image(db.Model):
    __tablename__ = "images"

    image_id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey("boards.board_id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    directory = db.Column(db.Text)
    original_image_name = db.Column(db.String(255))
    ext = db.Column(db.String(10))
