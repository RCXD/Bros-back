"""
보안 모듈 - 신고 및 관리
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user

from apps.config.server import db
from apps.report.models import Report, ReportType

bp = Blueprint("security", __name__)


@bp.post("/reports")
@jwt_required()
def create_report():
    """
    콘텐츠 신고 생성
    JSON body:
        - target_type: 필수 (USER, POST, REPLY)
        - target_id: 필수
        - reason: 필수
        - description: 선택
    """
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        target_type = data.get("target_type")
        target_id = data.get("target_id")
        reason = data.get("reason")
        
        if not all([target_type, target_id, reason]):
            return jsonify({"error": "target_type, target_id, reason은 필수입니다"}), 400
        
        # target_type 검증
        try:
            report_type = ReportType[target_type.upper()]
        except KeyError:
            return jsonify({"error": f"유효하지 않은 target_type입니다. 다음 중 하나여야 합니다: {[t.name for t in ReportType]}"}), 400
        
        # 이미 신고했는지 확인
        existing = Report.query.filter_by(
            reporter_id=current_user.user_id,
            target_type=report_type,
            target_id=target_id
        ).first()
        
        if existing:
            return jsonify({"error": "이미 신고한 콘텐츠입니다"}), 409
        
        report = Report(
            reporter_id=current_user.user_id,
            target_type=report_type,
            target_id=target_id,
            reason=reason
        )
        
        db.session.add(report)
        db.session.commit()
        
        return jsonify({
            "message": "신고가 제출되었습니다",
            "report_id": report.report_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"신고 생성 실패: {str(e)}"}), 400


@bp.get("/reports")
@jwt_required()
def get_my_reports():
    """현재 사용자가 제출한 신고 조회"""
    current_user_id = int(get_jwt_identity())
    
    reports = Report.query.filter_by(reporter_id=current_user_id)\
        .order_by(Report.created_at.desc()).all()
    
    result = []
    for report in reports:
        result.append({
            "report_id": report.report_id,
            "target_type": report.target_type.name,
            "target_id": report.target_id,
            "reason": report.reason,
            "is_resolved": report.is_resolved,
            "created_at": report.created_at.isoformat(),
            "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None
        })
    
    return jsonify({"reports": result, "count": len(result)}), 200


@bp.get("/reports/<int:report_id>")
@jwt_required()
def get_report(report_id):
    """특정 신고 상세 조회"""
    current_user_id = int(get_jwt_identity())
    report = Report.query.get_or_404(report_id)
    
    # 소유권 확인
    if report.reporter_id != current_user_id:
        return jsonify({"error": "권한이 없습니다"}), 403
    
    return jsonify({
        "report_id": report.report_id,
        "target_type": report.target_type.name,
        "target_id": report.target_id,
        "reason": report.reason,
        "is_resolved": report.is_resolved,
        "created_at": report.created_at.isoformat(),
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None
    }), 200


@bp.delete("/reports/<int:report_id>")
@jwt_required()
def cancel_report(report_id):
    """신고 취소 (아직 처리되지 않은 경우)"""
    try:
        current_user_id = int(get_jwt_identity())
        report = Report.query.get_or_404(report_id)
        
        # 소유권 확인
        if report.reporter_id != current_user_id:
            return jsonify({"error": "권한이 없습니다"}), 403
        
        # 미처리 신고만 취소 가능
        if report.is_resolved:
            return jsonify({"error": "처리 완료된 신고는 취소할 수 없습니다"}), 400
        
        db.session.delete(report)
        db.session.commit()
        
        return jsonify({"message": "신고가 취소되었습니다"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"신고 취소 실패: {str(e)}"}), 400


@bp.post("/accidents")
@jwt_required()
def report_accident():
    """
    도로 사고 또는 위험 요소 신고
    JSON body:
        - lat: 필수
        - lon: 필수
        - type: 필수 (accident, hazard, roadwork 등)
        - severity: 필수 (low, medium, high, critical)
        - description: 필수
        - images: 선택
    """
    try:
        # TODO: AccidentReport 모델 통합 시 구현
        return jsonify({
            "message": "사고 신고 기능 통합 대기 중",
            "note": "AccidentReport 모델 추가 필요"
        }), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/accidents")
def get_accidents():
    """
    최근 사고/위험 요소 조회
    Query params:
        - lat: 중심 위도
        - lon: 중심 경도
        - radius: 검색 반경(km)
        - type: 유형별 필터
    """
    # TODO: AccidentReport 모델 통합 시 구현
    return jsonify({
        "accidents": [],
        "message": "사고 신고 기능 통합 대기 중"
    }), 200


@bp.get("/accidents/<int:accident_id>")
def get_accident(accident_id):
    """특정 사고 상세 조회"""
    # TODO: AccidentReport 모델 통합 시 구현
    return jsonify({"message": "사고 신고 기능 통합 대기 중"}), 501


@bp.put("/accidents/<int:accident_id>")
@jwt_required()
def update_accident(accident_id):
    """사고 신고 수정 (신고자만)"""
    # TODO: AccidentReport 모델 통합 시 구현
    return jsonify({"message": "사고 신고 기능 통합 대기 중"}), 501


@bp.delete("/accidents/<int:accident_id>")
@jwt_required()
def delete_accident(accident_id):
    """사고 신고 삭제 (신고자 또는 관리자)"""
    # TODO: AccidentReport 모델 통합 시 구현
    return jsonify({"message": "사고 신고 기능 통합 대기 중"}), 501
