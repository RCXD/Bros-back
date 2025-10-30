from flask import Blueprint, request, jsonify
from ..models import Reply
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity

bp = Blueprint("replies", __name__)


@bp.route("/", methods=["POST"])
@jwt_required()
def create_reply():
    data = request.get_json() or {}
    content = data.get("content")
    post_id = data.get("post_id")

    if not content or not post_id:
        return jsonify({"error": "내용과 게시글 ID는 필수입니다."}), 400

    current_user_id = get_jwt_identity()
    reply = Reply(content=content, post_id=post_id, user_id=current_user_id)
    db.session.add(reply)
    db.session.commit()

    return jsonify({"message": "댓글이 작성되었습니다.", "reply_id": reply.id}), 201


@bp.route("/<int:reply_id>", methods=["DELETE"])
@jwt_required()
def delete_reply(reply_id):
    current_user_id = get_jwt_identity()
    reply = Reply.query.get_or_404(reply_id)

    if reply.user_id != current_user_id:
        return jsonify({"error": "본인의 댓글만 삭제할 수 있습니다."}), 403

    
    db.session.delete(reply)
    db.session.commit()

    return jsonify({"message": "댓글이 삭제되었습니다."}), 200


@bp.route("/<int:reply_id>", methods=["PUT"])
@jwt_required()
def update_reply(reply_id):
    data = request.get_json() or {}
    content = data.get("content")

    if not content:
        return jsonify({"error": "내용은 필수입니다."}), 400

    current_user_id = get_jwt_identity()
    reply = Reply.query.get_or_404(reply_id)

    if reply.user_id != current_user_id:
        return jsonify({"error": "본인의 댓글만 수정할 수 있습니다."}), 403

    reply.content = content
    db.session.commit()

    return jsonify({"message": "댓글이 수정되었습니다."}), 200


@bp.route("/post/<int:post_id>/replies", methods=["GET"])
def get_root_replies(post_id):
    """
    루트 댓글 10개 단위로 페이지네이션
    """
    page = request.args.get("page", 1, type=int)
    per_page = 10

    pagination = (
        Reply.query.filter_by(post_id=post_id, parent_id=None)
        .order_by(Reply.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    root_replies = [
        {
            "reply_id": r.reply_id,
            "content": (
                r.content.decode("utf-8") if isinstance(r.content, bytes) else r.content
            ),
            "post_id": r.post_id,
            "user_id": r.user_id,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
            "children_count": Reply.query.filter_by(
                parent_id=r.reply_id
            ).count(),  # 대댓글 수
        }
        for r in pagination.items
    ]

    return (
        jsonify(
            {
                "replies": root_replies,
                "pagination": {
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "current_page": pagination.page,
                    "per_page": pagination.per_page,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                },
            }
        ),
        200,
    )


@bp.route("/reply/<int:parent_id>/children", methods=["GET"])
def get_child_replies(parent_id):
    """
    ✅ 특정 댓글(parent_id)의 대댓글 30개 단위로 페이지네이션
    """
    page = request.args.get("page", 1, type=int)
    per_page = 30

    pagination = (
        Reply.query.filter_by(parent_id=parent_id)
        .order_by(Reply.created_at.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    children = [
        {
            "reply_id": r.reply_id,
            "content": (
                r.content.decode("utf-8") if isinstance(r.content, bytes) else r.content
            ),
            "post_id": r.post_id,
            "user_id": r.user_id,
            "parent_id": r.parent_id,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in pagination.items
    ]

    return (
        jsonify(
            {
                "children": children,
                "pagination": {
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "current_page": pagination.page,
                    "per_page": pagination.per_page,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                },
            }
        ),
        200,
    )
