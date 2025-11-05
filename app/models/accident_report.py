from ..extensions import db
from datetime import datetime


class AccidentReport(db.Model):
    __tablename__ = "accident_reports"

    report_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    description = db.Column(db.Text)
    image = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    verified = db.Column(db.Boolean, default=False)
    ai_label = db.Column(db.String(255))
