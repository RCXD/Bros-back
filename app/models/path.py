from ..extensions import db


class Path(db.Model):
    __tablename__ = "paths"

    path_id = db.Column(db.Integer, primary_key=True)
    start_latitude = db.Column(db.Float, nullable=False)
    start_longitude = db.Column(db.Float, nullable=False)
    arrive_latitude = db.Column(db.Float, nullable=False)
    arrive_longitude = db.Column(db.Float, nullable=False)
