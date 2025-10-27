from ..extensions import db


class BestFriend(db.Model):
    __tablename__ = "best_friends"

    best_friend_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    friend_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
