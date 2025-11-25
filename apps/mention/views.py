"""
멘션 뷰
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from apps.config.server import db
from apps.mention.models import Mention
from apps.notification.models import Notification
from apps.auth.models import User
from apps.post.models import Post
from apps.reply.models import Reply

bp = Blueprint("mention", __name__, url_prefix="/mention")


@bp.get("/api_info")
def api_info():
    """
    멘션 API 정보 제공 (개발용)
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
    """멘션 직렬화 헬퍼 함수"""
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
    """
    멘션 생성 (POST or REPLY)

    Request Body:
    {
        "mentioned_user_id": 2,
        "post_id": 5  // or "reply_id": 10
    }

    Response: 201
    {
        "message": "멘션 생성 완료",
        "mention": {...}
    }
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

    # 중복 멘션 확인
    existing_mention = Mention.query.filter_by(
        mentioned_user_id=mentioned_user_id, post_id=post_id, reply_id=reply_id
    ).first()

    if existing_mention:
        return jsonify({"error": "이미 존재하는 멘션입니다"}), 400

    try:
        # 멘션 생성
        new_mention = Mention(
            mentioner_id=current_user_id,
            mentioned_user_id=mentioned_user_id,
            post_id=post_id,
            reply_id=reply_id,
        )
        db.session.add(new_mention)
        db.session.flush()  # mention_id 생성

        # 알림 자동 생성
        notification = Notification(
            user_id=mentioned_user_id,
            from_user_id=current_user_id,
            type="MENTION",
            post_id=post_id,
            reply_id=reply_id,
            mention_id=new_mention.mention_id,
        )
        db.session.add(notification)
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
    """
    내가 받은 멘션 조회

    Response: 200
    {
        "mentions": [...]
    }
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
    """
    내가 보낸 멘션 조회

    Response: 200
    {
        "mentions": [...]
    }
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
    """
    특정 게시글의 모든 멘션 조회

    Response: 200
    {
        "mentions": [...]
    }
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
    """
    모든 멘션 조회 (관리자용)

    Response: 200
    {
        "mentions": [...]
    }
    """
    # TODO: 관리자 권한 체크 추가 필요
    mentions = Mention.query.order_by(Mention.created_at.desc()).all()

    return jsonify({"mentions": [serialize_mention(m) for m in mentions]}), 200


@bp.route("/type/<string:mention_type>", methods=["GET"])
@jwt_required()
def get_mentions_by_type(mention_type):
    """
    타입별 멘션 조회

    Parameters:
    - mention_type: "POST" or "REPLY"

    Response: 200
    {
        "mentions": [...]
    }
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
