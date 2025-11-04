from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Mention
from ..models.mention import MentionType
from ..extensions import db


bp = Blueprint('mention', __name__)

# 멘션 등록
@bp.route("/create", methods=["POST"])
@jwt_required()
def create_mention():
    """
    content_type: 'POST' | 'REPLY' | 'SUBREPLY'
    object_id: 멘션이 발생한 대상의 ID (post_id, reply_id 등)
    user_id: 언급된 사용자 ID
    post_id: 원본 게시글 ID
    """

    data = request.get_json() or {}
    current_user_id = get_jwt_identity()

    content_type = data.get("content_type")
    object_id = data.get("object_id")
    mentioned_user_id = data.get("user_id")
    post_id = data.get("post_id")

    # 필수값 검증
    if not all([content_type, object_id, mentioned_user_id]):
        return jsonify({"message": "content_type, object_id, user_id는 필수입니다."}), 400

    # 타입 검증
    if content_type.upper() not in ["POST", "REPLY", "SUBREPLY"]:
        return jsonify({"message": "content_type은 POST, REPLY, SUBREPLY 중 하나여야 합니다."}), 400

    # 멘션 중복 방지 (unique_mention 제약)
    existing = Mention.query.filter_by(
        content_type=content_type.upper(),
        object_id=object_id,
        user_id=mentioned_user_id
    ).first()

    if existing:
        return jsonify({"message": "이미 존재하는 멘션입니다."}), 409

    mention = Mention(
        content_type=MentionType[content_type.upper()],
        object_id=object_id,
        mentioned_user_id=mentioned_user_id,
        post_id=post_id
    )

    db.session.add(mention)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "멘션 등록 실패"}), 400

    return jsonify({
        "message": "멘션 등록 완료",
        "mention": {
            "mention_id": mention.mention_id,
            "content_type": mention.content_type.value,
            "object_id": mention.object_id,
            "user_id": mention.user_id,
            "post_id": mention.post_id,
            "created_at": mention.created_at.isoformat()
        }
    }), 201

# user_id로 특정 유저가 언급된 멘션 조회
@bp.route("/user/<int:user_id>", methods=["GET"])
@jwt_required()
def get_mentions_for_user(user_id):
    current_user_id = int(get_jwt_identity())  # JWT에서 현재 유저 ID 가져오기
    if user_id != current_user_id:
        return jsonify({"message": "권한 없음"}), 403

    mentions = Mention.query.filter_by(user_id=user_id).all()
    result = []
    for m in mentions:
        result.append({
            "mention_id": m.mention_id,
            "content_type": m.content_type.value,
            "object_id": m.object_id,
            "post_id": m.post_id,
            "created_at": m.created_at.isoformat(),
            "is_checked": m.is_checked
        })
    return jsonify(result), 200

# ㅡㅡㅡㅡㅡㅡㅡㅡ아래는 관리자용ㅡㅡㅡㅡㅡㅡㅡㅡ

# 전체 멘션 조회 (관리자용)
@bp.route("/mentions", methods=["GET"])
@jwt_required()
def get_all_mentions():
    mentions = Mention.query.all()
    result = []
    for m in mentions:
        result.append({
            "mention_id": m.mention_id,
            "content_type": m.content_type.value,
            "object_id": m.object_id,
            "user_id": m.user_id,
            "post_id": m.post_id,
            "created_at": m.created_at.isoformat()
        })
    return jsonify(result), 200

# 게시글 id로 특정 게시글 내 멘션 조회
@bp.route("/post/<int:post_id>", methods=["GET"])
def get_mentions_in_post(post_id):
    mentions = Mention.query.filter_by(post_id=post_id).all()
    result = []
    for m in mentions:
        result.append({
            "mention_id": m.mention_id,
            "content_type": m.content_type.value,
            "object_id": m.object_id,
            "user_id": m.user_id,
            "created_at": m.created_at.isoformat()
        })
    return jsonify(result), 200

# 멘션 타입별 조회(POST, REPLY, SUBREPLY)
@bp.route("/type/<mention_type>", methods=["GET"])
def get_mentions_by_type(mention_type):
    mentions = Mention.query.filter_by(content_type=mention_type.upper()).all()
    result = []
    for m in mentions:
        result.append({
            "mention_id": m.mention_id,
            "object_id": m.object_id,
            "user_id": m.user_id,
            "post_id": m.post_id,
            "created_at": m.created_at.isoformat()
        })
    return jsonify(result), 200