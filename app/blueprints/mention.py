from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Mention
from ..extensions import db
from ..utils.mention_utils import serialize_mention


bp = Blueprint("mention", __name__)


# 멘션 등록
@bp.route("/", methods=["POST"])
@jwt_required()
def create_mention():

    data = request.get_json() or {}
    current_user_id = get_jwt_identity()

    post_id = data.get("post_id")
    reply_id = data.get("reply_id")
    mentioned_user_id = data.get("user_id")
    post_id = data.get("post_id")

    filled_targets = [t for t in (post_id, reply_id) if t is not None]
    if len(filled_targets) != 1:
        return (
            jsonify(
                success=False,
                message="post_id, reply_id 중 하나만 전달해야 합니다.",
            ),
            400,
        )
    from ..models import Post, Reply

    if post_id:
        target = Post.query.get_or_404(post_id)
    elif reply_id:
        target = Reply.query.get_or_404(reply_id)
    if not target:
        return jsonify(success=False, message="대상 객체를 찾을 수 없습니다."), 404

    # 내가 작성한 글/댓글이 맞는지 확인
    if target.user_id != current_user_id:
        return (
            jsonify(success=False, message="내 게시글/댓글에만 멘션할 수 있습니다."),
            403,
        )

    existing = Mention.query.filter_by(
        mentioned_user_id=mentioned_user_id,
        post_id=post_id,
        reply_id=reply_id
    ).first()

    if existing:
        return jsonify(success=False, message="이미 등록된 멘션입니다."), 409

    mention = Mention(
        mentioned_user_id=mentioned_user_id,
        post_id=post_id,
        reply_id=reply_id
    )

    db.session.add(mention)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"message": "멘션 등록 실패"}), 400

    return serialize_mention(mention), 201


# 내 맨션 조회
@bp.route("/mine", methods=["GET"])
@jwt_required()
def get_mentions_for_user():
    current_user_id = int(get_jwt_identity())  # JWT에서 현재 유저 ID 가져오기

    mentions = Mention.query.filter_by(user_id=current_user_id).all()
    result = []
    for m in mentions:
        result.append(serialize_mention(m))
    return jsonify(result), 200


# ㅡㅡㅡㅡㅡㅡㅡㅡ아래는 관리자용ㅡㅡㅡㅡㅡㅡㅡㅡ


# 전체 멘션 조회 (관리자용)
@bp.route("/mentions", methods=["GET"])
@jwt_required()
def get_all_mentions():
    mentions = Mention.query.all()
    result = []
    for m in mentions:
        result.append(serialize_mention(m))
    return jsonify(result), 200


# 게시글 id로 특정 게시글 내 멘션 조회
@bp.route("/post/<int:post_id>", methods=["GET"])
def get_mentions_in_post(post_id):
    mentions = Mention.query.filter_by(post_id=post_id).all()
    result = []
    for m in mentions:
        result.append(serialize_mention(m))
    return jsonify(result), 200


# 멘션 타입별 조회(POST, REPLY, SUBREPLY)
@bp.route("/type/<mention_type>", methods=["GET"])
def get_mentions_by_type(mention_type):
    mentions = Mention.query.filter_by(content_type=mention_type.upper()).all()
    result = []
    for m in mentions:
        result.append(serialize_mention(m))
    return jsonify(result), 200
