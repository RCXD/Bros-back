from ..models.post import Post
from ..models.user import User
from ..models.reply import Reply
from ..models.post_like import PostLike
from ..extensions import db
from flask import jsonify


def apply_order(query, order_by):
    """
    쿼리에 정렬 조건 적용
    """
    if order_by == "latest":
        query = query.order_by(Post.created_at.desc())
    elif order_by == "oldest":
        query = query.order_by(Post.created_at.asc())
    elif order_by == "popular":
        query = query.order_by(Post.view_count.desc())
    elif order_by == "most_liked":
        query = (
            query.outerjoin(Post.likes)
            .group_by(Post.post_id)
            .order_by(db.func.count(PostLike.like_id).desc())
        )
    elif order_by == "most_commented":
        query = (
            query.outerjoin(Post.replies)
            .group_by(Post.post_id)
            .order_by(db.func.count(Reply.reply_id).desc())
        )
    else:
        # 기본 정렬: 최신순
        query = query.order_by(Post.created_at.desc())

    return query


def serialize_post(post):
    """Post 객체를 JSON 응답 형태로 직렬화"""
    likes = Post.query.filter(PostLike.post_id == post.post_id).count()
    replies = Reply.query.filter(Reply.post_id == post.post_id).count()
    nickname = User.query.filter(User.user_id == post.user_id).first().nickname
    images = [
        {
            "image_id": img.image_id,
            "uuid": img.uuid,
            "original_image_name": img.original_image_name,
            "ext": img.ext,
        }
        for img in post.images
    ]

    location_data = None
    if hasattr(post, "location_obj") and post.location_obj:
        loc = post.location_obj
        location_data = {
            "location_id": loc.location_id,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "name": loc.name,
            "recommend_point": loc.recommend_point,
            "risk_point": loc.risk_point,
            "created_at": loc.created_at.isoformat(),
            "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
        }

    return {
        "post_id": post.post_id,
        "user_id": post.user_id,
        "nickname": nickname,
        "category_id": post.category_id,
        "content": post.content,
        "location": location_data,
        "view_counts": post.view_counts,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        "images": images,
        "likes": likes,
        "replies": replies,
    }


def paginate_posts(query, page, per_page):
    """공통 페이지네이션 + 직렬화 처리"""
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    result = [serialize_post(p) for p in pagination.items]
    return (
        jsonify(
            {
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
                "items": result,
            }
        ),
        200,
    )
