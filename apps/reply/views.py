"""
댓글 모듈 - 댓글 및 대댓글
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user

from apps.config.server import db
from apps.reply.models import Reply, ReplyLike
from apps.post.models import Post
from apps.auth.models import User

bp = Blueprint("reply", __name__)


@bp.get("")
def get_replies():
    """
    게시글의 댓글 조회
    Query params:
        - post_id: 필수 - 댓글을 조회할 게시글 ID
        - page: 페이지 번호
        - per_page: 페이지당 항목 수
    """
    post_id = request.args.get("post_id", type=int)
    if not post_id:
        return jsonify({"error": "post_id는 필수입니다"}), 400
    
    # 게시글 존재 확인
    Post.query.get_or_404(post_id)
    
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    
    # 최상위 댓글 조회 (부모 댓글이 없는 것)
    pagination = Reply.query.filter_by(post_id=post_id, parent_id=None)\
        .order_by(Reply.created_at.asc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    replies = []
    for reply in pagination.items:
        author = User.query.get(reply.user_id)
        like_count = ReplyLike.query.filter_by(reply_id=reply.reply_id).count()
        child_count = Reply.query.filter_by(parent_id=reply.reply_id).count()
        
        replies.append({
            "reply_id": reply.reply_id,
            "post_id": reply.post_id,
            "user_id": reply.user_id,
            "author": {
                "username": author.username,
                "nickname": author.nickname,
                "profile_img": author.profile_img
            } if author else None,
            "content": reply.content,
            "parent_id": reply.parent_id,
            "like_count": like_count,
            "child_count": child_count,
            "created_at": reply.created_at.isoformat(),
            "updated_at": reply.updated_at.isoformat()
        })
    
    return jsonify({
        "items": replies,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200


@bp.post("")
@jwt_required()
def create_reply():
    """
    댓글 작성
    JSON body:
        - post_id: 필수
        - content: 필수
        - parent_id: 선택 (대댓글용)
    """
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        post_id = data.get("post_id")
        content = data.get("content")
        parent_id = data.get("parent_id")
        
        if not post_id or not content:
            return jsonify({"error": "post_id와 content는 필수입니다"}), 400
        
        # 게시글 존재 확인
        Post.query.get_or_404(post_id)
        
        # 부모 댓글 검증 (제공된 경우)
        if parent_id:
            parent = Reply.query.get(parent_id)
            if not parent:
                return jsonify({"error": "부모 댓글을 찾을 수 없습니다"}), 404
            if parent.post_id != post_id:
                return jsonify({"error": "부모 댓글이 다른 게시글에 속합니다"}), 400
        
        reply = Reply(
            post_id=post_id,
            user_id=current_user.user_id,
            content=content,
            parent_id=parent_id
        )
        
        db.session.add(reply)
        db.session.commit()
        
        return jsonify({
            "message": "댓글이 작성되었습니다",
            "reply_id": reply.reply_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"댓글 작성 실패: {str(e)}"}), 400


@bp.get("/<int:reply_id>")
def get_reply(reply_id):
    """ID로 단일 댓글 조회"""
    reply = Reply.query.get_or_404(reply_id)
    author = User.query.get(reply.user_id)
    like_count = ReplyLike.query.filter_by(reply_id=reply_id).count()
    
    return jsonify({
        "reply_id": reply.reply_id,
        "post_id": reply.post_id,
        "user_id": reply.user_id,
        "author": {
            "username": author.username,
            "nickname": author.nickname,
            "profile_img": author.profile_img
        } if author else None,
        "content": reply.content,
        "parent_id": reply.parent_id,
        "like_count": like_count,
        "created_at": reply.created_at.isoformat(),
        "updated_at": reply.updated_at.isoformat()
    }), 200


@bp.put("/<int:reply_id>")
@jwt_required()
def update_reply(reply_id):
    """
    댓글 수정
    JSON body:
        - content: 필수
    """
    try:
        current_user = get_current_user()
        reply = Reply.query.get_or_404(reply_id)
        
        # 소유권 확인
        if reply.user_id != current_user.user_id:
            return jsonify({"error": "권한이 없습니다"}), 403
        
        data = request.get_json()
        content = data.get("content")
        
        if not content:
            return jsonify({"error": "content는 필수입니다"}), 400
        
        reply.content = content
        db.session.commit()
        
        return jsonify({"message": "댓글이 수정되었습니다"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"댓글 수정 실패: {str(e)}"}), 400


@bp.delete("/<int:reply_id>")
@jwt_required()
def delete_reply(reply_id):
    """댓글 삭제"""
    try:
        current_user = get_current_user()
        reply = Reply.query.get_or_404(reply_id)
        
        # 소유권 확인
        if reply.user_id != current_user.user_id:
            return jsonify({"error": "권한이 없습니다"}), 403
        
        db.session.delete(reply)
        db.session.commit()
        
        return jsonify({"message": "댓글이 삭제되었습니다"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"댓글 삭제 실패: {str(e)}"}), 400


@bp.post("/<int:reply_id>/like")
@jwt_required()
def like_reply(reply_id):
    """댓글 좋아요 (토글)"""
    current_user_id = int(get_jwt_identity())
    
    # 댓글 존재 확인
    Reply.query.get_or_404(reply_id)
    
    # 이미 좋아요 했는지 확인
    existing = ReplyLike.query.filter_by(
        reply_id=reply_id,
        user_id=current_user_id
    ).first()
    
    if existing:
        # 좋아요 취소
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "댓글 좋아요 취소", "liked": False}), 200
    else:
        # 좋아요
        like = ReplyLike(reply_id=reply_id, user_id=current_user_id)
        db.session.add(like)
        db.session.commit()
        return jsonify({"message": "댓글 좋아요", "liked": True}), 201


@bp.delete("/<int:reply_id>/like")
@jwt_required()
def unlike_reply(reply_id):
    """댓글 좋아요 취소"""
    current_user_id = int(get_jwt_identity())
    
    like = ReplyLike.query.filter_by(
        reply_id=reply_id,
        user_id=current_user_id
    ).first()
    
    if not like:
        return jsonify({"error": "좋아요하지 않은 댓글입니다"}), 404
    
    db.session.delete(like)
    db.session.commit()
    
    return jsonify({"message": "댓글 좋아요 취소"}), 200


@bp.get("/<int:reply_id>/replies")
def get_nested_replies(reply_id):
    """댓글의 대댓글 조회"""
    # 부모 댓글 존재 확인
    Reply.query.get_or_404(reply_id)
    
    replies = Reply.query.filter_by(parent_id=reply_id)\
        .order_by(Reply.created_at.asc()).all()
    
    result = []
    for reply in replies:
        author = User.query.get(reply.user_id)
        like_count = ReplyLike.query.filter_by(reply_id=reply.reply_id).count()
        
        result.append({
            "reply_id": reply.reply_id,
            "post_id": reply.post_id,
            "user_id": reply.user_id,
            "author": {
                "username": author.username,
                "nickname": author.nickname,
                "profile_img": author.profile_img
            } if author else None,
            "content": reply.content,
            "like_count": like_count,
            "created_at": reply.created_at.isoformat(),
            "updated_at": reply.updated_at.isoformat()
        })
    
    return jsonify({"items": result, "count": len(result)}), 200
