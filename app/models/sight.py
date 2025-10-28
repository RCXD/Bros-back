from ..extensions import db


class SightType(db.Model):
    __tablename__ = "sight_types"

    sight_type_id = db.Column(db.Integer, primary_key=True)
    sight_type_name = db.Column(db.String(255), nullable=False)
    sights = db.relationship("Sight", backref="sight_type", lazy=True)


class Sight(db.Model):
    __tablename__ = "sights"

    sight_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    sight_type_id = db.Column(db.Integer, db.ForeignKey("sight_types.sight_type_id"))
    score = db.Column(db.Integer)
