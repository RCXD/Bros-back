"""
Mention views — API endpoints for creating and querying user mentions.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from apps.config.server import db
from apps.mention.models import Mention, MentionItemType
from apps.notification.models import Notification
from apps.notification.utils import create_mention_notification
from apps.auth.models import User
from apps.post.models import Post
from apps.reply.models import Reply

bp = Blueprint("mention", __name__, url_prefix="/mention")


@bp.get("/api_info")
def api_info():
    """Return mention API metadata for development use.

    Returns:
        JSON object describing available endpoints with 200 status.
    """
    info = {
        "module": "mention",
        "base_path": "/mention",
        "description": "사용자 멘션 조회 및 관리",
        "endpoints": [
            {
                "path": "/mention",
                "method": "POST",
                "auth_required": True,
                "description": "멘션 생성",
                "json_body": {
                    "mentioned_user_id": "멘션할 사용자 ID (필수)",
                    "post_id": "게시물 ID (선택)",
                    "reply_id": "댓글 ID (선택)",
                },
            },
            {
                "path": "/mention",
                "method": "GET",
                "auth_required": True,
                "description": "멘션 목록 조회",
                "query_params": {
                    "page": "페이지 번호 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                },
            },
            {
                "path": "/mention/<mention_id>",
                "method": "PATCH",
                "auth_required": True,
                "description": "멘션 확인 처리",
            },
            {
                "path": "/mention/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


def serialize_mention(mention):
    """Serialize a Mention ORM object to a plain dictionary.

    Args:
        mention: A Mention model instance to serialize.

    Returns:
        Dictionary containing the mention's fields and related user info.
    """
    mention_type = "POST" if mention.post_id else "REPLY"

    return {
        "mention_id": mention.mention_id,
        "mentioner_id": mention.mentioner_id,
        "mentioner_username": mention.mentioner.username if mention.mentioner else None,
        "mentioner_nickname": mention.mentioner.nickname if mention.mentioner else None,
        "mentioned_user_id": mention.mentioned_user_id,
        "mentioned_username": (
            mention.mentioned_user.username if mention.mentioned_user else None
        ),
        "post_id": mention.post_id,
        "reply_id": mention.reply_id,
        "mention_type": mention_type,
        "created_at": mention.created_at.isoformat() if mention.created_at else None,
        "is_checked": mention.is_checked,
    }


# === LEGACY ENDPOINTS from app/blueprints/mention.py ===


@bp.route("/", methods=["POST"])
@jwt_required()
def create_mention():
    """Create a mention targeting either a post or a reply.

    Expects a JSON body with ``mentioned_user_id`` and exactly one of
    ``post_id`` or ``reply_id``.  A notification is automatically dispatched
    to the mentioned user via :func:`create_mention_notification`.

    Args:
        (via request body):
            mentioned_user_id: ID of the user being mentioned.
            post_id: ID of the post to attach the mention to (mutually
                exclusive with ``reply_id``).
            reply_id: ID of the reply to attach the mention to (mutually
                exclusive with ``post_id``).

    Returns:
        JSON object with a confirmation message and the serialized mention
        with 201 status on success, or an error message with 400/404/500
        status on failure.
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    mentioned_user_id = data.get("mentioned_user_id")
    post_id = data.get("post_id")
    reply_id = data.get("reply_id")

    # 검증
    if not mentioned_user_id:
        return jsonify({"error": "mentioned_user_id is required"}), 400

    if (post_id and reply_id) or (not post_id and not reply_id):
        return (
            jsonify(
                {"error": "정확히 하나의 대상(post_id or reply_id)만 지정해야 합니다"}
            ),
            400,
        )

    # 자기 자신 멘션 방지
    if current_user_id == mentioned_user_id:
        return jsonify({"error": "자기 자신을 멘션할 수 없습니다"}), 400

    # 사용자 존재 확인
    mentioned_user = User.query.get(mentioned_user_id)
    if not mentioned_user:
        return jsonify({"error": "해당 사용자를 찾을 수 없습니다"}), 404

    # 대상 존재 확인
    if post_id:
        target = Post.query.get(post_id)
        if not target:
            return jsonify({"error": "해당 게시글을 찾을 수 없습니다"}), 404
    else:
        target = Reply.query.get(reply_id)
        if not target:
            return jsonify({"error": "해당 댓글을 찾을 수 없습니다"}), 404

    # item_type과 item_id 결정
    if post_id:
        item_type = MentionItemType.POST
        item_id = post_id
    else:
        item_type = MentionItemType.REPLY
        item_id = reply_id

    # 중복 멘션 확인
    existing_mention = Mention.query.filter_by(
        mentioned_user_id=mentioned_user_id, item_type=item_type, item_id=item_id
    ).first()

    if existing_mention:
        return jsonify({"error": "이미 존재하는 멘션입니다"}), 400

    try:
        # 멘션 생성
        new_mention = Mention(
            mentioner_id=current_user_id,
            mentioned_user_id=mentioned_user_id,
            item_type=item_type,
            item_id=item_id,
        )
        db.session.add(new_mention)
        db.session.flush()  # mention_id 생성

        # 알림 자동 생성 (utils 함수 사용)
        create_mention_notification(current_user_id, mentioned_user_id, new_mention)

        db.session.commit()

        return (
            jsonify(
                {"message": "멘션 생성 완료", "mention": serialize_mention(new_mention)}
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"멘션 생성 실패: {str(e)}"}), 500


@bp.route("/mine", methods=["GET"])
@jwt_required()
def get_my_mentions():
    """Retrieve all mentions received by the current user, newest first.

    Returns:
        JSON object with a ``mentions`` list of serialized mention dicts,
        with 200 status.
    """
    current_user_id = get_jwt_identity()
    # TODO:
    mentions = (
        Mention.query.filter_by(mentioned_user_id=current_user_id)
        .order_by(Mention.created_at.desc())
        .all()
    )

    return jsonify({"mentions": [serialize_mention(m) for m in mentions]}), 200


@bp.route("/sent", methods=["GET"])
@jwt_required()
def get_sent_mentions():
    """Retrieve all mentions sent by the current user, newest first.

    Returns:
        JSON object with a ``mentions`` list of serialized mention dicts,
        with 200 status.
    """
    current_user_id = get_jwt_identity()

    mentions = (
        Mention.query.filter_by(mentioner_id=current_user_id)
        .order_by(Mention.created_at.desc())
        .all()
    )

    return jsonify({"mentions": [serialize_mention(m) for m in mentions]}), 200


@bp.route("/post/<int:post_id>", methods=["GET"])
@jwt_required()
def get_post_mentions(post_id):
    """Retrieve all mentions attached to a specific post.

    Args:
        post_id: Primary key of the post whose mentions are requested.

    Returns:
        JSON object with a ``mentions`` list of serialized mention dicts with
        200 status, or a 404 error if the post does not exist.
    """
    post = Post.query.get(post_id)
    if not post:
        return jsonify({"error": "해당 게시글을 찾을 수 없습니다"}), 404

    mentions = (
        Mention.query.filter_by(post_id=post_id)
        .order_by(Mention.created_at.desc())
        .all()
    )

    return jsonify({"mentions": [serialize_mention(m) for m in mentions]}), 200


@bp.route("/all", methods=["GET"])
@jwt_required()
def get_all_mentions():
    """Retrieve every mention in the system, newest first (admin use).

    Returns:
        JSON object with a ``mentions`` list of all serialized mention dicts,
        with 200 status.
    """
    # TODO: 관리자 권한 체크 추가 필요
    mentions = Mention.query.order_by(Mention.created_at.desc()).all()

    return jsonify({"mentions": [serialize_mention(m) for m in mentions]}), 200


@bp.route("/type/<string:mention_type>", methods=["GET"])
@jwt_required()
def get_mentions_by_type(mention_type):
    """Retrieve the current user's received mentions filtered by type.

    Args:
        mention_type: Either ``"POST"`` or ``"REPLY"`` (case-insensitive).

    Returns:
        JSON object with a ``mentions`` list of serialized mention dicts with
        200 status, or a 400 error if ``mention_type`` is not valid.
    """
    current_user_id = get_jwt_identity()

    if mention_type.upper() not in ["POST", "REPLY"]:
        return jsonify({"error": "유효하지 않은 타입입니다 (POST or REPLY)"}), 400

    if mention_type.upper() == "POST":
        mentions = (
            Mention.query.filter(
                Mention.mentioned_user_id == current_user_id,
                Mention.post_id.isnot(None),
            )
            .order_by(Mention.created_at.desc())
            .all()
        )
    else:
        mentions = (
            Mention.query.filter(
                Mention.mentioned_user_id == current_user_id,
                Mention.reply_id.isnot(None),
            )
            .order_by(Mention.created_at.desc())
            .all()
        )

    return jsonify({"mentions": [serialize_mention(m) for m in mentions]}), 200
