"""
테스트 모듈 - 테스트 및 개발용 엔드포인트
"""
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required

from apps.config.server import db
from apps.auth.models import User
from apps.post.models import Post

bp = Blueprint("test", __name__)


@bp.get("/health")
def health_check():
    """헬스 체크 엔드포인트"""
    return jsonify({
        "status": "ok",
        "message": "서비스 정상 작동 중",
        "environment": current_app.config.get("ENV", "unknown")
    }), 200


@bp.get("/db")
def test_db():
    """
    데이터베이스 연결 테스트
    데이터베이스 연결 상태 및 기본 통계 반환
    """
    try:
        # 간단한 쿼리 시도
        user_count = User.query.count()
        post_count = Post.query.count()
        
        return jsonify({
            "status": "ok",
            "database": "연결됨",
            "stats": {
                "users": user_count,
                "posts": post_count
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "database": "연결 끊김",
            "error": str(e)
        }), 500


@bp.post("/email")
@jwt_required()
def test_email():
    """
    이메일 전송 기능 테스트
    JSON body:
        - recipient: 필수
        - subject: 선택
        - body: 선택
    """
    data = request.get_json()
    recipient = data.get("recipient")
    
    if not recipient:
        return jsonify({"error": "recipient는 필수입니다"}), 400
    
    # TODO: 이메일 서비스 설정 시 이메일 전송 구현
    return jsonify({
        "message": "이메일 서비스가 아직 구성되지 않았습니다",
        "note": f"전송 대상: {recipient}"
    }), 501


@bp.get("/config")
def test_config():
    """
    현재 설정 조회 (민감 정보 제외)
    배포 문제 디버깅에 유용
    """
    config_info = {
        "environment": current_app.config.get("ENV", "unknown"),
        "debug": current_app.config.get("DEBUG", False),
        "testing": current_app.config.get("TESTING", False),
        "database_type": "mysql" if "mysql" in current_app.config.get("SQLALCHEMY_DATABASE_URI", "").lower() else "unknown",
        "jwt_enabled": bool(current_app.config.get("JWT_SECRET_KEY")),
        "cors_enabled": True,  # 항상 활성화
    }
    
    return jsonify(config_info), 200


@bp.get("/redis")
def test_redis():
    """Redis 연결 테스트 (사용 가능한 경우)"""
    # TODO: Redis 통합 시 Redis 연결 테스트 구현
    return jsonify({
        "message": "Redis가 아직 통합되지 않았습니다",
        "note": "캐싱/세션을 위한 Redis 지원 추가 가능"
    }), 501


@bp.post("/error")
def test_error():
    """
    에러 처리 검증을 위한 테스트 에러 트리거
    Query params:
        - code: 시뮬레이션할 HTTP 에러 코드
    """
    code = request.args.get("code", 500, type=int)
    error_messages = {
        400: "잘못된 요청 테스트",
        401: "인증 실패 테스트",
        403: "권한 없음 테스트",
        404: "찾을 수 없음 테스트",
        500: "내부 서버 오류 테스트"
    }
    
    message = error_messages.get(code, f"오류 {code} 테스트")
    return jsonify({"error": message, "test": True}), code
