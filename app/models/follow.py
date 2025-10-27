from ..extensions import db

class Follow(db.Model):
    __tablename__ = "follows"

    follower_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), primary_key=True
    )
    following_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), primary_key=True
    )