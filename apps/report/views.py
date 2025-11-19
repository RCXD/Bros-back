from flask import Blueprint, request, jsonify
from apps.config.server import db
from apps.report.models import Report, ReportType
from flask_jwt_extended import jwt_required, get_jwt_identity

bp = Blueprint("report", __name__)


# ----------------------------------
# 1. 사용자 신고 생성
# ----------------------------------
@bp.post("/report")
@jwt_required()
def create_report():
    """Create content report"""
    data = request.get_json()

    reporter_id = get_jwt_identity()  # JWT에서 사용자 id 가져오기
    target_type = data.get("target_type")
    target_id = data.get("target_id")
    reason = data.get("reason")  # 문자열 또는 리스트
    description = data.get("description", None)

    # 리스트면 쉼표로 합치기
    if isinstance(reason, list):
        reason = ",".join(reason)

    try:
        report = Report(
            reporter_id=reporter_id,
            target_type=ReportType[target_type],
            target_id=target_id,
            reason=reason,
            description=description,
        )
        db.session.add(report)
        db.session.commit()
        return (
            jsonify({"message": "Report created", "report_id": report.report_id}),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ----------------------------------
# 3. 사용자 본인 신고 조회
# ----------------------------------
@bp.get("/report/me")
@jwt_required()
def get_my_reports():
    """Get all reports created by the current user"""
    reporter_id = get_jwt_identity()
    reports = (
        Report.query.filter_by(reporter_id=reporter_id)
        .order_by(Report.created_at.desc())
        .all()
    )

    result = []
    for r in reports:
        result.append(
            {
                "report_id": r.report_id,
                "target_type": r.target_type.name,
                "target_id": r.target_id,
                "reason": r.reason.split(",") if r.reason else [],
                "description": r.description,
                "is_resolved": r.is_resolved,
                "created_at": r.created_at.isoformat(),
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
        )
    return jsonify(result), 200


# ----------------------------------
# 2. 관리자용 신고 조회
# ----------------------------------
@bp.get("/reports")
@jwt_required()
def get_reports():
    """Get all reports (admin only)"""
    # TODO: 관리자 여부 체크
    reports = Report.query.order_by(Report.created_at.desc()).all()
    result = []
    for r in reports:
        result.append(
            {
                "report_id": r.report_id,
                "reporter_id": r.reporter_id,
                "target_type": r.target_type.name,
                "target_id": r.target_id,
                "reason": r.reason.split(",") if r.reason else [],
                "description": r.description,
                "is_resolved": r.is_resolved,
                "created_at": r.created_at.isoformat(),
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
        )
    return jsonify(result), 200


# ----------------------------------
# 4. 사고 신고 생성
# ----------------------------------
@bp.post("/accident_report")
@jwt_required()
def report_accident():
    """Report road accident"""
    data = request.get_json()
    location = data.get("location")
    description = data.get("description")

    # TODO: 사고 신고 DB 모델 만들어서 저장
    return (
        jsonify(
            {
                "message": "Accident report received",
                "location": location,
                "description": description,
            }
        ),
        201,
    )
