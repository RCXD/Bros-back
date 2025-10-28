from ..extensions import db
from datetime import datetime
import enum

class ReportType(enum.Enum):
    USER = "USER"
    POST = "POST"
    REPLY = "REPLY"

class Report(db.Model):
    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    report_target_type = db.Column(db.Enum(ReportType), nullable=False)
    report_target_id = db.Column(db.Integer, nullable=False)
    report_reason = db.Column(db.String(255), nullable=False)
    report_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("reports_made", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "report_target_type", "report_target_id", name="unique_report_per_user"),
    )
