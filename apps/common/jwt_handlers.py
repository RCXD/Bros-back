"""
JWT handlers and callbacks
"""
from flask import jsonify
from apps.config.server import BLACKLIST


def register_jwt_handlers(jwt_manager):
    """Register JWT handlers for the application"""
    
    @jwt_manager.user_identity_loader
    def user_identity_lookup(user):
        """Define the identity value to store in JWT"""
        from apps.auth.models import User
        return user.user_id if isinstance(user, User) else user
    
    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Load actual User object from JWT"""
        from apps.auth.models import User
        identity = jwt_data["sub"]
        return User.query.get(identity)
    
    @jwt_manager.unauthorized_loader
    def unauthorized_callback(err):
        """Handle missing authorization header"""
        return jsonify({
            "error": "authorization_required",
            "message": "Authorization 헤더가 필요합니다."
        }), 401
    
    @jwt_manager.invalid_token_loader
    def invalid_token_callback(err):
        """Handle invalid token"""
        return jsonify({
            "error": "invalid_token",
            "message": "유효하지 않은 토큰입니다."
        }), 401
    
    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Handle expired token"""
        return jsonify({
            "error": "token_expired",
            "message": "토큰이 만료되었습니다."
        }), 401
    
    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Handle revoked token"""
        return jsonify({
            "error": "token_revoked",
            "message": "이미 만료되었거나 로그아웃된 토큰입니다."
        }), 401
    
    @jwt_manager.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        """Check if token is in blocklist"""
        jti = jwt_payload["jti"]
        return jti in BLACKLIST
