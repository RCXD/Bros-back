"""
Notification-related API endpoints.

Migrated from: app/blueprints/notification.py
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from apps.config.server import db
from apps.notification.models import Notification, NotificationType
from apps.auth.models import User
from apps.post.models import Post
from apps.reply.models import Reply
from apps.user.models import Follow, Friend

# === LEGACY: app/blueprints/notification.py와 동일한 모델 import 구조 유지 ===
# from apps.mention.models import Mention  # 필요시 추가
# === END LEGACY ===

bp = Blueprint("notification", __name__, url_prefix="/notification")


@bp.get("/api_info")
def api_info():
    """Return notification API metadata for development use.

    Returns:
        JSON object describing available endpoints with 200 status.
    """
    info = {
        "module": "notification",
        "base_path": "/notification",
        "description": "사용자 알림 조회 및 관리",
        "endpoints": [
            {
                "path": "/notification",
                "method": "POST",
                "auth_required": True,
                "description": "알림 생성 (수동 호출용)",
                "json_body": {
                    "to_user_id": "받는 사용자 ID (필수)",
                    "type": "알림 타입 (필수, MENTION/LIKE/COMMENT/FOLLOW 등)",
                    "post_id": "게시물 ID (선택)",
                    "reply_id": "댓글 ID (선택)",
                    "mention_id": "멘션 ID (선택)",
                    "product_id": "상품 ID (선택)",
                },
            },
            {
                "path": "/notification",
                "method": "GET",
                "auth_required": True,
                "description": "알림 목록 조회",
                "query_params": {
                    "page": "페이지 번호 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                    "is_checked": "읽음 필터 (true/false)",
                },
            },
            {
                "path": "/notification/<notification_id>",
                "method": "PATCH",
                "auth_required": True,
                "description": "알림 읽음 처리",
            },
            {
                "path": "/notification/mark-all-read",
                "method": "PATCH",
                "auth_required": True,
                "description": "모든 알림 읽음 처리",
            },
            {
                "path": "/notification/<notification_id>",
                "method": "DELETE",
                "auth_required": True,
                "description": "알림 삭제",
            },
            {
                "path": "/notification/unread-count",
                "method": "GET",
                "auth_required": True,
                "description": "읽지 않은 알림 개수 조회",
            },
            {
                "path": "/notification/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


@bp.post("")
@jwt_required()
def create_notification():
    """Create a notification manually (intended for development/testing use).

    Reads JSON from the request body to build a Notification record and
    persists it to the database.

    Returns:
        JSON representation of the created notification with 201 status on
        success, or an error message with 400/404/500 status on failure.

    Raises:
        IntegrityError: Rolled back and returned as a 400 response when a
            database constraint is violated.
    """
    data = request.get_json() or {}
    from_user_id = int(get_jwt_identity())

    to_user_id = data.get("to_user_id")
    notif_type = data.get(
        "type"
    )  # === LEGACY: "MENTION", "LIKE", "COMMENT" 등 문자열 ===
    post_id = data.get("post_id")
    reply_id = data.get("reply_id")
    mention_id = data.get("mention_id")
    product_id = data.get("product_id")  # === 기존 apps 버전에서 추가된 필드 ===

    # 필수값 체크
    if not to_user_id or not notif_type:
        return jsonify({"message": "to_user_id와 type은 필수입니다."}), 400

    # 자기 자신에게 알림 생성 금지
    if from_user_id == to_user_id:
        return (
            jsonify({"message": "자기 자신에게 알림을 생성할 수 없습니다."}),
            400,
        )

    # 수신자 존재 확인
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({"message": "수신자 유저가 존재하지 않습니다."}), 404

    # === LEGACY: NotificationType enum 검증 (레거시에서는 문자열로 받음) ===
    try:
        notification_type = NotificationType[notif_type.upper()]
    except KeyError:
        return (
            jsonify({"message": f"유효하지 않은 알림 타입: {notif_type}"}),
            400,
        )
    # === END LEGACY ===

    notification = Notification(
        type=notification_type,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        post_id=post_id,
        reply_id=reply_id,
        mention_id=mention_id,
        product_id=product_id,
        message=f"{from_user_id.username}가 당신에게 알림을 보냈습니다. [개발용]",
    )

    db.session.add(notification)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"message": f"DB 제약조건 오류: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"알림 생성 실패: {str(e)}"}), 500

    # === LEGACY: serialize() 호환 (to_dict()로 통일됨) ===
    return jsonify(notification.to_dict()), 201


@bp.get("")
@jwt_required()
def get_my_notifications():
    """Retrieve the current user's notifications with optional filtering.

    Supports pagination and an ``unread_only`` flag to limit results to
    unread notifications. When ``follow_state=true`` is passed, each item
    is annotated with the mutual-follow relationship between the recipient
    and the notification sender.

    Returns:
        JSON object containing a paginated list of notification dicts along
        with pagination metadata, with 200 status.
    """
    current_user_id = int(get_jwt_identity())

    # 페이지네이션 파라미터
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # 읽지 않은 알림만 조회 옵션
    unread_only = request.args.get("unread_only", "false").lower() == "true"

    # 팔로우 상태 정보 조회 옵션
    follow_state = request.args.get("follow_state", "false").lower() == "true"

    query = Notification.query.filter_by(to_user_id=current_user_id)

    if unread_only:
        query = query.filter_by(is_checked=False)

    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    if follow_state:
        list_follow_state = []
        for notification_ in notifications.items:
            from_user = User.query.filter_by(user_id=notification_.from_user_id).first()
            # if not from_user:
            #     follow_state_list.append({"following": False, "followed": False})
            #     continue
            follow_state_ = {
                "following": Follow.query.filter_by(
                    from_user_id=current_user_id,
                    to_user_id=from_user.user_id,
                ).count()
                > 0,  # 팔로잉 (내가 그 사람을 팔로우)
                "followed": Follow.query.filter_by(
                    from_user_id=from_user.user_id,
                    to_user_id=current_user_id,
                ).count()
                > 0,  # 팔로우 당함 (나를 팔로우 하는 사람)
            }
            # followed==True인 상태에서 following==False이면 버튼 상태: 맞팔로우 / following==True이면 맞팔로잉(회색)
            # followed==False인 상태에서 following==False이면 버튼 상태: 팔로우 / following==True이면 팔로잉(회색)
            if follow_state_["following"] and follow_state_["followed"]:
                follow_state_["button_state"] = (
                    "맞팔로잉"  # 맞팔로우 : 서로 팔로우하는 상태에서 내가 팔로우 삭제요청
                )
            elif follow_state_["following"] and not follow_state_["followed"]:
                follow_state_["button_state"] = (
                    "팔로잉"  # 팔로잉(회색) : 상대가 팔로우하지 않는 상태에서 내가 팔로우 삭제요청
                )
            elif not follow_state_["following"] and follow_state_["followed"]:
                follow_state_["button_state"] = (
                    "맞팔로우"  # 맞팔로우 : 상대가 팔로우하는 상태에서 내가 팔로우 요청
                )
            else:
                follow_state_["button_state"] = (
                    "팔로우"  # 팔로우: 서로 팔로우하지 않는 상태에서 내가 팔로우 요청
                )

            list_follow_state.append(follow_state_)

    result = {
        "items": [
            dict(list(n.to_dict().items()) + [("follow_state", list_follow_state[i])])
            for i, n in enumerate(notifications.items)
        ],  # follow_state 포함됨
        "total": notifications.total,
        "page": page,
        "per_page": per_page,
        "pages": notifications.pages,
        "has_next": notifications.has_next,
        "has_prev": notifications.has_prev,
    }

    return jsonify(result), 200


@bp.get("/unread-count")
@jwt_required()
def get_unread_count():
    """Return the number of unread notifications for the current user.

    Returns:
        JSON object ``{"unread_count": <int>}`` with 200 status.
    """
    current_user_id = int(get_jwt_identity())

    count = Notification.query.filter_by(
        to_user_id=current_user_id, is_checked=False
    ).count()

    return jsonify({"unread_count": count}), 200


@bp.patch("/<int:notification_id>")
@jwt_required()
def mark_notification_as_read(notification_id):
    """Mark a single notification as read.

    Args:
        notification_id: Primary key of the notification to update.

    Returns:
        JSON representation of the updated notification with 200 status, or
        a 404 error if the notification is not found or does not belong to the
        current user.
    """
    current_user_id = int(get_jwt_identity())

    notification = Notification.query.filter_by(
        notification_id=notification_id, to_user_id=current_user_id
    ).first()

    if not notification:
        return jsonify({"message": "알림을 찾을 수 없습니다."}), 404

    notification.is_checked = True
    db.session.commit()

    return jsonify(notification.to_dict()), 200


@bp.patch("/mark-all-read")
@jwt_required()
def mark_all_as_read():
    """Mark all unread notifications as read for the current user.

    Returns:
        JSON object with a confirmation message and ``updated_count`` field
        indicating how many notifications were updated, with 200 status.
    """
    current_user_id = int(get_jwt_identity())

    updated_count = Notification.query.filter_by(
        to_user_id=current_user_id, is_checked=False
    ).update({"is_checked": True})

    db.session.commit()

    return (
        jsonify(
            {
                "message": f"{updated_count}개의 알림을 읽음 처리했습니다.",
                "updated_count": updated_count,
            },
        ),
        200,
    )


@bp.delete("/<int:notification_id>")
@jwt_required()
def delete_notification(notification_id):
    """Delete a notification owned by the current user.

    Args:
        notification_id: Primary key of the notification to delete.

    Returns:
        JSON confirmation message with 200 status on success, or 404 if the
        notification is not found or does not belong to the current user.
    """
    current_user_id = int(get_jwt_identity())

    notification = Notification.query.filter_by(
        notification_id=notification_id, to_user_id=current_user_id
    ).first()

    if not notification:
        return jsonify({"message": "알림을 찾을 수 없습니다."}), 404

    db.session.delete(notification)
    db.session.commit()

    return jsonify({"message": "알림이 삭제되었습니다."}), 200
