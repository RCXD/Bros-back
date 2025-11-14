"""
Admin module - Administrative functions
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_current_user
from sqlalchemy import func
from datetime import datetime, timedelta

from apps.config.server import db
from apps.auth.models import User, AccountType
from apps.admin.models import Post, Reply, Follow, Report

bp = Blueprint("admin", __name__)


def admin_required():
    """Decorator to check if user is admin"""
    current_user = get_current_user()
    if not current_user or current_user.account_type != AccountType.ADMIN:
        return jsonify({"error": "관리자 권한이 필요합니다"}), 403
    return None


# =====================================================
# User Management
# =====================================================

@bp.get("/users")
@jwt_required()
def get_users():
    """
    Get all users with filtering and pagination
    Query params:
        - username: Filter by username
        - email: Filter by email
        - nickname: Filter by nickname
        - account_type: Filter by USER or ADMIN
        - page: Page number (default 1)
        - per_page: Items per page (default 20)
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
    
    return jsonify({
        "users": [
            {
                "user_id": u.user_id,
                "username": u.username,
                "nickname": u.nickname,
                "email": u.email,
                "address": u.address,
                "profile_img": u.profile_img,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "account_type": u.account_type.name,
                "oauth_type": u.oauth_type.name,
                "follower_count": u.follower_count,
                "is_expired": u.is_expired,
            }
            for u in pagination.items
        ],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
        "per_page": per_page,
    }), 200


@bp.get("/users/<int:user_id>")
@jwt_required()
def get_user_detail(user_id):
    """Get detailed user information including statistics"""
    error = admin_required()
    if error:
        return error
    
    user = User.query.get_or_404(user_id)
    
    # Get user statistics
    post_count = Post.query.filter_by(user_id=user_id).count()
    reply_count = Reply.query.filter_by(user_id=user_id).count()
    following_count = Follow.query.filter_by(follower_id=user_id).count()
    follower_count = Follow.query.filter_by(following_id=user_id).count()
    
    return jsonify({
        **user.to_dict(),
        "statistics": {
            "posts": post_count,
            "replies": reply_count,
            "following": following_count,
            "followers": follower_count,
        }
    }), 200


@bp.post("/users/<int:user_id>/ban")
@jwt_required()
def ban_user(user_id):
    """
    Ban/suspend a user account
    JSON body:
        - reason: Optional reason for ban
    """
    error = admin_required()
    if error:
        return error
    
    user = User.query.get_or_404(user_id)
    
    if user.account_type == AccountType.ADMIN:
        return jsonify({"error": "관리자 계정은 정지할 수 없습니다"}), 400
    
    user.is_expired = True
    db.session.commit()
    
    data = request.get_json() or {}
    reason = data.get("reason", "관리자에 의한 정지")
    
    return jsonify({
        "message": f"사용자 {user.username} 계정이 정지되었습니다",
        "reason": reason
    }), 200


@bp.post("/users/<int:user_id>/unban")
@jwt_required()
def unban_user(user_id):
    """Restore a banned user account"""
    error = admin_required()
    if error:
        return error
    
    user = User.query.get_or_404(user_id)
    user.is_expired = False
    db.session.commit()
    
    return jsonify({
        "message": f"사용자 {user.username} 계정 정지가 해제되었습니다"
    }), 200


@bp.delete("/users/<int:user_id>")
@jwt_required()
def delete_user(user_id):
    """Permanently delete a user account"""
    error = admin_required()
    if error:
        return error
    
    user = User.query.get_or_404(user_id)
    
    if user.account_type == AccountType.ADMIN:
        return jsonify({"error": "관리자 계정은 삭제할 수 없습니다"}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": f"사용자 {user.username} 삭제 완료"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "사용자 삭제 실패", "details": str(e)}), 400


# =====================================================
# Platform Statistics
# =====================================================

@bp.get("/statistics")
@jwt_required()
def get_statistics():
    """Get comprehensive platform statistics"""
    error = admin_required()
    if error:
        return error
    
    # User statistics
    total_users = User.query.filter_by(account_type=AccountType.USER).count()
    banned_users = User.query.filter_by(account_type=AccountType.USER, is_expired=True).count()
    admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    new_users = User.query.filter(
        User.created_at >= thirty_days_ago,
        User.account_type == AccountType.USER
    ).count()
    active_users = User.query.filter(
        User.last_login >= thirty_days_ago,
        User.account_type == AccountType.USER
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
    
    return jsonify({
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
    }), 200


@bp.get("/statistics/activity")
@jwt_required()
def get_activity_statistics():
    """Get daily activity statistics for the last 30 days"""
    error = admin_required()
    if error:
        return error
    
    days = request.args.get("days", 30, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    # Daily user registrations
    daily_users = db.session.query(
        func.date(User.created_at).label("date"),
        func.count(User.user_id).label("count")
    ).filter(
        User.created_at >= start_date,
        User.account_type == AccountType.USER
    ).group_by(func.date(User.created_at)).all()
    
    # Daily posts
    daily_posts = db.session.query(
        func.date(Post.created_at).label("date"),
        func.count(Post.post_id).label("count")
    ).filter(Post.created_at >= start_date).group_by(func.date(Post.created_at)).all()
    
    return jsonify({
        "user_registrations": [
            {"date": str(date), "count": count} for date, count in daily_users
        ],
        "posts": [
            {"date": str(date), "count": count} for date, count in daily_posts
        ],
    }), 200


# =====================================================
# Reports Management
# =====================================================

@bp.get("/reports")
@jwt_required()
def get_reports():
    """
    Get all reports with filtering
    Query params:
        - status: pending/resolved
        - page: Page number
        - per_page: Items per page
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
    
    return jsonify({
        "reports": [
            {
                "report_id": r.report_id,
                "reporter_id": r.reporter_id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
                "is_resolved": r.is_resolved,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in pagination.items
        ],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
    }), 200


@bp.post("/reports/<int:report_id>/resolve")
@jwt_required()
def resolve_report(report_id):
    """Mark a report as resolved"""
    error = admin_required()
    if error:
        return error
    
    report = Report.query.get_or_404(report_id)
    report.is_resolved = True
    report.resolved_at = datetime.now()
    db.session.commit()
    
    return jsonify({"message": "신고가 처리되었습니다"}), 200
