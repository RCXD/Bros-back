"""
게시글 모듈 - 게시글 CRUD 및 상호작용
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.exc import IntegrityError

from apps.config.server import db
from apps.post.models import Post, Category, PostLike
from apps.auth.models import User

bp = Blueprint("post", __name__)


@bp.get("")
def get_posts():
    """
    페이지네이션 및 필터링을 포함한 게시글 목록 조회
    Query params:
        - page: 페이지 번호
        - per_page: 페이지당 항목 수
        - category: 카테고리별 필터
        - order_by: 정렬 순서 (latest, popular 등)
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    category = request.args.get("category")
    order_by = request.args.get("order_by", "latest")
    
    query = Post.query
    
    # 카테고리별 필터링
    if category:
        cat = Category.query.filter_by(category_name=category).first()
        if cat:
            query = query.filter_by(category_id=cat.category_id)
    
    # 정렬
    if order_by == "popular":
        query = query.order_by(Post.view_counts.desc())
    else:  # latest
        query = query.order_by(Post.created_at.desc())
    
    # 페이지네이션
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    posts = []
    for post in pagination.items:
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        posts.append({
            "post_id": post.post_id,
            "user_id": post.user_id,
            "content": post.content,
            "category": post.category.category_name if post.category else None,
            "view_counts": post.view_counts,
            "like_count": like_count,
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat()
        })
    
    return jsonify({
        "posts": posts,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200


@bp.post("")
@jwt_required()
def create_post():
    """
    새 게시글 작성
    Form data:
        - content: 필수
        - category_id: 필수
        - images: 선택 (다중 파일)
    """
    try:
        current_user = get_current_user()
        content = request.form.get("content")
        category_id = request.form.get("category_id", type=int)
        
        if not content:
            return jsonify({"error": "내용은 필수입니다"}), 400
        if not category_id:
            return jsonify({"error": "카테고리는 필수입니다"}), 400
        
        # 카테고리 존재 확인
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"error": "유효하지 않은 카테고리입니다"}), 400
        
        # 게시글 생성
        post = Post(
            user_id=current_user.user_id,
            category_id=category_id,
            content=content
        )
        
        db.session.add(post)
        db.session.commit()
        
        # TODO: 이미지 업로드 처리
        
        return jsonify({
            "message": "게시글이 작성되었습니다",
            "post_id": post.post_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"게시글 작성 실패: {str(e)}"}), 400


@bp.get("/<int:post_id>")
def get_post(post_id):
    """ID로 단일 게시글 조회"""
    post = Post.query.get_or_404(post_id)
    
    # 조회수 증가
    post.add_view_counts()
    db.session.commit()
    
    # 좋아요 수 조회
    like_count = PostLike.query.filter_by(post_id=post_id).count()
    
    # 작성자 정보 조회
    author = User.query.get(post.user_id)
    
    return jsonify({
        "post_id": post.post_id,
        "user_id": post.user_id,
        "author": {
            "user_id": author.user_id,
            "username": author.username,
            "nickname": author.nickname,
            "profile_img": author.profile_img
        } if author else None,
        "content": post.content,
        "category": post.category.category_name if post.category else None,
        "view_counts": post.view_counts,
        "like_count": like_count,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat()
    }), 200


@bp.put("/<int:post_id>")
@jwt_required()
def update_post(post_id):
    """
    게시글 수정
    Form data:
        - content: 선택
        - images: 선택
    """
    try:
        current_user = get_current_user()
        post = Post.query.get_or_404(post_id)
        
        # 소유권 확인
        if post.user_id != current_user.user_id:
            return jsonify({"error": "권한이 없습니다"}), 403
        
        content = request.form.get("content")
        if content:
            post.content = content
        
        # TODO: 이미지 업데이트 처리
        
        db.session.commit()
        
        return jsonify({"message": "게시글이 수정되었습니다"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"게시글 수정 실패: {str(e)}"}), 400


@bp.delete("/<int:post_id>")
@jwt_required()
def delete_post(post_id):
    """게시글 삭제"""
    try:
        current_user = get_current_user()
        post = Post.query.get_or_404(post_id)
        
        # 소유권 확인
        if post.user_id != current_user.user_id:
            return jsonify({"error": "권한이 없습니다"}), 403
        
        db.session.delete(post)
        db.session.commit()
        
        return jsonify({"message": "게시글이 삭제되었습니다"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"게시글 삭제 실패: {str(e)}"}), 400


@bp.post("/<int:post_id>/like")
@jwt_required()
def like_post(post_id):
    """게시글 좋아요 (토글)"""
    current_user_id = int(get_jwt_identity())
    
    # 게시글 존재 확인
    Post.query.get_or_404(post_id)
    
    # 이미 좋아요 했는지 확인
    existing = PostLike.query.filter_by(
        post_id=post_id,
        user_id=current_user_id
    ).first()
    
    if existing:
        # 좋아요 취소
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "좋아요 취소", "liked": False}), 200
    else:
        # 좋아요
        like = PostLike(post_id=post_id, user_id=current_user_id)
        db.session.add(like)
        db.session.commit()
        return jsonify({"message": "좋아요", "liked": True}), 201


@bp.delete("/<int:post_id>/like")
@jwt_required()
def unlike_post(post_id):
    """게시글 좋아요 취소"""
    current_user_id = int(get_jwt_identity())
    
    like = PostLike.query.filter_by(
        post_id=post_id,
        user_id=current_user_id
    ).first()
    
    if not like:
        return jsonify({"error": "좋아요하지 않은 게시글입니다"}), 404
    
    db.session.delete(like)
    db.session.commit()
    
    return jsonify({"message": "좋아요 취소"}), 200


@bp.get("/<int:post_id>/likes")
def get_post_likes(post_id):
    """게시글에 좋아요한 사용자 목록 조회"""
    # 게시글 존재 확인
    Post.query.get_or_404(post_id)
    
    likes = PostLike.query.filter_by(post_id=post_id).all()
    
    result = []
    for like in likes:
        user = User.query.get(like.user_id)
        if user:
            result.append({
                "user_id": user.user_id,
                "username": user.username,
                "nickname": user.nickname,
                "profile_img": user.profile_img
            })
    
    return jsonify({"likes": result, "count": len(result)}), 200


@bp.get("/me")
@jwt_required()
def get_my_posts():
    """현재 사용자의 게시글 조회"""
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    
    pagination = Post.query.filter_by(user_id=current_user_id)\
        .order_by(Post.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    posts = []
    for post in pagination.items:
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        posts.append({
            "post_id": post.post_id,
            "content": post.content,
            "category": post.category.category_name if post.category else None,
            "view_counts": post.view_counts,
            "like_count": like_count,
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat()
        })
    
    return jsonify({
        "posts": posts,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200
