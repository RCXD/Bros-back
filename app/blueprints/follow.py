from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Follow, User

bp = Blueprint("follow", __name__)

# 팔로우 등록
@bp.route("/apply/<int:target_id>", methods=["POST"])
@jwt_required()
def follow_user(target_id):
    current_user_id = get_jwt_identity()

    if current_user_id == target_id:
        return jsonify({"message": "자신을 팔로우할 수 없습니다"}), 400

    existing = Follow.query.filter_by(follower_id=current_user_id, following_id=target_id).first()
    if existing:
        return jsonify({"message": "이미 팔로우 중입니다"}), 400

    follow = Follow(follower_id=current_user_id, following_id=target_id)
    db.session.add(follow)
    db.session.commit()

    return jsonify({"message": "팔로우 완료"}), 201


# 팔로우 취소
@bp.route("/delete/<int:target_id>", methods=["DELETE"])
@jwt_required()
def unfollow_user(target_id):
    current_user_id = get_jwt_identity()

    follow = Follow.query.filter_by(follower_id=current_user_id, following_id=target_id).first()
    if not follow:
        return jsonify({"message": "팔로우 기록이 없습니다"}), 404

    db.session.delete(follow)
    db.session.commit()

    return jsonify({"message": f"user {target_id} 팔로우 취소 완료"}), 200


# 내가 팔로우하는 유저 목록 조회
@bp.route("/following", methods=["GET"])
@jwt_required()
def get_following():
    current_user_id = get_jwt_identity()
    followings = Follow.query.filter_by(follower_id=current_user_id).all()

    result = []
    for f in followings:
        user = User.query.get_or_404(f.following_id)
        result.append({
            "user_id": user.user_id,
            "nickname": user.nickname,
            "email": user.email
        })

    return jsonify(result), 200


# 나를 팔로우하는 유저 목록 조회
@bp.route("/followers", methods=["GET"])
@jwt_required()
def get_followers():
    current_user_id = get_jwt_identity()
    followers = Follow.query.filter_by(following_id=current_user_id).all()

    result = []
    for f in followers:
        user = User.query.get_or_404(f.follower_id)
        result.append({
            "user_id": user.user_id,
            "nickname": user.nickname,
            "email": user.email
        })

    return jsonify(result), 200
