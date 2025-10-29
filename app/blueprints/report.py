from flask import Blueprint, request, jsonify
from ..models import Report
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from ..models.report import ReportType

bp = Blueprint('report', __name__)

# 신고 등록
@bp.route("/report", methods=["POST"])
@jwt_required()
def create_report():
    data = request.get_json() or {}
    current_user_id = get_jwt_identity()

    report_target_type = data.get("report_target_type")  # USER / POST / REPLY
    report_target_id = data.get("report_target_id")
    report_reason = data.get("report_reason")

    # 필수 입력값 체크
    if not all([report_target_type, report_target_id, report_reason]):
        return jsonify({"message": "report_target_type, report_target_id, report_reason 필수"}), 400

    # Enum 검증
    try:
        target_type_enum = ReportType[report_target_type.upper()]
    except KeyError:
        return jsonify({"message": "report_target_type는 USER, POST, REPLY만 가능합니다."}), 400

    # 중복 신고 방지
    existing = Report.query.filter_by(
        user_id=current_user_id,
        report_target_type=target_type_enum,
        report_target_id=report_target_id
    ).first()
    if existing:
        return jsonify({"message": "이미 신고한 대상입니다."}), 409

    report = Report(
        user_id=current_user_id,
        report_target_type=target_type_enum,
        report_target_id=report_target_id,
        report_reason=report_reason,
        created_at=datetime.utcnow()
    )
    db.session.add(report)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "신고 등록 실패"}), 500

    return jsonify({"message": "신고 등록 완료"}), 200

# 2. 본인이 등록한 신고 목록 조회
@bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_reports():
    current_user_id = get_jwt_identity()
    reports = Report.query.filter_by(user_id=current_user_id).all()
    result = []
    for r in reports:
        result.append({
            "report_id": r.report_id,
            "report_target_type": r.report_target_type.value,
            "report_target_id": r.report_target_id,
            "report_reason": r.report_reason,
            "created_at": r.created_at.isoformat()
        })
    return jsonify(result), 200

@bp.route("/reports", methods=["GET"])
@jwt_required()
def get_all_reports():
    # 추후 관리자 검증 추가 필요
    reports = Report.query.all()
    result = []
    for r in reports:
        result.append({
            "report_id": r.report_id,
            "user_id": r.user_id,
            "report_target_type": r.report_target_type.value,
            "report_target_id": r.report_target_id,
            "report_reason": r.report_reason,
            "created_at": r.created_at.isoformat()
        })
    return jsonify(result), 200