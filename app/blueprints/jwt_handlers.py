from ..models import User
from flask import jsonify

# ======================================
# ✅ JWT 관련 설정 및 예외 처리
# ======================================
def register_jwt_handlers(jwt):

    # 1️⃣ JWT에 저장할 identity 값 정의
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        return user.user_id if isinstance(user, User) else user

    # 2️⃣ JWT로부터 실제 User 객체 로드
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        return User.query.get(identity)

    # 3️⃣ 토큰 관련 예외 처리 통일
    @jwt.unauthorized_loader
    def unauthorized_callback(err):
        return (
            jsonify(
                {
                    "error": "authorization_required",
                    "message": "Authorization 헤더가 필요합니다.",
                }
            ),
            401,
        )

    @jwt.invalid_token_loader
    def invalid_token_callback(err):
        return (
            jsonify({"error": "invalid_token", "message": "유효하지 않은 토큰입니다."}),
            401,
        )

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return (
            jsonify(
                {
                    "error": "token_expired",
                    "message": "토큰이 만료되었습니다. Refresh Token으로 재발급 받으세요.",
                }
            ),
            401,
        )

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return (
            jsonify(
                {
                    "error": "token_revoked",
                    "message": "이미 만료되었거나 로그아웃된 토큰입니다.",
                }
            ),
            401,
        )
