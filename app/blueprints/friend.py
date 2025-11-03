from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Friend, Follow

bp = Blueprint("friend", __name__)

#  즐겨찾기(친한친구) 등록
@bp.route("/", methods=["POST"])
@jwt_required()
def add_friend():
    """
    즐겨찾기 등록
    - 로그인한 사용자가 팔로잉 중인 사람만 등록 가능
    """
    data = request.get_json() or {}
    current_user_id = get_jwt_identity()
    target_id = data.get("friend_id")

    if not target_id:
        return jsonify({"message": "friend_id는 필수입니다."}), 400
    if current_user_id == target_id:
        return jsonify({"message": "자기 자신은 즐겨찾기 등록 불가"}), 400

    # 팔로우 관계 확인
    follow = Follow.query.filter_by(follower_id=current_user_id, following_id=target_id).first()
    if not follow:
        return jsonify({"message": "팔로잉 중인 사용자만 즐겨찾기 등록 가능"}), 403

    # 중복 방지
    existing = Friend.query.filter_by(user_id=current_user_id, friend_id=target_id).first()
    if existing:
        return jsonify({"message": "이미 즐겨찾기 등록됨"}), 409

    new_friend = Friend(user_id=current_user_id, friend_id=target_id)
    db.session.add(new_friend)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "등록 실패"}), 400

    return jsonify({"message": "즐겨찾기 등록 완료"}), 201


#  즐겨찾기 삭제
@bp.route("delete/<int:friend_id>", methods=["DELETE"])
@jwt_required()
def remove_friend(friend_id):
    """
    즐겨찾기 해제
    """
    current_user_id = get_jwt_identity()
    record = Friend.query.filter_by(user_id=current_user_id, friend_id=friend_id).first()
    if not record:
        return jsonify({"message": "등록된 즐겨찾기 없음"}), 404

    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "즐겨찾기 해제 완료"}), 200


#  내 즐겨찾기 목록 조회
@bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_friends():
    """
    내가 즐겨찾기로 등록한 친구 목록 조회
    """
    current_user_id = get_jwt_identity()
    friends = Friend.query.filter_by(user_id=current_user_id).all()

    result = []
    for f in friends:
        result.append({
            "friend_id": f.friend_id,
            "nickname": f.friend.nickname if hasattr(f.friend, "nickname") else None,
            "user_id": f.user_id,
        })
    return jsonify(result), 200
