from flask import Blueprint, request, jsonify
from ..models import Reply
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity

bp = Blueprint("reply", __name__)


@bp.route("/", methods=["POST"])
@jwt_required()
def create_reply():
    data = request.get_json() or {}
    content = data.get("content")
    post_id = data.get("post_id")
    parent_id_ = data.get("parent_id")

    if not content or not post_id:
        return jsonify({"message": "내용과 게시글 ID는 필수입니다."}), 400
    
    if len(content) > 400:
        return jsonify({"message": "댓글은 400자 이하로 입력해야 합니다."}), 400

    # 부모 댓글이 있다면 존재 여부 확인
    if parent_id_:
        parent = Reply.query.get(parent_id_)
        if parent.parent_id is not None:
            return jsonify({"message": "대댓글에는 추가로 댓글을 달 수 없습니다."}), 400     

    # 현재 로그인 유저 ID 가져오기
    current_user_id = get_jwt_identity()

    # 새 댓글(또는 대댓글) 생성
    reply = Reply(
        content=content,
        post_id=post_id,
        user_id=current_user_id,
    )
    if parent_id_:
        reply.parent_id = parent_id_

    db.session.add(reply)
    try:
        db.session.commit()
        return (
            jsonify({"message": "댓글이 작성되었습니다.", "reply_id": reply.reply_id}),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"댓글 등록 실패: {str(e)}"}), 400


@bp.route("/<int:reply_id>", methods=["DELETE"])
@jwt_required()
def delete_reply(reply_id):
    current_user_id = int(get_jwt_identity())
    reply = Reply.query.get_or_404(reply_id)

    if reply.user_id != current_user_id:
        return jsonify({"message": "본인의 댓글만 삭제할 수 있습니다."}), 403

    # 자식 댓글(대댓글)도 함께 삭제
    Reply.query.filter_by(parent_id=reply_id).delete()

    db.session.delete(reply)
    db.session.commit()

    return jsonify({"message": "댓글이 삭제되었습니다."}), 200


@bp.route("/<int:reply_id>", methods=["PUT"])
@jwt_required()
def update_reply(reply_id):
    data = request.get_json() or {}
    content = data.get("content")

    if not content:
        return jsonify({"message": "내용은 필수입니다."}), 400

    current_user_id = int(get_jwt_identity())
    reply = Reply.query.get_or_404(reply_id)

    if reply.user_id != current_user_id:
        return jsonify({"message": "본인의 댓글만 수정할 수 있습니다."}), 403

    reply.content = content
    db.session.commit()

    return jsonify({"message": "댓글이 수정되었습니다."}), 200


@bp.route("/<int:post_id>", methods=["GET"])
def get_root_replies(post_id):
    """
    루트 댓글 10개 단위로 페이지네이션
    """
    page = request.args.get("page", 1, type=int)
    PER_PAGE = 10

    pagination = (
        Reply.query.filter_by(post_id=post_id, parent_id=None)
        .order_by(Reply.created_at.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )

    root_replies = [
        {
            "reply_id": r.reply_id,
            "content": r.content,
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


@bp.route("/children/<int:parent_id>", methods=["GET"])
def get_child_replies(parent_id):
    """
    특정 댓글(parent_id)의 대댓글 20개 단위로 페이지네이션
    """
    page = request.args.get("page", 1, type=int)
    PER_PAGE = 20

    pagination = (
        Reply.query.filter_by(parent_id=parent_id)
        .order_by(Reply.created_at.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
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
