from ..extensions import db


class PostLike(db.Model):
    __tablename__ = "post_likes"

    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)

    post = db.relationship("Post", backref=db.backref("likes", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("liked_posts", lazy="dynamic"))
