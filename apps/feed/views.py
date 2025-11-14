"""
피드 모듈 - 사용자 피드 및 타임라인
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from apps.config.server import db
from apps.post.models import Post, PostLike, Category, Image
from apps.user.models import Follow
from apps.auth.models import User

bp = Blueprint("feed", __name__)


@bp.get("")
@jwt_required()
def get_feed():
    """
    개인화된 사용자 피드 조회
    Query params:
        - page: 페이지 번호
        - per_page: 페이지당 항목 수
    """
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    
    # 현재 사용자가 팔로우하는 사용자 ID 조회
    following_ids = [f.following_id for f in Follow.query.filter_by(follower_id=current_user_id).all()]
    
    # 자신의 게시글 포함
    following_ids.append(current_user_id)
    
    # 팔로우한 사용자들의 게시글 조회
    pagination = Post.query.filter(Post.user_id.in_(following_ids))\
        .order_by(Post.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    posts = []
    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()
        
        posts.append({
            "post_id": post.post_id,
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
            "images": [{
                "image_id": img.image_id,
                "uuid": img.uuid,
                "directory": img.directory,
                "original_image_name": img.original_image_name,
                "ext": img.ext
            } for img in images],
            "created_at": post.created_at.isoformat()
        })
    
    return jsonify({
        "items": posts,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200


@bp.get("/trending")
def get_trending():
    """
    트렌딩 게시글 조회
    Query params:
        - period: 기간 (today, week, month)
        - limit: 반환할 게시글 수
    """
    period = request.args.get("period", "week")
    limit = request.args.get("limit", 20, type=int)
    
    # 시간 범위 계산
    now = datetime.now()
    if period == "today":
        start_time = now - timedelta(days=1)
    elif period == "month":
        start_time = now - timedelta(days=30)
    else:  # week
        start_time = now - timedelta(days=7)
    
    # 트렌딩 게시글 조회 (기간 내 조회수 기준)
    posts = Post.query.filter(Post.created_at >= start_time)\
        .order_by(Post.view_counts.desc())\
        .limit(limit).all()
    
    result = []
    for post in posts:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()
        
        result.append({
            "post_id": post.post_id,
            "author": {
                "user_id": author.user_id,
                "username": author.username,
                "nickname": author.nickname
            } if author else None,
            "content": post.content[:200],  # 미리보기
            "category": post.category.category_name if post.category else None,
            "view_counts": post.view_counts,
            "like_count": like_count,
            "images": [{
                "image_id": img.image_id,
                "uuid": img.uuid,
                "directory": img.directory,
                "original_image_name": img.original_image_name,
                "ext": img.ext
            } for img in images],
            "created_at": post.created_at.isoformat()
        })
    
    return jsonify({"items": result, "count": len(result)}), 200


@bp.get("/explore")
def get_explore():
    """
    탐색 피드 (새로운 콘텐츠 발견)
    Query params:
        - category: 카테고리별 필터
        - page: 페이지 번호
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    category = request.args.get("category")
    
    query = Post.query
    
    if category:
        cat = Category.query.filter_by(category_name=category).first()
        if cat:
            query = query.filter_by(category_id=cat.category_id)
    
    # 최신순 정렬
    pagination = query.order_by(Post.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    posts = []
    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()
        
        posts.append({
            "post_id": post.post_id,
            "author": {
                "user_id": author.user_id,
                "username": author.username,
                "nickname": author.nickname,
                "profile_img": author.profile_img
            } if author else None,
            "content": post.content[:200],
            "category": post.category.category_name if post.category else None,
            "view_counts": post.view_counts,
            "like_count": like_count,
            "images": [{
                "image_id": img.image_id,
                "uuid": img.uuid,
                "directory": img.directory,
                "original_image_name": img.original_image_name,
                "ext": img.ext
            } for img in images],
            "created_at": post.created_at.isoformat()
        })
    
    return jsonify({
        "items": posts,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200


@bp.get("/nearby")
@jwt_required()
def get_nearby():
    """
    주변 위치의 게시글 조회
    Query params:
        - lat: 위도
        - lon: 경도
        - radius: 검색 반경(km)
    """
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    radius = request.args.get("radius", 10, type=float)
    
    if lat is None or lon is None:
        return jsonify({"error": "lat와 lon은 필수입니다"}), 400
    
    # TODO: 위치 모델 사용 가능 시 지리공간 쿼리 구현
    # 현재는 빈 결과 반환
    return jsonify({
        "items": [],
        "message": "지리공간 검색이 아직 구현되지 않았습니다"
    }), 200
