"""
사용자 뷰 - 프로필, 팔로우, 친구 엔드포인트
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

from apps.notification.models import Notification, NotificationType
from apps.notification.utils import (
    create_follow_notification,
    create_unfollow_notification,
)
from apps.config.server import db
from apps.auth.models import User
from apps.user.models import Follow, Friend

bp = Blueprint("user", __name__)


@bp.get("/api_info")
def api_info():
    """
    사용자 API 정보 제공 (개발용)
    """
    info = {
        "module": "user",
        "base_path": "/user",
        "description": "사용자 프로필 조회 및 팔로우 관리",
        "endpoints": [
            {
                "path": "/user/<user_id>",
                "method": "GET",
                "auth_required": False,
                "description": "특정 사용자 프로필 조회",
            },
            {
                "path": "/user/<user_id>/follow",
                "method": "PATCH",
                "auth_required": True,
                "description": "사용자 팔로우 토글 (추가/제거)",
            },
            {
                "path": "/user/<user_id>/followers",
                "method": "GET",
                "auth_required": False,
                "description": "팔로워 목록 조회",
            },
            {
                "path": "/user/<user_id>/following",
                "method": "GET",
                "auth_required": False,
                "description": "팔로잉 목록 조회",
            },
            {
                "path": "/user/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


@bp.get("/<int:user_id>")
def get_user(user_id):
    """ID로 사용자 프로필 조회"""
    user = User.query.get_or_404(user_id)

    # 팔로워 수 계산
    user.calculate_follower()
    db.session.commit()

    return jsonify(user.to_dict()), 200


@bp.patch("/<int:user_id>/follow")
@jwt_required()
def follow_user(user_id):
    """사용자 팔로우 토글"""
    current_user_id = int(get_jwt_identity())

    if current_user_id == user_id:
        return jsonify({"message": "자기 자신을 팔로우할 수 없습니다"}), 400

    # 대상 사용자 존재 확인
    target_user = User.query.get_or_404(user_id)

    # 현재 팔로우 상태 확인
    i_follow_them = Follow.query.filter_by(
        from_user_id=current_user_id, to_user_id=user_id
    ).first()

    they_follow_me = Follow.query.filter_by(
        from_user_id=user_id, to_user_id=current_user_id
    ).first()

    try:
        if i_follow_them:
            # 언팔로우
            db.session.delete(i_follow_them)
            db.session.commit()

            # 상태 결정
            if they_follow_me:
                status_message = "맞팔로우"  # 내가 팔로우 해제, 상대는 나를 팔로우
            else:
                status_message = "팔로우"  # 서로 팔로우하지 않음

            # 언팔로우 알림 전송
            create_unfollow_notification(current_user_id, user_id)

            return (
                jsonify(
                    {
                        "message": "언팔로우 성공",
                        "following": False,
                        "followed": they_follow_me is not None,
                        "status_message": status_message,
                    }
                ),
                200,
            )
        else:
            # 팔로우
            follow = Follow(from_user_id=current_user_id, to_user_id=user_id)
            db.session.add(follow)
            db.session.commit()

            # 상태 결정
            if they_follow_me:
                status_message = "맞팔로잉"  # 서로 팔로우
            else:
                status_message = "팔로잉"  # 내가 상대를 팔로우, 상대는 나를 팔로우 안함

            # 팔로우 알림 전송
            create_follow_notification(current_user_id, user_id, follow.follow_id)

            return (
                jsonify(
                    {
                        "message": "팔로우 성공",
                        "following": True,
                        "followed": they_follow_me is not None,
                        "status_message": status_message,
                    }
                ),
                201,
            )

    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "팔로우 처리 중 오류가 발생했습니다"}), 500


@bp.get("/<int:user_id>/followers")
def get_followers(user_id):
    """사용자의 팔로워 목록 조회"""
    # 사용자 존재 확인
    User.query.get_or_404(user_id)

    # 페이지네이션 파라미터
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    pagination = Follow.query.filter_by(to_user_id=user_id).paginate(
        page=page, per_page=per_page, error_out=False
    )
    followers = pagination.items

    result = []
    for follow in followers:
        user = User.query.get(follow.from_user_id)
        if user:
            result.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "profile_img": user.profile_img,
                }
            )

    return (
        jsonify(
            {
                "items": result,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


@bp.get("/<int:user_id>/following")
def get_following(user_id):
    """이 사용자가 팔로우하는 사용자 목록 조회"""
    # 사용자 존재 확인
    User.query.get_or_404(user_id)

    # 페이지네이션 파라미터
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    pagination = Follow.query.filter_by(from_user_id=user_id).paginate(
        page=page, per_page=per_page, error_out=False
    )
    following = pagination.items

    result = []
    for follow in following:
        user = User.query.get(follow.to_user_id)
        if user:
            result.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "profile_img": user.profile_img,
                }
            )

    return (
        jsonify(
            {
                "items": result,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


@bp.post("/<int:user_id>/friend")
@jwt_required()
def send_friend_request(user_id):
    """친구 요청 보내기"""
    current_user_id = int(get_jwt_identity())

    if current_user_id == user_id:
        return jsonify({"message": "자기 자신을 친구로 추가할 수 없습니다"}), 400

    # 대상 사용자 존재 확인
    User.query.get_or_404(user_id)

    # 이미 친구인지 확인
    existing = Friend.query.filter_by(
        user_id=current_user_id, friend_user_id=user_id
    ).first()

    if existing:
        return jsonify({"message": "이미 친구입니다"}), 409

    try:
        # 양방향 친구 관계 생성
        friend1 = Friend(user_id=current_user_id, friend_user_id=user_id)
        friend2 = Friend(user_id=user_id, friend_user_id=current_user_id)

        db.session.add(friend1)
        db.session.add(friend2)

        # 알림 발생 (commit 전에 import 추가)
        from apps.notification.utils import create_friend_request_notification

        db.session.commit()

        create_friend_request_notification(current_user_id, user_id)

        return jsonify({"message": "친구 추가 성공"}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "이미 친구입니다"}), 409


@bp.delete("/<int:user_id>/friend")
@jwt_required()
def remove_friend(user_id):
    """친구 관계 삭제"""
    current_user_id = int(get_jwt_identity())

    friend1 = Friend.query.filter_by(
        user_id=current_user_id, friend_user_id=user_id
    ).first()

    friend2 = Friend.query.filter_by(
        user_id=user_id, friend_user_id=current_user_id
    ).first()

    if not friend1:
        return jsonify({"message": "친구 관계가 아닙니다"}), 404

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
            result.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "profile_img": user.profile_img,
                    "created_at": friend.created_at.isoformat(),
                }
            )

    return jsonify({"friends": result, "count": len(result)}), 200
