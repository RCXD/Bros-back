"""
알림 관련 API 엔드포인트
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
    """
    알림 API 정보 제공 (개발용)
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
    """
    알림 생성 (수동 호출용)

    === LEGACY: app/blueprints/notification.py의 create_notification() 로직 통합 ===
    - 기존: type을 문자열로 받아서 .upper() 처리
    - 추가: product_id 필드 지원 (apps 버전에서 추가됨)
    === END LEGACY ===
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

# TODO: 현재 쿼리를 이중으로 반환함 && 
@bp.get("")
@jwt_required()
def get_my_notifications():
    """
    내 알림 조회

    === LEGACY vs 기존 비교 ===
    - LEGACY (app/blueprints): 페이지네이션 없이 전체 조회
    - 기존 (apps): 페이지네이션 + unread_only 필터 지원
    - 선택: 기존 apps 버전 유지 (더 많은 기능)
    === END ===
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

    result = {
        "items": [],
        "total": notifications.total,
        "page": page,
        "per_page": per_page,
        "pages": notifications.pages,
        "has_next": notifications.has_next,
        "has_prev": notifications.has_prev,
    }

    follow_state_map = {}
    follow_state_map_for_items = None
    if follow_state:
        from_user_ids = {
            n.from_user_id
            for n in notifications.items
            if n.from_user_id is not None
        }

        if from_user_ids:
            following = {
                row.to_user_id
                for row in Follow.query.filter(
                    Follow.from_user_id == current_user_id,
                    Follow.to_user_id.in_(from_user_ids),
                ).all()
            }

            followed = {
                row.from_user_id
                for row in Follow.query.filter(
                    Follow.to_user_id == current_user_id,
                    Follow.from_user_id.in_(from_user_ids),
                ).all()
            }

            follow_state_map = {
                uid: {
                    "following": uid in following,
                    "followed": uid in followed,
                }
                for uid in from_user_ids
            }

        follow_state_map_for_items = follow_state_map

    for notification_ in notifications.items:
        item_dict = notification_.to_dict(follow_state_map_for_items)
        result["items"].append(item_dict)

    return jsonify(result), 200


@bp.get("/unread-count")
@jwt_required()
def get_unread_count():
    """읽지 않은 알림 개수 조회"""
    current_user_id = int(get_jwt_identity())

    count = Notification.query.filter_by(
        to_user_id=current_user_id, is_checked=False
    ).count()

    return jsonify({"unread_count": count}), 200


@bp.patch("/<int:notification_id>")
@jwt_required()
def mark_notification_as_read(notification_id):
    """알림 읽음 처리"""
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
    """모든 알림 읽음 처리"""
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
    """알림 삭제"""
    current_user_id = int(get_jwt_identity())

    notification = Notification.query.filter_by(
        notification_id=notification_id, to_user_id=current_user_id
    ).first()

    if not notification:
        return jsonify({"message": "알림을 찾을 수 없습니다."}), 404

    db.session.delete(notification)
    db.session.commit()

    return jsonify({"message": "알림이 삭제되었습니다."}), 200
