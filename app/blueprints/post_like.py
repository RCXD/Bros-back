from flask import Blueprint, jsonify, request
from ..extensions import db
from ..models import PostLike, Post, User
from flask_jwt_extended import jwt_required, get_jwt_identity

bp = Blueprint("post_like", __name__)


# 좋아요 등록
@bp.route("/", methods=["POST"])
@jwt_required()
def add_like():
    data = request.get_json() or {}
    post_id = data.get("post_id")
    user_id = data.get("user_id")

    # 필수 값 확인
    if not post_id or not user_id:
        return jsonify({"error": "post_id와 user_id가 필요합니다"}), 400

    # 중복 방지 (이미 좋아요 했는지 확인)
    existing_like = PostLike.query.filter_by(post_id=post_id, user_id=user_id).first()
    if existing_like:
        return jsonify({"message": "이미 좋아요한 게시글입니다"}), 400

    like = PostLike(post_id=post_id, user_id=user_id)
    db.session.add(like)
    db.session.commit()

    return (
        jsonify(
            {"message": "좋아요 등록 완료", "post_id": post_id, "user_id": user_id}
        ),
        201,
    )


# 좋아요 취소
@bp.route("/", methods=["DELETE"])
@jwt_required()
def remove_like():
    data = request.get_json() or {}
    post_id = data.get("post_id")
    user_id = data.get("user_id")

    if not post_id or not user_id:
        return jsonify({"error": "post_id와 user_id가 필요합니다"}), 400

    like = PostLike.query.filter_by(post_id=post_id, user_id=user_id).first()
    if not like:
        return jsonify({"message": "좋아요 기록이 없습니다"}), 404

    db.session.delete(like)
    db.session.commit()

    return (
        jsonify(
            {"message": "좋아요 취소 완료", "post_id": post_id, "user_id": user_id}
        ),
        200,
    )


# 특정 게시글의 좋아요 수 조회
@bp.route("/post/<int:post_id>", methods=["GET"])
def get_post_likes(post_id):
    count = PostLike.query.filter_by(post_id=post_id).count()
    return jsonify({"post_id": post_id, "like_count": count}), 200


# 특정 사용자가 좋아요한 게시글 목록 조회
@bp.route("/user/<int:user_id>", methods=["GET"])
def get_user_likes(user_id):
    pagination = PostLike.query.filter_by(user_id=user_id).paginate(
        page=request.args.get("page", 1, type=int), per_page=10
    )
    result = []
    for like in pagination.items:
        result.append({"post_id": like.post_id, "user_id": like.user_id})
    response = {
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
        "items": result,
    }

    return jsonify(response), 200


# 전체 좋아요 목록 조회 (테스트용)
@bp.route("/", methods=["GET"])
def get_all_likes():
    likes = PostLike.query.all()

    result = []
    for like in likes:
        result.append({"post_id": like.post_id, "user_id": like.user_id})

    return jsonify(result), 200
