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
from apps.post.models import Post, PostLike, Category
from apps.image.models import Image
from apps.user.models import Follow
from apps.auth.models import User
from apps.product.models import Product

bp = Blueprint("feed", __name__)
INFO_PATH = Path(__file__).resolve().parent / "info.json"


def _serialize_post(post, preview_length=None):
    """Serialize a Post ORM object to a dictionary.

    Args:
        post: The Post instance to serialize.
        preview_length: If set, truncates the post content to this many characters.

    Returns:
        A dict containing post metadata, author info, image list, and engagement stats.
    """
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
        "category": post.category.category_name if post.category else None,
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
    """Build a standard paginated JSON response for feed endpoints.

    Args:
        posts_payload: List of serialized post dicts to include in the response.
        pagination: SQLAlchemy Pagination object holding totals and page flags.
        page: Current page number.
        per_page: Number of items per page.

    Returns:
        A tuple of (Response, 200) containing the paginated feed data as JSON.
    """
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
    """Serialize a Product ORM object to a flat dictionary.

    Args:
        product: The Product instance to serialize.

    Returns:
        A dict with product fields suitable for JSON output.
    """
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
    """Return feed API endpoint metadata for development reference.

    Returns:
        JSON response with module info and endpoint list, HTTP 200.
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
    """Retrieve the personalized feed for the authenticated user (Write-Heavy model).

    Reads pre-built FeedItem rows rather than performing a live Follow JOIN,
    providing O(1) SELECT performance. Images are fetched in a single batch
    query to avoid N+1 database calls.

    Returns:
        Paginated JSON feed response with ``items``, pagination metadata, HTTP 200.
    """
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # ✅ Write-Heavy 모델: FeedItem 활용으로 단순 SELECT
    pagination = (
        db.session.query(
            FeedItem, Post, User, func.count(PostLike.post_id).label("like_count")
        )
        .join(Post, FeedItem.related_post_id == Post.post_id)
        .join(User, Post.user_id == User.user_id)
        .outerjoin(PostLike, Post.post_id == PostLike.post_id)
        .filter(FeedItem.user_id == current_user_id)
        .group_by(FeedItem.feed_id, Post.post_id, User.user_id)
        .order_by(FeedItem.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    posts_data = []
    post_ids = [item[1].post_id for item in pagination.items]

    # 한 번에 모든 이미지 조회 (N+1 방지)
    images_map = {}
    if post_ids:
        images = Image.query.filter(Image.post_id.in_(post_ids)).all()
        for img in images:
            if img.post_id not in images_map:
                images_map[img.post_id] = []
            images_map[img.post_id].append(img)

    # 데이터 조합
    for feed_item, post, author, like_count in pagination.items:
        posts_data.append(
            {
                "feed_id": feed_item.feed_id,
                "feed_type": feed_item.feed_type,
                "post_id": post.post_id,
                "author": {
                    "user_id": author.user_id,
                    "nickname": author.nickname,
                    "profile_img": author.profile_img,
                },
                "content": post.content,
                "category": post.category.category_name if post.category else None,
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
                    for img in images_map.get(post.post_id, [])
                ],
                "created_at": post.created_at.isoformat(),
                "is_read": feed_item.is_read,
            }
        )

    return (
        jsonify(
            {
                "items": posts_data,
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
    """Return trending posts ranked by view count within a time window.

    Args (query string):
        period: Time window - ``today``, ``week`` (default), or ``month``.
        limit: Maximum number of posts to return (default 20).

    Returns:
        JSON with ``items`` list of trending post dicts and ``count``, HTTP 200.
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
                "category": post.category.category_name if post.category else None,
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
    """Return a paginated reel-style feed of short posts.

    Args (query string):
        page: Page number (default 1).
        per_page: Items per page (default 12).
        max_length: Maximum post content length in characters (default 140).

    Returns:
        Paginated JSON feed response, HTTP 200.
    """
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
    """Return a personalized recommendation feed based on the user's liked categories.

    Excludes posts from already-followed users and prioritises high-view posts
    in the same categories as previously liked content.

    Returns:
        Paginated JSON feed response, HTTP 200.
    """
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    following_ids = {
        f.to_user_id for f in Follow.query.filter_by(from_user_id=current_user_id).all()
    }
    following_ids.add(current_user_id)

    category_rows = (
        db.session.query(Post.category_id)
        .join(PostLike, Post.post_id == PostLike.post_id)
        .filter(PostLike.user_id == current_user_id, Post.category_id.isnot(None))
        .distinct()
        .limit(4)
        .all()
    )
    category_ids = [row[0] for row in category_rows if row[0] is not None]

    recommendation_query = Post.query.filter(~Post.user_id.in_(list(following_ids)))
    if category_ids:
        recommendation_query = recommendation_query.filter(
            Post.category_id.in_(category_ids)
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
    """Return a paginated shopping feed of active products.

    Args (query string):
        page: Page number (default 1).
        per_page: Items per page (default 16).
        category: Optional case-insensitive category name filter.

    Returns:
        Paginated JSON product feed, HTTP 200.
    """
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
    """Return highlight posts from followed users that exceed a minimum view count.

    Args (query string):
        limit: Maximum number of posts to return (default 12).
        min_views: Minimum view count threshold to qualify as a highlight (default 200).

    Returns:
        JSON with ``items`` list of highlight post dicts and ``count``, HTTP 200.
    """
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
    """Return a paginated explore feed for discovering new content.

    Args (query string):
        category: Optional category name to filter posts.
        page: Page number (default 1).
        per_page: Items per page (default 20).

    Returns:
        Paginated JSON feed response, HTTP 200.
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
                "category": post.category.category_name if post.category else None,
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
    """Return posts near a geographic coordinate (geospatial query not yet implemented).

    Args (query string):
        lat: Latitude of the search origin (required).
        lon: Longitude of the search origin (required).
        radius: Search radius in kilometres (default 10).

    Returns:
        JSON with empty ``items`` list and a status message, HTTP 200.
        HTTP 400 if ``lat`` or ``lon`` is missing.
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
