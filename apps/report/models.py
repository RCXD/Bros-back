"""
Report model for content moderation
"""
import enum
from datetime import datetime
from apps.config.server import db


class ReportType(enum.Enum):
    """Types of content that can be reported"""
    USER = "USER"
    POST = "POST"
    REPLY = "REPLY"


class Report(db.Model):
    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    
    # What is being reported
    target_type = db.Column(db.Enum(ReportType), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    
    # Status tracking
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    reporter = db.relationship("User", backref=db.backref("reports_made", lazy="dynamic"), foreign_keys=[reporter_id])

    __table_args__ = (
        db.UniqueConstraint(
            "reporter_id",
            "target_type",
            "target_id",
            name="unique_report_per_user",
        ),
    )

    def __repr__(self):
        return f'<Report {self.report_id} - {self.target_type.name}:{self.target_id}>'
