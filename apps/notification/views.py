"""
알림 관련 API 엔드포인트
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from apps.config.server import db
from apps.notification.models import Notification, NotificationType
from apps.auth.models import User
from apps.post.models import Post
from apps.reply.models import Reply


bp = Blueprint("notification", __name__, url_prefix="/notification")


@bp.route("/", methods=["POST"])
@jwt_required()
def create_notification():
    """알림 생성 (수동 호출용)"""
    data = request.get_json() or {}
    from_user_id = int(get_jwt_identity())

    to_user_id = data.get("to_user_id")
    notif_type = data.get("type")
    post_id = data.get("post_id")
    reply_id = data.get("reply_id")
    mention_id = data.get("mention_id")
    product_id = data.get("product_id")

    # 필수값 체크
    if not to_user_id or not notif_type:
        return jsonify(success=False, message="to_user_id와 type은 필수입니다."), 400

    # 자기 자신에게 알림 생성 금지
    if from_user_id == to_user_id:
        return jsonify(success=False, message="자기 자신에게 알림을 생성할 수 없습니다."), 400

    # 수신자 존재 확인
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify(success=False, message="수신자 유저가 존재하지 않습니다."), 404

    # NotificationType enum 검증
    try:
        notification_type = NotificationType[notif_type.upper()]
    except KeyError:
        return jsonify(success=False, message=f"유효하지 않은 알림 타입: {notif_type}"), 400

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
        return jsonify(success=False, message=f"DB 제약조건 오류: {str(e)}"), 400
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=f"알림 생성 실패: {str(e)}"), 500

    return jsonify(success=True, data=notification.to_dict()), 201


@bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_notifications():
    """내 알림 조회"""
    current_user_id = int(get_jwt_identity())
    
    # 페이지네이션 파라미터
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    
    # 읽지 않은 알림만 조회 옵션
    unread_only = request.args.get("unread_only", "false").lower() == "true"

    query = Notification.query.filter_by(to_user_id=current_user_id)
    
    if unread_only:
        query = query.filter_by(is_checked=False)
    
    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    result = {
        "notifications": [n.to_dict() for n in notifications.items],
        "total": notifications.total,
        "page": notifications.page,
        "per_page": notifications.per_page,
        "total_pages": notifications.pages,
    }
    
    return jsonify(success=True, data=result), 200


@bp.route("/unread-count", methods=["GET"])
@jwt_required()
def get_unread_count():
    """읽지 않은 알림 개수 조회"""
    current_user_id = int(get_jwt_identity())
    
    count = Notification.query.filter_by(
        to_user_id=current_user_id,
        is_checked=False
    ).count()
    
    return jsonify(success=True, data={"unread_count": count}), 200


@bp.route("/<int:notification_id>", methods=["PATCH"])
@jwt_required()
def mark_notification_as_read(notification_id):
    """알림 읽음 처리"""
    current_user_id = int(get_jwt_identity())
    
    notification = Notification.query.filter_by(
        notification_id=notification_id,
        to_user_id=current_user_id
    ).first()
    
    if not notification:
        return jsonify(success=False, message="알림을 찾을 수 없습니다."), 404

    notification.is_checked = True
    db.session.commit()
    
    return jsonify(success=True, data=notification.to_dict()), 200


@bp.route("/mark-all-read", methods=["PATCH"])
@jwt_required()
def mark_all_as_read():
    """모든 알림 읽음 처리"""
    current_user_id = int(get_jwt_identity())
    
    updated_count = Notification.query.filter_by(
        to_user_id=current_user_id,
        is_checked=False
    ).update({"is_checked": True})
    
    db.session.commit()
    
    return jsonify(
        success=True,
        message=f"{updated_count}개의 알림을 읽음 처리했습니다.",
        data={"updated_count": updated_count}
    ), 200


@bp.route("/<int:notification_id>", methods=["DELETE"])
@jwt_required()
def delete_notification(notification_id):
    """알림 삭제"""
    current_user_id = int(get_jwt_identity())
    
    notification = Notification.query.filter_by(
        notification_id=notification_id,
        to_user_id=current_user_id
    ).first()
    
    if not notification:
        return jsonify(success=False, message="알림을 찾을 수 없습니다."), 404

    db.session.delete(notification)
    db.session.commit()
    
    return jsonify(success=True, message="알림이 삭제되었습니다."), 200
