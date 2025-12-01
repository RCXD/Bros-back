"""
검색 서비스 뷰
"""

from flask import jsonify, request, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_, and_, func

from apps.search import bp
from apps.config.server import db
from apps.search.models import SearchHistory, SearchCache
from apps.post.models import Post, PostLike
from apps.auth.models import User
from apps.mention.models import Mention, MentionItemType
from apps.notification.models import Notification
from apps.product.models import Product
from apps.user.models import Follow
from apps.favorite.models import Favorite, FavoriteType


@bp.get("/api_info")
def api_info():
    """
    검색 API 정보 제공 (개발용)
    """
    info = {
        "module": "search",
        "base_path": "/search",
        "description": "통합 검색 서비스",
        "endpoints": [
            {
                "path": "/search/posts",
                "method": "GET",
                "auth_required": False,
                "description": "게시글 검색 (닉네임, 본문, 멘션된 사용자)",
                "query_params": {
                    "q": "검색어 (필수)",
                    "page": "페이지 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                },
            },
            {
                "path": "/search/my-posts",
                "method": "GET",
                "auth_required": True,
                "description": "내 게시글 검색",
                "query_params": {"q": "검색어 (필수)"},
            },
            {
                "path": "/search/liked-posts",
                "method": "GET",
                "auth_required": True,
                "description": "좋아요한 게시글 검색",
                "query_params": {"q": "검색어 (필수)"},
            },
            {
                "path": "/search/saved-posts",
                "method": "GET",
                "auth_required": True,
                "description": "보관한 게시글 검색",
                "query_params": {"q": "검색어 (필수)"},
            },
            {
                "path": "/search/notifications",
                "method": "GET",
                "auth_required": True,
                "description": "알림 검색",
                "query_params": {"q": "검색어 (필수)"},
            },
            {
                "path": "/search/followers",
                "method": "GET",
                "auth_required": True,
                "description": "팔로워 검색",
                "query_params": {"q": "검색어 (필수)"},
            },
            {
                "path": "/search/following",
                "method": "GET",
                "auth_required": True,
                "description": "팔로잉 검색",
                "query_params": {"q": "검색어 (필수)"},
            },
            {
                "path": "/search/products",
                "method": "GET",
                "auth_required": False,
                "description": "상품 검색 (상품명, 브랜드, 판매자, 카테고리, 몰)",
                "query_params": {
                    "q": "검색어 (필수)",
                    "page": "페이지 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                },
            },
            {
                "path": "/search/users",
                "method": "GET",
                "auth_required": False,
                "description": "유저 검색 (닉네임)",
                "query_params": {
                    "q": "검색어 (필수)",
                    "page": "페이지 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                },
            },
            {
                "path": "/search/history",
                "method": "GET",
                "auth_required": True,
                "description": "내 검색 기록 조회",
            },
            {
                "path": "/search/popular",
                "method": "GET",
                "auth_required": False,
                "description": "인기 검색어 조회",
                "query_params": {
                    "type": "검색 타입 (선택)",
                    "limit": "개수 (기본: 10)",
                },
            },
        ],
    }
    return jsonify(info), 200


def save_search_history(user_id, query, search_type, result_count):
    """검색 기록 저장"""
    if not user_id:
        return

    history = SearchHistory(
        user_id=user_id,
        search_query=query,
        search_type=search_type,
        result_count=result_count,
    )
    db.session.add(history)

    # 검색 캐시 업데이트
    SearchCache.increment_search_count(query, search_type)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"검색 기록 저장 실패: {e}")


def search_posts_query(query_string, base_query=None):
    """
    게시글 검색 쿼리 생성 (공통 로직)

    Args:
        query_string: 검색어
        base_query: 기본 쿼리 (None이면 Post.query 사용)

    Returns:
        검색 결과 쿼리
    """
    if base_query is None:
        base_query = Post.query

    search_pattern = f"%{query_string}%"

    # 1. 본문 내용 검색
    content_match = base_query.filter(Post.content.like(search_pattern))

    # 2. 작성자 닉네임 검색
    author_match = base_query.join(User, Post.user_id == User.user_id).filter(
        or_(User.nickname.like(search_pattern), User.username.like(search_pattern))
    )

    # 3. 멘션된 사용자 검색
    mentioned_match = (
        base_query.join(Mention, Post.post_id == Mention.item_id)
        .filter(Mention.item_type == MentionItemType.POST)
        .join(User, Mention.mentioned_user_id == User.user_id)
        .filter(
            or_(User.nickname.like(search_pattern), User.username.like(search_pattern))
        )
    )

    # UNION으로 합치기
    result_query = content_match.union(author_match, mentioned_match)

    return result_query


@bp.get("/posts")
def search_posts():
    """게시글 검색 (닉네임, 본문, 멘션된 사용자)"""
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    # 검색 쿼리 생성
    result_query = search_posts_query(query_string)

    # 최신순 정렬 및 페이지네이션
    pagination = result_query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 결과 직렬화
    posts = []
    current_user_id = getattr(g, "user_id", None)

    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        is_liked = False
        if current_user_id:
            is_liked = (
                PostLike.query.filter_by(
                    post_id=post.post_id, user_id=current_user_id
                ).first()
                is not None
            )

        posts.append(
            {
                "post_id": post.post_id,
                "author": {
                    "user_id": author.user_id if author else None,
                    "nickname": author.nickname if author else None,
                    "profile_img": author.profile_img if author else None,
                },
                "content": post.content,
                "category": post.category,
                "view_counts": post.view_counts,
                "like_count": like_count,
                "isLiked": is_liked,
                "created_at": post.created_at.isoformat(),
            }
        )

    # 검색 기록 저장
    save_search_history(current_user_id, query_string, "post", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
                "per_page": per_page,
            }
        ),
        200,
    )


@bp.get("/my-posts")
@jwt_required()
def search_my_posts():
    """내 게시글 검색"""
    current_user_id = int(get_jwt_identity())
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    # 내 게시글만 필터링
    base_query = Post.query.filter_by(user_id=current_user_id)
    result_query = search_posts_query(query_string, base_query)

    pagination = result_query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    posts = []
    for post in pagination.items:
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        is_liked = (
            PostLike.query.filter_by(
                post_id=post.post_id, user_id=current_user_id
            ).first()
            is not None
        )

        posts.append(
            {
                "post_id": post.post_id,
                "content": post.content,
                "category": post.category,
                "like_count": like_count,
                "isLiked": is_liked,
                "created_at": post.created_at.isoformat(),
            }
        )

    save_search_history(current_user_id, query_string, "my_post", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/liked-posts")
@jwt_required()
def search_liked_posts():
    """좋아요한 게시글 검색"""
    current_user_id = int(get_jwt_identity())
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    # 좋아요한 게시글만 필터링
    liked_post_ids = [
        like.post_id for like in PostLike.query.filter_by(user_id=current_user_id).all()
    ]

    base_query = Post.query.filter(Post.post_id.in_(liked_post_ids))
    result_query = search_posts_query(query_string, base_query)

    pagination = result_query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    posts = []
    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()

        posts.append(
            {
                "post_id": post.post_id,
                "author": {
                    "user_id": author.user_id if author else None,
                    "nickname": author.nickname if author else None,
                    "profile_img": author.profile_img if author else None,
                },
                "content": post.content,
                "like_count": like_count,
                "isLiked": True,
                "created_at": post.created_at.isoformat(),
            }
        )

    save_search_history(current_user_id, query_string, "liked_post", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/saved-posts")
@jwt_required()
def search_saved_posts():
    """보관한 게시글 검색"""
    current_user_id = int(get_jwt_identity())
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    # 보관한 게시글 ID 조회
    saved_post_ids = [
        fav.item_id
        for fav in Favorite.query.filter_by(
            user_id=current_user_id, item_type=FavoriteType.POST
        ).all()
    ]

    base_query = Post.query.filter(Post.post_id.in_(saved_post_ids))
    result_query = search_posts_query(query_string, base_query)

    pagination = result_query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    posts = []
    for post in pagination.items:
        author = User.query.get(post.user_id)
        like_count = PostLike.query.filter_by(post_id=post.post_id).count()
        is_liked = (
            PostLike.query.filter_by(
                post_id=post.post_id, user_id=current_user_id
            ).first()
            is not None
        )

        posts.append(
            {
                "post_id": post.post_id,
                "author": {
                    "user_id": author.user_id if author else None,
                    "nickname": author.nickname if author else None,
                    "profile_img": author.profile_img if author else None,
                },
                "content": post.content,
                "like_count": like_count,
                "isLiked": is_liked,
                "isSaved": True,
                "created_at": post.created_at.isoformat(),
            }
        )

    save_search_history(current_user_id, query_string, "saved_post", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": posts,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/notifications")
@jwt_required()
def search_notifications():
    """알림 검색 (발신자 닉네임, 메시지 내용)"""
    current_user_id = int(get_jwt_identity())
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    search_pattern = f"%{query_string}%"

    # 발신자 닉네임 또는 메시지 내용으로 검색
    query = (
        Notification.query.filter_by(to_user_id=current_user_id)
        .join(User, Notification.from_user_id == User.user_id)
        .filter(
            or_(
                User.nickname.like(search_pattern),
                User.username.like(search_pattern),
                Notification.message.like(search_pattern),
            )
        )
    )

    pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    notifications = []
    for notif in pagination.items:
        from_user = User.query.get(notif.from_user_id)
        notifications.append(
            {
                "notification_id": notif.notification_id,
                "type": notif.type.value,
                "message": notif.message,
                "from_user": {
                    "user_id": from_user.user_id if from_user else None,
                    "nickname": from_user.nickname if from_user else None,
                    "profile_img": from_user.profile_img if from_user else None,
                },
                "is_checked": notif.is_checked,
                "created_at": notif.created_at.isoformat(),
            }
        )

    save_search_history(current_user_id, query_string, "notification", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": notifications,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/followers")
@jwt_required()
def search_followers():
    """팔로워 검색"""
    current_user_id = int(get_jwt_identity())
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    search_pattern = f"%{query_string}%"

    # 나를 팔로우하는 사람들 중 검색
    query = (
        User.query.join(Follow, User.user_id == Follow.from_user_id)
        .filter(Follow.to_user_id == current_user_id)
        .filter(
            or_(User.nickname.like(search_pattern), User.username.like(search_pattern))
        )
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    users = []
    for user in pagination.items:
        # 내가 이 사람을 팔로우하는지 확인
        i_follow_them = Follow.query.filter_by(
            from_user_id=current_user_id, to_user_id=user.user_id
        ).first()

        users.append(
            {
                "user_id": user.user_id,
                "username": user.username,
                "nickname": user.nickname,
                "profile_img": user.profile_img,
                "i_follow_them": i_follow_them is not None,
            }
        )

    save_search_history(current_user_id, query_string, "follower", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": users,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/following")
@jwt_required()
def search_following():
    """팔로잉 검색"""
    current_user_id = int(get_jwt_identity())
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    search_pattern = f"%{query_string}%"

    # 내가 팔로우하는 사람들 중 검색
    query = (
        User.query.join(Follow, User.user_id == Follow.to_user_id)
        .filter(Follow.from_user_id == current_user_id)
        .filter(
            or_(User.nickname.like(search_pattern), User.username.like(search_pattern))
        )
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    users = []
    for user in pagination.items:
        # 이 사람이 나를 팔로우하는지 확인
        they_follow_me = Follow.query.filter_by(
            from_user_id=user.user_id, to_user_id=current_user_id
        ).first()

        users.append(
            {
                "user_id": user.user_id,
                "username": user.username,
                "nickname": user.nickname,
                "profile_img": user.profile_img,
                "they_follow_me": they_follow_me is not None,
            }
        )

    save_search_history(current_user_id, query_string, "following", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": users,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/products")
def search_products():
    """상품 검색 (상품명, 브랜드, 판매자, 카테고리, 몰)"""
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    search_pattern = f"%{query_string}%"

    # 다중 필드 검색
    query = Product.query.filter(
        or_(
            Product.name.like(search_pattern),
            Product.brand.like(search_pattern),
            Product.seller_name.like(search_pattern),
            Product.category.like(search_pattern),
            Product.mall_name.like(search_pattern),
        )
    )

    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    products = []
    for product in pagination.items:
        products.append(
            {
                "product_id": product.product_id,
                "name": product.name,
                "brand": product.brand,
                "seller_name": product.seller_name,
                "category": product.category,
                "mall_name": product.mall_name,
                "price": product.price,
                "image": product.image,
                "link_url": product.link_url,
                "rating": product.rating,
                "review_count": product.review_count,
            }
        )

    # 검색 기록 저장 (로그인한 경우)
    current_user_id = getattr(g, "user_id", None)
    save_search_history(current_user_id, query_string, "product", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": products,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/users")
def search_users():
    """유저 검색 (닉네임)"""
    query_string = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if not query_string:
        return jsonify({"message": "검색어를 입력해주세요"}), 400

    search_pattern = f"%{query_string}%"

    # 닉네임으로 검색 (추후 email 추가 가능)
    query = User.query.filter(
        User.nickname.like(search_pattern)
        # or_(
        #     User.nickname.like(search_pattern),
        #     User.email.like(search_pattern)  # 추후 활성화
        # )
    )

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    users = []
    current_user_id = getattr(g, "user_id", None)

    for user in pagination.items:
        user_data = {
            "user_id": user.user_id,
            "nickname": user.nickname,
            "profile_img": user.profile_img,
        }

        # 로그인한 경우 팔로우 상태 추가
        if current_user_id:
            i_follow_them = Follow.query.filter_by(
                from_user_id=current_user_id, to_user_id=user.user_id
            ).first()
            they_follow_me = Follow.query.filter_by(
                from_user_id=user.user_id, to_user_id=current_user_id
            ).first()

            user_data["i_follow_them"] = i_follow_them is not None
            user_data["they_follow_me"] = they_follow_me is not None

        users.append(user_data)

    # 검색 기록 저장 (로그인한 경우)
    save_search_history(current_user_id, query_string, "user", pagination.total)

    return (
        jsonify(
            {
                "query": query_string,
                "items": users,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.get("/history")
@jwt_required()
def get_search_history():
    """내 검색 기록 조회"""
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search_type = request.args.get("type")  # 타입별 필터링 (선택)

    query = SearchHistory.query.filter_by(user_id=current_user_id)

    if search_type:
        query = query.filter_by(search_type=search_type)

    pagination = query.order_by(SearchHistory.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    history = [item.to_dict() for item in pagination.items]

    return (
        jsonify(
            {
                "items": history,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.delete("/history/<int:search_id>")
@jwt_required()
def delete_search_history(search_id):
    """검색 기록 삭제"""
    current_user_id = int(get_jwt_identity())

    history = SearchHistory.query.filter_by(
        search_id=search_id, user_id=current_user_id
    ).first_or_404()

    db.session.delete(history)
    db.session.commit()

    return jsonify({"message": "검색 기록이 삭제되었습니다"}), 200


@bp.delete("/history")
@jwt_required()
def clear_search_history():
    """모든 검색 기록 삭제"""
    current_user_id = int(get_jwt_identity())

    SearchHistory.query.filter_by(user_id=current_user_id).delete()
    db.session.commit()

    return jsonify({"message": "모든 검색 기록이 삭제되었습니다"}), 200


@bp.get("/popular")
def get_popular_searches():
    """인기 검색어 조회"""
    search_type = request.args.get("type")
    limit = request.args.get("limit", 10, type=int)

    popular = SearchCache.get_popular_searches(search_type, limit)

    items = [item.to_dict() for item in popular]

    return jsonify({"items": items, "count": len(items)}), 200
