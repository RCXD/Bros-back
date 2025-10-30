from ..extensions import db


class Location(db.Model):
    __tablename__ = "locations"

    location_id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_danger = db.Column(db.Boolean, default=False)
    risk_level = db.Column(db.Integer)

