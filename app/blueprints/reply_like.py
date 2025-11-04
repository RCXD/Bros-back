from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import ReplyLike

bp = Blueprint("reply_like", __name__)


# 특정 댓글의 좋아요 수 조회
@bp.route("/<int:reply_id>", methods=["GET"])
def get_reply_likes(reply_id):
    count = ReplyLike.query.filter_by(reply_id=reply_id).count()
    return jsonify({"reply_id": reply_id, "like_count": count}), 200


# 내가 좋아요한 댓글 목록
@bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_reply_likes():
    page = request.args.get("page", 1, type=int)
    current_user_id = get_jwt_identity()
    likes = ReplyLike.query.filter_by(user_id=current_user_id).paginate(
        page=page, per_page=10
    )

    result_list = []
    for like in likes.items:
        result_list.append({"reply_id": like.reply_id, "user_id": like.user_id})
    return jsonify(result_list), 200


# 좋아요 등록 (댓글/대댓글 모두 동일)
@bp.route("/<int:reply_id>", methods=["POST"])
@jwt_required()
def add_reply_like(reply_id):
    current_user_id = get_jwt_identity()

    existing = ReplyLike.query.filter_by(
        reply_id=reply_id, user_id=current_user_id
    ).first()
    if existing:
        return jsonify({"message": "이미 좋아요한 댓글입니다"}), 400

    like = ReplyLike(reply_id=reply_id, user_id=current_user_id)
    db.session.add(like)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "댓글 좋아요 등록 완료",
                "reply_id": reply_id,
                "user_id": current_user_id,
            }
        ),
        201,
    )


# 좋아요 취소
@bp.route("/<int:reply_id>", methods=["DELETE"])
@jwt_required()
def remove_reply_like(reply_id):
    current_user_id = get_jwt_identity()

    like = ReplyLike.query.filter_by(reply_id=reply_id, user_id=current_user_id).first()
    if not like:
        return jsonify({"message": "좋아요 기록이 없습니다"}), 404

    db.session.delete(like)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "댓글 좋아요 취소 완료",
                "reply_id": reply_id,
                "user_id": current_user_id,
            }
        ),
        200,
    )
