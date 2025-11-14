"""
사용자 뷰 - 프로필, 팔로우, 친구 엔드포인트
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from apps.config.server import db
from apps.auth.models import User
from apps.user.models import Follow, Friend

bp = Blueprint("user", __name__)


@bp.get("/<int:user_id>")
def get_user(user_id):
    """ID로 사용자 프로필 조회"""
    user = User.query.get_or_404(user_id)
    
    # 팔로워 수 계산
    user.calculate_follower()
    db.session.commit()
    
    return jsonify(user.to_dict()), 200


@bp.post("/<int:user_id>/follow")
@jwt_required()
def follow_user(user_id):
    """사용자 팔로우"""
    current_user_id = int(get_jwt_identity())
    
    if current_user_id == user_id:
        return jsonify({"error": "자기 자신을 팔로우할 수 없습니다"}), 400
    
    # 대상 사용자 존재 확인
    target_user = User.query.get_or_404(user_id)
    
    # 이미 팔로우 중인지 확인
    existing = Follow.query.filter_by(
        follower_id=current_user_id,
        following_id=user_id
    ).first()
    
    if existing:
        return jsonify({"error": "이미 팔로우 중인 사용자입니다"}), 409
    
    try:
        follow = Follow(follower_id=current_user_id, following_id=user_id)
        db.session.add(follow)
        db.session.commit()
        
        return jsonify({"message": "팔로우 성공"}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "이미 팔로우 중인 사용자입니다"}), 409


@bp.delete("/<int:user_id>/follow")
@jwt_required()
def unfollow_user(user_id):
    """사용자 언팔로우"""
    current_user_id = int(get_jwt_identity())
    
    follow = Follow.query.filter_by(
        follower_id=current_user_id,
        following_id=user_id
    ).first()
    
    if not follow:
        return jsonify({"error": "팔로우 중이 아닙니다"}), 404
    
    db.session.delete(follow)
    db.session.commit()
    
    return jsonify({"message": "언팔로우 성공"}), 200


@bp.get("/<int:user_id>/followers")
def get_followers(user_id):
    """사용자의 팔로워 목록 조회"""
    # 사용자 존재 확인
    User.query.get_or_404(user_id)
    
    followers = Follow.query.filter_by(following_id=user_id).all()
    
    result = []
    for follow in followers:
        user = User.query.get(follow.follower_id)
        if user:
            result.append({
                "user_id": user.user_id,
                "username": user.username,
                "nickname": user.nickname,
                "profile_img": user.profile_img
            })
    
    return jsonify({"followers": result, "count": len(result)}), 200


@bp.get("/<int:user_id>/following")
def get_following(user_id):
    """이 사용자가 팔로우하는 사용자 목록 조회"""
    # 사용자 존재 확인
    User.query.get_or_404(user_id)
    
    following = Follow.query.filter_by(follower_id=user_id).all()
    
    result = []
    for follow in following:
        user = User.query.get(follow.following_id)
        if user:
            result.append({
                "user_id": user.user_id,
                "username": user.username,
                "nickname": user.nickname,
                "profile_img": user.profile_img
            })
    
    return jsonify({"following": result, "count": len(result)}), 200


@bp.post("/<int:user_id>/friend")
@jwt_required()
def send_friend_request(user_id):
    """친구 요청 보내기"""
    current_user_id = int(get_jwt_identity())
    
    if current_user_id == user_id:
        return jsonify({"error": "자기 자신을 친구로 추가할 수 없습니다"}), 400
    
    # 대상 사용자 존재 확인
    User.query.get_or_404(user_id)
    
    # 이미 친구인지 확인
    existing = Friend.query.filter_by(
        user_id=current_user_id,
        friend_user_id=user_id
    ).first()
    
    if existing:
        return jsonify({"error": "이미 친구입니다"}), 409
    
    try:
        # 양방향 친구 관계 생성
        friend1 = Friend(user_id=current_user_id, friend_user_id=user_id)
        friend2 = Friend(user_id=user_id, friend_user_id=current_user_id)
        
        db.session.add(friend1)
        db.session.add(friend2)
        db.session.commit()
        
        return jsonify({"message": "친구 추가 성공"}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "이미 친구입니다"}), 409


@bp.delete("/<int:user_id>/friend")
@jwt_required()
def remove_friend(user_id):
    """친구 관계 삭제"""
    current_user_id = int(get_jwt_identity())
    
    friend1 = Friend.query.filter_by(
        user_id=current_user_id,
        friend_user_id=user_id
    ).first()
    
    friend2 = Friend.query.filter_by(
        user_id=user_id,
        friend_user_id=current_user_id
    ).first()
    
    if not friend1:
        return jsonify({"error": "친구 관계가 아닙니다"}), 404
    
    # 양방향 친구 관계 삭제
    if friend1:
        db.session.delete(friend1)
    if friend2:
        db.session.delete(friend2)
    
    db.session.commit()
    
    return jsonify({"message": "친구 삭제 성공"}), 200


@bp.get("/me/friends")
@jwt_required()
def get_my_friends():
    """현재 사용자의 친구 목록 조회"""
    current_user_id = int(get_jwt_identity())
    
    friends = Friend.query.filter_by(user_id=current_user_id).all()
    
    result = []
    for friend in friends:
        user = User.query.get(friend.friend_user_id)
        if user:
            result.append({
                "user_id": user.user_id,
                "username": user.username,
                "nickname": user.nickname,
                "profile_img": user.profile_img,
                "created_at": friend.created_at.isoformat()
            })
    
    return jsonify({"friends": result, "count": len(result)}), 200
