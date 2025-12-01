"""
피드 모듈 - 사용자 피드 및 타임라인
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import func
import json

from apps.config.server import db
from apps.post.models import CategoryType, Post, PostLike
from apps.image.models import Image
from apps.user.models import Follow
from apps.auth.models import User
from apps.product.models import Product

bp = Blueprint("feed", __name__)
INFO_PATH = Path(__file__).resolve().parent / "info.json"


def _serialize_post(post, preview_length=None):
    """공통 포스트를 딕셔너리로 변환"""
    author = post.author or User.query.get(post.user_id)
    images = Image.query.filter_by(post_id=post.post_id).all()
    like_count = post.likes.count()

    content = post.content or ""
    if preview_length:
        content = content[:preview_length]

    return {
        "post_id": post.post_id,
        "author": (
            {"nickname": author.nickname, "profile_img": author.profile_img}
            if author
            else None
        ),
        "content": content,
        "category": post.category,
        "view_counts": post.view_counts,
        "like_count": like_count,
        "images": [
            {
                "image_id": img.image_id,
                "uuid": img.uuid,
                "directory": img.directory,
                "original_image_name": img.original_image_name,
                "ext": img.ext,
            }
            for img in images
        ],
        "created_at": post.created_at.isoformat(),
    }


def _pack_feed_response(posts_payload, pagination, page, per_page):
    return (
        jsonify(
            {
                "items": posts_payload,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


def _serialize_product(product):
    return {
        "product_id": product.product_id,
        "uuid": product.uuid,
        "code": product.code,
        "name": product.name,
        "category": product.category,
        "price": str(product.price),
        "original_price": (
            str(product.original_price) if product.original_price else None
        ),
        "discount_percentage": product.discount_percentage,
        "currency": product.currency,
        "mall_name": product.mall_name,
        "seller_name": product.seller_name,
        "product_url": product.product_url,
        "rating": float(product.rating) if product.rating is not None else None,
        "n_reviews": product.n_reviews,
        "is_active": product.is_active,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


@bp.get("/api_info")
def api_info():
    """
    피드 API 정보 제공 (개발용)
    """
    try:
        with INFO_PATH.open("r", encoding="utf-8") as fh:
            info = json.load(fh)
    except Exception:
        info = {
            "module": "feed",
            "base_path": "/feed",
            "description": "사용자 맞춤 피드 조회",
            "endpoints": [],
            "note": "feed/info.json을 확인하세요",
        }
    return jsonify(info), 200


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
    following_ids = [
        f.to_user_id for f in Follow.query.filter_by(from_user_id=current_user_id).all()
    ]

    # 자신의 게시글 포함
    following_ids.append(current_user_id)

    # 팔로우한 사용자들의 게시글 조회
    pagination = (
        Post.query.filter(Post.user_id.in_(following_ids))
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    posts = []
    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()

        posts.append(
            {
                "post_id": post.post_id,
                "author": (
                    {"nickname": author.nickname, "profile_img": author.profile_img}
                    if author
                    else None
                ),
                "content": post.content,
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "images": [
                    {
                        "image_id": img.image_id,
                        "uuid": img.uuid,
                        "directory": img.directory,
                        "original_image_name": img.original_image_name,
                        "ext": img.ext,
                    }
                    for img in images
                ],
                "created_at": post.created_at.isoformat(),
            }
        )

    return (
        jsonify(
            {
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


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
    posts = (
        Post.query.filter(Post.created_at >= start_time)
        .order_by(Post.view_counts.desc())
        .limit(limit)
        .all()
    )

    result = []
    for post in posts:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()

        result.append(
            {
                "post_id": post.post_id,
                "author": (
                    {"nickname": author.nickname, "profile_img": author.profile_img}
                    if author
                    else None
                ),
                "content": post.content[:200],  # 미리보기
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "images": [
                    {
                        "image_id": img.image_id,
                        "uuid": img.uuid,
                        "directory": img.directory,
                        "original_image_name": img.original_image_name,
                        "ext": img.ext,
                    }
                    for img in images
                ],
                "created_at": post.created_at.isoformat(),
            }
        )

    return jsonify({"items": result, "count": len(result)}), 200


@bp.get("/reels")
@jwt_required()
def get_reels():
    """릴스 스타일의 짧은 콘텐츠 피드"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 12, type=int)
    max_length = request.args.get("max_length", 140, type=int)

    content_length = func.length(func.coalesce(Post.content, ""))
    reels_query = Post.query.filter(content_length <= max_length)
    pagination = reels_query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    posts_payload = [
        _serialize_post(post, preview_length=120) for post in pagination.items
    ]

    return _pack_feed_response(posts_payload, pagination, page, per_page)


@bp.get("/recommendations")
@jwt_required()
def get_recommendations():
    """사용자 취향 기반 추천 피드"""
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    following_ids = {
        f.to_user_id for f in Follow.query.filter_by(from_user_id=current_user_id).all()
    }
    following_ids.add(current_user_id)

    category_rows = (
        db.session.query(Post.category)
        .join(PostLike, Post.post_id == PostLike.post_id)
        .filter(PostLike.user_id == current_user_id, Post.category.isnot(None))
        .distinct()
        .limit(4)
        .all()
    )
    preferred_categories = [
        row[0]
        for row in category_rows
        if row[0] is not None and CategoryType.has(row[0])
    ]

    recommendation_query = Post.query.filter(~Post.user_id.in_(list(following_ids)))
    if preferred_categories:
        recommendation_query = recommendation_query.filter(
            Post.category.in_(preferred_categories)
        )

    pagination = recommendation_query.order_by(
        Post.view_counts.desc(), Post.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    posts_payload = [
        _serialize_post(post, preview_length=150) for post in pagination.items
    ]

    return _pack_feed_response(posts_payload, pagination, page, per_page)


@bp.get("/shop")
def get_shop_feed():
    """상품/쇼핑 피드"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 16, type=int)
    category = request.args.get("category")

    query = Product.query.filter(Product.is_active.is_(True))
    if category:
        query = query.filter(Product.category.ilike(f"%{category}%"))

    pagination = query.order_by(
        Product.rating.desc(), Product.n_reviews.desc(), Product.updated_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    products = [_serialize_product(product) for product in pagination.items]

    return (
        jsonify(
            {
                "items": products,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


@bp.get("/highlights")
@jwt_required()
def get_highlights():
    """하이라이트 피드 (팔로우 대상 중심)"""
    current_user_id = int(get_jwt_identity())
    limit = request.args.get("limit", 12, type=int)
    min_views = request.args.get("min_views", 200, type=int)

    following_ids = {
        f.to_user_id for f in Follow.query.filter_by(from_user_id=current_user_id).all()
    }
    following_ids.add(current_user_id)

    posts = (
        Post.query.filter(
            Post.user_id.in_(list(following_ids)), Post.view_counts >= min_views
        )
        .order_by(Post.view_counts.desc(), Post.created_at.desc())
        .limit(limit)
        .all()
    )

    payload = [_serialize_post(post, preview_length=100) for post in posts]
    return jsonify({"items": payload, "count": len(payload)}), 200


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
        normalized_category = category.strip().upper()
        if not CategoryType.has(normalized_category):
            return jsonify({"message": "유효하지 않은 카테고리입니다"}), 400
        query = query.filter_by(category=normalized_category)

    # 최신순 정렬
    pagination = query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    posts = []
    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        images = Image.query.filter_by(post_id=post.post_id).all()

        posts.append(
            {
                "post_id": post.post_id,
                "author": (
                    {"nickname": author.nickname, "profile_img": author.profile_img}
                    if author
                    else None
                ),
                "content": post.content[:200],
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "images": [
                    {
                        "image_id": img.image_id,
                        "uuid": img.uuid,
                        "directory": img.directory,
                        "original_image_name": img.original_image_name,
                        "ext": img.ext,
                    }
                    for img in images
                ],
                "created_at": post.created_at.isoformat(),
            }
        )

    return (
        jsonify(
            {
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


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
        return jsonify({"message": "lat와 lon은 필수입니다"}), 400

    # TODO: 위치 모델 사용 가능 시 지리공간 쿼리 구현
    # 현재는 빈 결과 반환
    return (
        jsonify({"items": [], "message": "지리공간 검색이 아직 구현되지 않았습니다"}),
        200,
    )
