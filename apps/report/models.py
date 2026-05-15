"""
Report model for content moderation
"""

import enum
from datetime import datetime
from apps.config.server import db


class ReportType(enum.Enum):
    """Enumeration of content types that can be reported."""

    USER = "USER"
    POST = "POST"
    REPLY = "REPLY"


class Report(db.Model):
    """SQLAlchemy model representing a content moderation report submitted by a user."""

    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

    # 신고 카테고리
    target_type = db.Column(db.Enum(ReportType), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)

    # 사유와 추가 설명
    reason = db.Column(db.String(255), nullable=False)  # 프론트에서 선택한 사유 문자열
    description = db.Column(db.Text, nullable=True)  # 자유롭게 작성하는 추가 설명

    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    resolved_at = db.Column(db.DateTime, nullable=True)

    reporter = db.relationship(
        "User",
        backref=db.backref("reports_made", lazy="dynamic"),
        foreign_keys=[reporter_id],
    )

    __table_args__ = (
        db.UniqueConstraint(
            "reporter_id",
            "target_type",
            "target_id",
            name="unique_report_per_user",
        ),
    )

    def __repr__(self):
        """Return a developer-readable representation of the report."""
        return f"<Report {self.report_id} - {self.target_type.name}:{self.target_id}>"
