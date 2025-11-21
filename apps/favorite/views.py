"""
즐겨찾기 모듈 - 사용자 즐겨찾기 및 북마크
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.exc import IntegrityError

from apps.config.server import db
from apps.favorite.models import Favorite, FavoriteType
from apps.post.models import Post
from apps.product.models import Product

bp = Blueprint("favorite", __name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@bp.get("")
@jwt_required()
def get_favorites():
    """
    현재 사용자의 즐겨찾기 조회
    Query params:
        - item_type: 타입별 필터 (STORY, ROUTE, REVIEW, REPORT, PRODUCT)
        - page: 페이지 번호
        - per_page: 페이지당 항목 수
    """
    current_user_id = int(get_jwt_identity())

    item_type = request.args.get("item_type")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Favorite.query.filter_by(user_id=current_user_id)

    # 타입별 필터링
    if item_type:
        try:
            favorite_type = FavoriteType[item_type.upper()]
            query = query.filter_by(item_type=favorite_type)
        except KeyError:
            return jsonify({"message": f"유효하지 않은 타입: {item_type}"}), 400

    # 페이지네이션
    pagination = query.order_by(Favorite.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    favorites = [fav.to_dict() for fav in pagination.items]

    return (
        jsonify(
            {
                "items": favorites,
                "total": pagination.total,
                "pages": pagination.pages,
                "page": page,
            }
        ),
        200,
    )


@bp.post("/<string:item_type>/<int:item_id>")
@jwt_required()
def toggle_favorite(item_type, item_id):
    """
    즐겨찾기 토글 (추가/제거)
    Path params:
        - item_type: story, product, route 등
        - item_id: 아이템 ID
    """
    current_user_id = int(get_jwt_identity())

    # item_type을 FavoriteType으로 매핑
    type_mapping = {
        "story": FavoriteType.STORY,
        "route": FavoriteType.ROUTE,
        "review": FavoriteType.REVIEW,
        "report": FavoriteType.REPORT,
        "product": FavoriteType.PRODUCT,
    }

    favorite_type = type_mapping.get(item_type.lower())
    if not favorite_type:
        return jsonify({"message": f"유효하지 않은 타입: {item_type}"}), 400

    # 아이템 존재 확인
    if favorite_type == FavoriteType.PRODUCT:
        item = Product.query.get(item_id)
    else:
        item = Post.query.get(item_id)

    if not item:
        return jsonify({"message": "아이템을 찾을 수 없습니다"}), 404

    # 이미 즐겨찾기 했는지 확인
    existing = Favorite.query.filter_by(
        user_id=current_user_id, item_type=favorite_type, item_id=item_id
    ).first()

    if existing:
        # 이미 즐겨찾기 → 제거
        db.session.delete(existing)
        db.session.commit()
        return (
            jsonify({"message": "즐겨찾기에서 제거되었습니다", "is_favorited": False}),
            200,
        )
    else:
        # 즐겨찾기 추가
        favorite = Favorite(
            user_id=current_user_id, item_type=favorite_type, item_id=item_id
        )
        db.session.add(favorite)
        db.session.commit()
        return (
            jsonify({"message": "즐겨찾기에 추가되었습니다", "is_favorited": True}),
            201,
        )


@bp.delete("/<string:item_type>/<int:item_id>")
@jwt_required()
def remove_from_favorites(item_type, item_id):
    """
    즐겨찾기 제거
    Path params:
        - item_type: post, product, route 등
        - item_id: 아이템 ID
    """
    current_user_id = int(get_jwt_identity())

    # item_type을 FavoriteType으로 매핑
    type_mapping = {
        "story": FavoriteType.STORY,
        "route": FavoriteType.ROUTE,
        "review": FavoriteType.REVIEW,
        "report": FavoriteType.REPORT,
        "product": FavoriteType.PRODUCT,
    }

    favorite_type = type_mapping.get(item_type.lower())
    if not favorite_type:
        return jsonify({"message": f"유효하지 않은 타입: {item_type}"}), 400

    # 즐겨찾기 찾기
    favorite = Favorite.query.filter_by(
        user_id=current_user_id, item_type=favorite_type, item_id=item_id
    ).first()

    if not favorite:
        return jsonify({"message": "즐겨찾기를 찾을 수 없습니다"}), 404

    db.session.delete(favorite)
    db.session.commit()

    return jsonify({"message": "즐겨찾기에서 제거되었습니다"}), 200


@bp.get("/check/<string:item_type>/<int:item_id>")
@jwt_required()
def check_favorite(item_type, item_id):
    """
    즐겨찾기 여부 확인
    Path params:
        - item_type: post, product, route 등
        - item_id: 아이템 ID
    """
    current_user_id = int(get_jwt_identity())

    # item_type을 FavoriteType으로 매핑
    type_mapping = {
        "story": FavoriteType.STORY,
        "route": FavoriteType.ROUTE,
        "review": FavoriteType.REVIEW,
        "report": FavoriteType.REPORT,
        "product": FavoriteType.PRODUCT,
    }

    favorite_type = type_mapping.get(item_type.lower())
    if not favorite_type:
        return jsonify({"message": f"유효하지 않은 타입: {item_type}"}), 400

    # 즐겨찾기 존재 확인
    exists = (
        Favorite.query.filter_by(
            user_id=current_user_id, item_type=favorite_type, item_id=item_id
        ).first()
        is not None
    )

    return jsonify({"is_favorited": exists}), 200
