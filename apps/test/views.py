"""
테스트 모듈
"""

from flask import Blueprint, jsonify

bp = Blueprint("test", __name__)


@bp.get("/api_info")
def api_info():
    """
    테스트 API 정보 제공 (개발용)
    """
    info = {
        "module": "test",
        "base_path": "/test",
        "description": "테스트 및 개발 지원 엔드포인트",
        "endpoints": [
            {
                "path": "/test/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            }
        ],
    }
    return jsonify(info), 200
