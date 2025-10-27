from ..extensions import db
import enum


class ReportType(enum.Enum):
    USER = "USER"
    BOARD = "BOARD"
    REPLY = "BOARD"


class Report(db.Model):
    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    report_target = db.Column(db.Integer, nullable=False)
    report_type = db.Column(db.Enum(ReportType), nullable=False)
    report_count = db.Column(db.Integer, default=0)
