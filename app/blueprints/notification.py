from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Notification, User, Post, Reply, Mention
from sqlalchemy.exc import IntegrityError

bp = Blueprint("notification", __name__)


# 알림 생성
@bp.route("/", methods=["POST"])
@jwt_required()
def create_notification():
    data = request.get_json() or {}
    from_user_id = int(get_jwt_identity())

    to_user_id = data.get("to_user_id")
    notif_type = data.get("type")  # "MENTION", "LIKE", "COMMENT" 등
    post_id = data.get("post_id")
    reply_id = data.get("reply_id")
    mention_id = data.get("mention_id")

    # 필수값 체크
    if not to_user_id or not notif_type:
        return jsonify(success=False, message="to_user_id와 type은 필수입니다."), 400

    # 자기 자신에게 알림 생성 금지
    if from_user_id == to_user_id:
        return (
            jsonify(success=False, message="자기 자신에게 알림을 생성할 수 없습니다."),
            400,
        )

    # 수신자 존재 확인
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify(success=False, message="수신자 유저가 존재하지 않습니다."), 404

    notification = Notification(
        type=notif_type.upper(),
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        post_id=post_id,
        reply_id=reply_id,
        mention_id=mention_id,
    )

    db.session.add(notification)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(success=False, message=f"DB 제약조건 오류: {e}"), 400
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=f"알림 생성 실패: {e}"), 400

    return jsonify(success=True, data=notification.serialize()), 201


# 내 알림 조회
@bp.route("/mine", methods=["GET"])
@jwt_required()
def get_my_notifications():
    current_user_id = int(get_jwt_identity())
    notifications = (
        Notification.query.filter_by(to_user_id=current_user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    result = [n.serialize() for n in notifications]
    return jsonify(success=True, data=result), 200


# 알림 읽음 처리
@bp.route("/<int:notification_id>/read", methods=["PATCH"])
@jwt_required()
def mark_notification_as_read(notification_id):
    current_user_id = int(get_jwt_identity())
    notification = Notification.query.filter_by(
        notification_id=notification_id, to_user_id=current_user_id
    ).first()
    if not notification:
        return jsonify(success=False, message="알림을 찾을 수 없습니다."), 404

    notification.is_checked = True
    db.session.commit()
    return jsonify(success=True, data=notification.serialize()), 200


# 관리자용 전체 알림 조회
@bp.route("/all", methods=["GET"])
@jwt_required()
def get_all_notifications():
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    result = [n.serialize() for n in notifications]
    return jsonify(success=True, data=result), 200
