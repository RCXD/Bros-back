from ..extensions import db
from datetime import datetime


class Post(db.Model):
    __tablename__ = "posts"

    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"))
    content = db.Column(db.Text, nullable=False)
    location = db.Column(db.Integer, db.ForeignKey("locations.location_id"))
    view_counts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    category = db.relationship("Category", backref="posts")

    def add_view_counts(self):
        self.view_counts = self.view_counts + 1