"""
Security module - Reports and moderation
"""
from flask import Blueprint

bp = Blueprint("security", __name__)

@bp.post("/report")
def create_report():
    """Create content report"""
    return {"message": "Create report - TODO"}, 501

@bp.get("/reports")
def get_reports():
    """Get all reports (admin)"""
    return {"message": "Get reports - TODO"}, 501

@bp.post("/accident_report")
def report_accident():
    """Report road accident"""
    return {"message": "Report accident - TODO"}, 501
