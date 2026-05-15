"""
사용자 뷰 - 프로필, 팔로우, 친구 엔드포인트
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.exc import IntegrityError

from apps.notification.models import Notification, NotificationType
from apps.config.server import db
from apps.auth.models import User, AccountType
from apps.user.models import Follow, Friend
from apps.user.reward_utils import (
    reward_follower_gained,
    reward_follow_special_user,
    get_user_reward_summary,
    get_user_medal,
    get_medal_by_points,
    get_user_league_info,
    MEDAL_TIERS,
)

bp = Blueprint("user", __name__)


@bp.get("/api_info")
def api_info():
    """Return API endpoint information for the user module (development use).

    Returns:
        JSON response with 200 status containing a description of all user endpoints.
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
    """Retrieve a user's public profile by their ID.

    Recalculates and persists the follower count before returning.

    Args:
        user_id: The ID of the user to retrieve.

    Returns:
        JSON response with 200 status containing the user's profile data.
        Returns 404 if the user does not exist.
    """
    user = User.query.get_or_404(user_id)

    # 팔로워 수 계산
    user.calculate_follower()
    db.session.commit()

    return jsonify(user.to_dict()), 200


@bp.patch("/<int:user_id>/follow")
@jwt_required()
def follow_user(user_id):
    """Toggle a follow relationship between the current user and a target user.

    Requires JWT authentication. Follows the target if not already following;
    unfollows otherwise. Awards reward points on a successful follow action.

    Args:
        user_id: The ID of the user to follow or unfollow.

    Returns:
        JSON response with 201 status when a follow is created, or 200 when removed.
        Both responses include the updated follow/followed flags and a status message.
        Returns 400 if the user attempts to follow themselves.

    Raises:
        400: If the current user tries to follow themselves.
        500: On database integrity error.
    """
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

            # 리워드 지급
            # 팔로우 당한 사람에게 리워드
            reward_follower_gained(user_id)
            # 특별 유저 팔로우 시 팔로우한 사람에게도 리워드
            reward_follow_special_user(current_user_id, target_user)

            # 상태 결정
            if they_follow_me:
                status_message = "맞팔로잉"  # 서로 팔로우
            else:
                status_message = "팔로잉"  # 내가 상대를 팔로우, 상대는 나를 팔로우 안함

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
    """Retrieve a paginated list of users who follow the specified user.

    Args:
        user_id: The ID of the user whose followers to retrieve.

    Query params:
        page: Page number (default: 1).
        per_page: Items per page (default: 20).

    Returns:
        JSON response with 200 status containing paginated follower user data.
        Returns 404 if the user does not exist.
    """
    # 사용자 존재 확인
    User.query.get_or_404(user_id)

    # 페이지네이션 파라미터
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)

    # 최적화 전 버전 - N+1 문제 발생 가능
    # pagination = Follow.query.filter_by(to_user_id=user_id).paginate(
    #     page=page, per_page=per_page, error_out=False
    # )
    # followers = pagination.items

    # result = []
    # for follow in followers:
    #     user = User.query.get(follow.from_user_id)
    #     if user:
    #         result.append(
    #             {
    #                 "user_id": user.user_id,
    #                 "username": user.username,
    #                 "nickname": user.nickname,
    #                 "profile_img": user.profile_img,
    #             }
    #         )

    # return (
    #     jsonify(
    #         {
    #             "items": result,
    #             "total": pagination.total,
    #             "pages": pagination.pages,
    #             "page": page,
    #             "per_page": per_page,
    #             "has_next": pagination.has_next,
    #             "has_prev": pagination.has_prev,
    #         }
    #     ),
    #     200,
    # )

    # 최적화 버전 : JOIN을 사용해 Follow + User 한 번에 조회
    pagination = (
        db.session.query(User)
        .join(Follow, Follow.from_user_id == User.user_id)
        .filter(Follow.to_user_id == user_id)
        .paginate(page=page, per_page=per_page,
        error_out=False)
    )

    followers = pagination.items

    result = [
        {
            "user_id" : follower.user_id,
            "username" : follower.username,
            "nickname" : follower.nickname,
            "profile_img" : follower.profile_img,
        }
        for follower in followers
    ]

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
        200
    )


@bp.get("/<int:user_id>/following")
def get_following(user_id):
    """Retrieve a paginated list of users that the specified user follows.

    Args:
        user_id: The ID of the user whose following list to retrieve.

    Query params:
        page: Page number (default: 1).
        per_page: Items per page (default: 20).

    Returns:
        JSON response with 200 status containing paginated following user data.
        Returns 404 if the user does not exist.
    """
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



# 친구 등록/삭제 토글 라우터 (친한친구 개념)
@bp.patch("/<int:user_id>/friend")
@jwt_required()
def toggle_friend(user_id):
    """Toggle a close-friend relationship between the current user and a target user.

    Requires JWT authentication. Adds the target as a friend if not already added;
    removes them otherwise.

    Args:
        user_id: The ID of the user to add or remove as a close friend.

    Returns:
        JSON response with 201 status when a friend is added, or 200 when removed,
        both including the is_friended flag. Returns 400 if the user attempts to
        friend themselves.

    Raises:
        400: If the current user tries to friend themselves.
        500: On database integrity error.
    """
    current_user_id = int(get_jwt_identity())

    if current_user_id == user_id:
        return jsonify({"message": "자기 자신을 친구로 추가할 수 없습니다", "is_friended": False}), 400

    # 대상 사용자 존재 확인
    User.query.get_or_404(user_id)

    # 이미 친구인지 확인
    existing = Friend.query.filter_by(
        user_id=current_user_id, friend_user_id=user_id
    ).first()

    try:
        if existing:
            # 친구 삭제
            db.session.delete(existing)
            db.session.commit()
            return jsonify({
                "message": "친구 삭제 성공",
                "is_friended": False
            }), 200
        else:
            # 친구 등록
            friend = Friend(user_id=current_user_id, friend_user_id=user_id)
            db.session.add(friend)
            db.session.commit()
            return jsonify({
                "message": "친구 추가 성공",
                "is_friended": True
            }), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "친구 처리 중 오류가 발생했습니다", "is_friended": False}), 500


@bp.get("/me/friends")
@jwt_required()
def get_my_friends():
    """Retrieve the current user's close-friends list.

    Requires JWT authentication.

    Returns:
        JSON response with 200 status containing friend user details and total count.
    """
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


# =============================================================================
# 포인트 관리 엔드포인트
# =============================================================================


@bp.get("/me/points")
@jwt_required()
def get_my_points():
    """Retrieve the current user's total points and today's reward summary.

    Requires JWT authentication.

    Returns:
        JSON response with 200 status containing user ID, total points, and a
        daily reward breakdown.
    """
    current_user_id = int(get_jwt_identity())
    user = User.query.get_or_404(current_user_id)

    # 오늘 리워드 요약 포함
    reward_summary = get_user_reward_summary(current_user_id)

    return (
        jsonify(
            {
                "user_id": user.user_id,
                "points": user.points,
                "today": reward_summary,
            }
        ),
        200,
    )


@bp.get("/<int:user_id>/points")
def get_user_points(user_id):
    """Retrieve a specific user's total points.

    Args:
        user_id: The ID of the user.

    Returns:
        JSON response with 200 status containing user ID and point total.
        Returns 404 if the user does not exist.
    """
    user = User.query.get_or_404(user_id)

    return (
        jsonify(
            {
                "user_id": user.user_id,
                "points": user.points,
            }
        ),
        200,
    )


# =============================================================================
# 메달 조회 엔드포인트
# =============================================================================


@bp.get("/me/medal")
@jwt_required()
def get_my_medal():
    """Retrieve the current user's medal tier and point information.

    Requires JWT authentication.

    Returns:
        JSON response with 200 status containing user ID, total points, and
        medal tier data.
    """
    current_user_id = int(get_jwt_identity())
    user = User.query.get_or_404(current_user_id)

    medal_info = get_user_medal(current_user_id)

    return (
        jsonify(
            {
                "user_id": user.user_id,
                "points": user.points,
                "medal": medal_info,
            }
        ),
        200,
    )


@bp.get("/<int:user_id>/medal")
def get_user_medal_info(user_id):
    """Retrieve a specific user's medal tier and point information.

    Args:
        user_id: The ID of the user.

    Returns:
        JSON response with 200 status containing user ID, total points, and
        medal tier data. Returns 404 if the user does not exist.
    """
    user = User.query.get_or_404(user_id)

    medal_info = get_user_medal(user_id)

    return (
        jsonify(
            {
                "user_id": user.user_id,
                "points": user.points,
                "medal": medal_info,
            }
        ),
        200,
    )


@bp.get("/medals")
def get_all_medals():
    """Retrieve all available medal tier definitions.

    Returns:
        JSON response with 200 status containing the full list of medal tiers
        and the total count.
    """
    return (
        jsonify(
            {
                "medals": MEDAL_TIERS,
                "count": len(MEDAL_TIERS),
            }
        ),
        200,
    )


# =============================================================================
# 리그 조회 엔드포인트 (미래 구현용)
# =============================================================================


@bp.get("/me/league")
@jwt_required()
def get_my_league():
    """Retrieve the current user's league information.

    Requires JWT authentication.

    Returns:
        JSON response with 200 status containing league data for the current user.
    """
    current_user_id = int(get_jwt_identity())

    league_info = get_user_league_info(current_user_id)

    return jsonify(league_info), 200


@bp.get("/<int:user_id>/league")
def get_user_league(user_id):
    """Retrieve a specific user's league information.

    Args:
        user_id: The ID of the user.

    Returns:
        JSON response with 200 status containing league data.
        Returns 404 if the user does not exist.
    """
    User.query.get_or_404(user_id)

    league_info = get_user_league_info(user_id)

    return jsonify(league_info), 200


# =============================================================================
# 관리자 전용 엔드포인트 (개발용)
# =============================================================================


@bp.patch("/admin/<int:user_id>/points")
@jwt_required()
def admin_set_user_points(user_id):
    """[Admin only] Set, add, or subtract points for a specific user.

    Requires JWT authentication with admin account type.

    Args:
        user_id: The ID of the target user.

    Query params:
        points: The point value to apply (required).
        mode: Operation mode — 'set' (default), 'add', or 'subtract'.

    Returns:
        JSON response with 200 status containing old and new point values on success.
        Returns 403 if the current user is not an admin.

    Raises:
        403: If the current user does not have admin privileges.
        400: If the points parameter is missing.
    """
    try:
        current_user = get_current_user()

        # 관리자 권한 확인
        if not current_user or current_user.account_type != AccountType.ADMIN:
            return jsonify({"message": "관리자 권한이 필요합니다"}), 403

        # 대상 사용자 조회
        target_user = User.query.get_or_404(user_id)

        # 쿼리 파라미터
        points = request.args.get("points", type=int)
        mode = request.args.get("mode", "set")

        if points is None:
            return jsonify({"message": "points 파라미터가 필요합니다"}), 400

        old_points = target_user.points

        if mode == "add":
            target_user.points += points
        elif mode == "subtract":
            target_user.points = max(0, target_user.points - points)  # 음수 방지
        else:  # set (기본)
            target_user.points = max(0, points)  # 음수 방지

        db.session.commit()

        return (
            jsonify(
                {
                    "message": "포인트가 수정되었습니다",
                    "user_id": target_user.user_id,
                    "username": target_user.username,
                    "old_points": old_points,
                    "new_points": target_user.points,
                    "mode": mode,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"포인트 수정 실패: {str(e)}"}), 500


@bp.get("/admin/points/leaderboard")
@jwt_required()
def admin_points_leaderboard():
    """[Admin only] Retrieve the top users ranked by points.

    Requires JWT authentication with admin account type.

    Query params:
        limit: Number of users to return (default: 20, max: 100).

    Returns:
        JSON response with 200 status containing a ranked leaderboard with user
        details and point totals. Returns 403 if the current user is not an admin.

    Raises:
        403: If the current user does not have admin privileges.
    """
    try:
        current_user = get_current_user()

        # 관리자 권한 확인
        if not current_user or current_user.account_type != AccountType.ADMIN:
            return jsonify({"message": "관리자 권한이 필요합니다"}), 403

        limit = min(request.args.get("limit", 20, type=int), 100)

        users = (
            User.query.filter(User.points > 0)
            .order_by(User.points.desc())
            .limit(limit)
            .all()
        )

        result = []
        for rank, user in enumerate(users, 1):
            result.append(
                {
                    "rank": rank,
                    "user_id": user.user_id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "points": user.points,
                }
            )

        return (
            jsonify(
                {
                    "leaderboard": result,
                    "count": len(result),
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"message": f"순위표 조회 실패: {str(e)}"}), 500
