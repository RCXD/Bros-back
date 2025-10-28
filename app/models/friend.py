from ..extensions import db


class BestFriend(db.Model):
    __tablename__ = "friends"

    friend_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    friend_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
