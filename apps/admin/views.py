"""
Admin module - Administrative functions
"""

import os

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_current_user
from sqlalchemy import func
from datetime import datetime, timedelta

from apps.config.server import db
from apps.auth.models import User, AccountType
from apps.admin.models import Post, Reply, Follow, Report
from apps.image.models import Image
from apps.notification.models import Notification, NotificationType

bp = Blueprint("admin", __name__)


@bp.get("/api_info")
def api_info():
    """Provide admin API endpoint information (development use).

    Returns:
        JSON response describing all available admin API endpoints with their
        paths, methods, auth requirements, and descriptions.
    """
    info = {
        "module": "admin",
        "base_path": "/admin",
        "description": "관리자 기능 (사용자, 게시물, 신고 관리 등)",
        "endpoints": [
            {
                "path": "/admin/users",
                "method": "GET",
                "auth_required": True,
                "description": "사용자 목록 조회 (관리자 전용)",
            },
            {
                "path": "/admin/user/<user_id>",
                "method": "DELETE",
                "auth_required": True,
                "description": "사용자 삭제 (관리자 전용)",
            },
            {
                "path": "/admin/posts",
                "method": "GET",
                "auth_required": True,
                "description": "게시물 목록 조회 (관리자 전용)",
            },
            {
                "path": "/admin/post/<post_id>",
                "method": "DELETE",
                "auth_required": True,
                "description": "게시물 삭제 (관리자 전용)",
            },
            {
                "path": "/admin/reports",
                "method": "GET",
                "auth_required": True,
                "description": "신고 목록 조회 (관리자 전용)",
            },
            {
                "path": "/admin/stats",
                "method": "GET",
                "auth_required": True,
                "description": "통계 정보 조회 (관리자 전용)",
            },
            {
                "path": "/admin/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
        "note": "모든 관리자 엔드포인트는 ADMIN 계정 타입 필요",
    }
    return jsonify(info), 200


def admin_required():
    """Check if the currently authenticated user has admin privileges.

    Returns:
        None if the user is an admin, or a JSON error response tuple with
        HTTP 403 if the user is not an admin or is not authenticated.
    """
    current_user = get_current_user()
    if not current_user or current_user.account_type != AccountType.ADMIN:
        return jsonify({"message": "관리자 권한이 필요합니다"}), 403
    return None


# =====================================================
# User Management
# =====================================================


@bp.get("/users")
@jwt_required()
def get_users():
    """Get all users with filtering and pagination.

    Query params:
        username: Filter by username (partial match).
        email: Filter by email (partial match).
        nickname: Filter by nickname (partial match).
        account_type: Filter by account type (USER or ADMIN).
        page: Page number (default 1).
        per_page: Items per page (default 20).

    Returns:
        JSON response containing the paginated user list and pagination metadata.
    """
    error = admin_required()
    if error:
        return error

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # Build query with filters
    query = User.query

    if username := request.args.get("username"):
        query = query.filter(User.username.ilike(f"%{username}%"))
    if email := request.args.get("email"):
        query = query.filter(User.email.ilike(f"%{email}%"))
    if nickname := request.args.get("nickname"):
        query = query.filter(User.nickname.ilike(f"%{nickname}%"))
    if account_type := request.args.get("account_type"):
        query = query.filter(User.account_type == AccountType[account_type.upper()])

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "users": [
                    {
                        "user_id": u.user_id,
                        "username": u.username,
                        "nickname": u.nickname,
                        "email": u.email,
                        "address": u.address,
                        "profile_img": u.profile_img,
                        "created_at": u.created_at.isoformat(),
                        "last_login": (
                            u.last_login.isoformat() if u.last_login else None
                        ),
                        "account_type": u.account_type.name,
                        "oauth_type": u.oauth_type.name,
                        "follower_count": u.follower_count,
                        "is_expired": u.is_expired,
                    }
                    for u in pagination.items
                ],
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
            }
        ),
        200,
    )


@bp.get("/users/<int:user_id>")
@jwt_required()
def get_user_detail(user_id):
    """Get detailed information and statistics for a specific user.

    Args:
        user_id: The integer ID of the user to retrieve.

    Returns:
        JSON response containing the user's profile data and activity statistics
        (post count, reply count, following, and follower counts).
    """
    error = admin_required()
    if error:
        return error

    user = User.query.get_or_404(user_id)

    # Get user statistics
    post_count = Post.query.filter_by(user_id=user_id).count()
    reply_count = Reply.query.filter_by(user_id=user_id).count()
    following_count = Follow.query.filter_by(from_user_id=user_id).count()
    follower_count = Follow.query.filter_by(to_user_id=user_id).count()

    return (
        jsonify(
            {
                **user.to_dict(),
                "statistics": {
                    "posts": post_count,
                    "replies": reply_count,
                    "following": following_count,
                    "followers": follower_count,
                },
            }
        ),
        200,
    )


@bp.post("/users/<int:user_id>/ban")
@jwt_required()
def ban_user(user_id):
    """Ban or suspend a user account.

    Args:
        user_id: The integer ID of the user to ban.

    Returns:
        JSON response confirming the ban with an optional reason, or an error
        response if the target is an admin account.
    """
    error = admin_required()
    if error:
        return error

    user = User.query.get_or_404(user_id)

    if user.account_type == AccountType.ADMIN:
        return jsonify({"message": "관리자 계정은 정지할 수 없습니다"}), 400

    user.is_expired = True
    db.session.commit()

    data = request.get_json() or {}
    reason = data.get("reason", "관리자에 의한 정지")

    return (
        jsonify(
            {
                "message": f"사용자 {user.username} 계정이 정지되었습니다",
                "reason": reason,
            }
        ),
        200,
    )


@bp.post("/users/<int:user_id>/unban")
@jwt_required()
def unban_user(user_id):
    """Restore a banned user account.

    Args:
        user_id: The integer ID of the user to unban.

    Returns:
        JSON response confirming the account has been reinstated.
    """
    error = admin_required()
    if error:
        return error

    user = User.query.get_or_404(user_id)
    user.is_expired = False
    db.session.commit()

    return (
        jsonify({"message": f"사용자 {user.username} 계정 정지가 해제되었습니다"}),
        200,
    )


@bp.delete("/users/<int:user_id>")
@jwt_required()
def delete_user(user_id):
    """Permanently delete a user account.

    Args:
        user_id: The integer ID of the user to delete.

    Returns:
        JSON response confirming deletion, or an error response if the user is
        an admin or the deletion fails.
    """
    error = admin_required()
    if error:
        return error

    user = User.query.get_or_404(user_id)

    if user.account_type == AccountType.ADMIN:
        return jsonify({"message": "관리자 계정은 삭제할 수 없습니다"}), 400

    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": f"사용자 {user.username} 삭제 완료"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "사용자 삭제 실패", "details": str(e)}), 400


# =====================================================
# Platform Statistics
# =====================================================


@bp.get("/statistics")
@jwt_required()
def get_statistics():
    """Get comprehensive platform statistics.

    Returns:
        JSON response containing user counts (total, banned, admins, new and
        active this month), content counts (posts and replies), and report
        counts (total, pending, resolved).
    """
    error = admin_required()
    if error:
        return error

    # User statistics
    total_users = User.query.filter_by(account_type=AccountType.USER).count()
    banned_users = User.query.filter_by(
        account_type=AccountType.USER, is_expired=True
    ).count()
    admins = User.query.filter_by(account_type=AccountType.ADMIN).count()

    # Recent activity (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    new_users = User.query.filter(
        User.created_at >= thirty_days_ago, User.account_type == AccountType.USER
    ).count()
    active_users = User.query.filter(
        User.last_login >= thirty_days_ago, User.account_type == AccountType.USER
    ).count()

    # Content statistics
    total_posts = Post.query.count()
    total_replies = Reply.query.count()
    total_reports = Report.query.count()
    pending_reports = Report.query.filter_by(is_resolved=False).count()

    # Growth data (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    new_posts_week = Post.query.filter(Post.created_at >= seven_days_ago).count()
    new_replies_week = Reply.query.filter(Reply.created_at >= seven_days_ago).count()

    return (
        jsonify(
            {
                "users": {
                    "total": total_users,
                    "banned": banned_users,
                    "admins": admins,
                    "new_this_month": new_users,
                    "active_this_month": active_users,
                },
                "content": {
                    "total_posts": total_posts,
                    "total_replies": total_replies,
                    "posts_this_week": new_posts_week,
                    "replies_this_week": new_replies_week,
                },
                "reports": {
                    "total": total_reports,
                    "pending": pending_reports,
                    "resolved": total_reports - pending_reports,
                },
            }
        ),
        200,
    )


@bp.get("/statistics/activity")
@jwt_required()
def get_activity_statistics():
    """Get daily activity statistics for a configurable number of past days.

    Query params:
        days: Number of days to look back (default 30).

    Returns:
        JSON response with daily user registration counts and daily post counts
        for the specified time period.
    """
    error = admin_required()
    if error:
        return error

    days = request.args.get("days", 30, type=int)
    start_date = datetime.now() - timedelta(days=days)

    # Daily user registrations
    daily_users = (
        db.session.query(
            func.date(User.created_at).label("date"),
            func.count(User.user_id).label("count"),
        )
        .filter(User.created_at >= start_date, User.account_type == AccountType.USER)
        .group_by(func.date(User.created_at))
        .all()
    )

    # Daily posts
    daily_posts = (
        db.session.query(
            func.date(Post.created_at).label("date"),
            func.count(Post.post_id).label("count"),
        )
        .filter(Post.created_at >= start_date)
        .group_by(func.date(Post.created_at))
        .all()
    )

    return (
        jsonify(
            {
                "user_registrations": [
                    {"date": str(date), "count": count} for date, count in daily_users
                ],
                "posts": [
                    {"date": str(date), "count": count} for date, count in daily_posts
                ],
            }
        ),
        200,
    )


# =====================================================
# Reports Management
# =====================================================


@bp.get("/reports")
@jwt_required()
def get_reports():
    """Get all reports with optional status filtering and pagination.

    Query params:
        status: Filter by resolution status (``pending`` or ``resolved``).
        page: Page number (default 1).
        per_page: Items per page (default 20).

    Returns:
        JSON response containing the paginated report list and pagination metadata.
    """
    error = admin_required()
    if error:
        return error

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Report.query

    if status := request.args.get("status"):
        is_resolved = status.lower() == "resolved"
        query = query.filter_by(is_resolved=is_resolved)

    pagination = query.order_by(Report.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return (
        jsonify(
            {
                "reports": [
                    {
                        "report_id": r.report_id,
                        "reporter_id": r.reporter_id,
                        "target_type": r.target_type,
                        "target_id": r.target_id,
                        "reason": r.reason,
                        "created_at": r.created_at.isoformat(),
                        "is_resolved": r.is_resolved,
                        "resolved_at": (
                            r.resolved_at.isoformat() if r.resolved_at else None
                        ),
                    }
                    for r in pagination.items
                ],
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.post("/reports/<int:report_id>/resolve")
@jwt_required()
def resolve_report(report_id):
    """Mark a report as resolved.

    Args:
        report_id: The integer ID of the report to resolve.

    Returns:
        JSON response confirming the report has been processed.
    """
    error = admin_required()
    if error:
        return error

    report = Report.query.get_or_404(report_id)
    report.is_resolved = True
    report.resolved_at = datetime.now()
    db.session.commit()

    return jsonify({"message": "신고가 처리되었습니다"}), 200


# TODO =====================================================
# 관리자전용 기능으로 통계 및 관리 용도로 사용되도록 할 예정
@bp.get("/image/user/<string:user_identifier>")
@jwt_required()
def get_user_profile_image(user_identifier):
    """Retrieve a user's profile image by user ID or username.

    Admin-only endpoint. Accepts either a numeric user ID or a username string.
    Falls back to the default profile image when no uploaded image is found.

    Args:
        user_identifier: A numeric user ID string or a plain username string.
            For example: ``"123"`` resolves by user_id; ``"john_doe"`` resolves
            by username.

    Returns:
        The profile image file, or the default profile image if none is found.
        Returns a 404 JSON response when the username does not exist.
    """
    # 관리자인지 확인
    error = admin_required()
    if error:
        return error

    # user_identifier가 숫자인지 확인
    if user_identifier.isdigit():
        # user_id로 조회
        user_id = int(user_identifier)
        image = Image.query.filter_by(user_id=user_id, post_id=None).first()
        if not image:
            # 이미지가 없으면 기본 프로필 이미지 반환
            folder = os.path.join(current_app.root_path, "static")
            return send_from_directory(folder, "default_profile.jpg")
    else:
        # username으로 조회
        user = User.query.filter_by(username=user_identifier).first()
        if not user:
            return jsonify({"message": "사용자를 찾을 수 없습니다"}), 404

        image = Image.query.filter_by(user_id=user.user_id, post_id=None).first()
        if not image:
            # 이미지가 없으면 기본 프로필 이미지 반환
            folder = os.path.join(current_app.root_path, "static")
            return send_from_directory(folder, "default_profile.jpg")

    # DB: static/profile_images/2025-11-12/uuid.jpg
    relative_path = image.directory

    # 절대 경로 생성
    absolute_path = os.path.join(current_app.root_path, relative_path)

    folder = os.path.dirname(absolute_path)
    filename = os.path.basename(absolute_path)

    # 파일 존재 여부 체크 (파일이 없으면 기본 이미지 반환)
    if not os.path.exists(absolute_path):
        folder = os.path.join(current_app.root_path, "static")
        return send_from_directory(folder, "default_profile.jpg")

    return send_from_directory(folder, filename)


# === LEGACY: app/blueprints/notification.py에만 있던 엔드포인트 ===
@bp.route("/all", methods=["GET"])
@jwt_required()
def get_all_notifications():
    """Retrieve all notifications across all users (admin view).

    Legacy endpoint migrated from app/blueprints/notification.py.
    Note: only checks authentication, not admin role (security TODO).

    Returns:
        JSON response with ``success`` flag and a list of serialized
        Notification objects ordered by creation time descending.
    """
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    result = [n.serialize() for n in notifications]  # serialize() 사용 (레거시 호환)
    return jsonify(success=True, data=result), 200


# === END LEGACY ===
