from flask import Blueprint, request, jsonify
from ..models import Post, Image
from ..extensions import db, jwt
from flask_jwt_extended import get_current_user, jwt_required, get_jwt_identity
from ..utils.image_storage import save_image

bp = Blueprint("mypage", __name__)

@bp.route("/", methods=["GET"])
@jwt_required()
def get_info():
    current_user = get_current_user()
    if not current_user:
        return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

    user_info = {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "address": current_user.address,
        "profile_img": current_user.profile_img,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login,
        "follower_count": current_user.follower_count,
    }
    return jsonify(user_info), 200
