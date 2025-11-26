"""
즐겨찾기 모듈 - 사용자 즐겨찾기 및 북마크
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy.exc import IntegrityError

from apps.config.server import db
from apps.favorite.models import Favorite, FavoriteType
from apps.post.models import Post, PostLike, Category
from apps.image.models import Image
from apps.product.models import Product
from apps.place.models import Place

bp = Blueprint("favorite", __name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@bp.get("/api_info")
def api_info():
    """
    즐겨찾기 API 정보 제공 (개발용)
    """
    info = {
        "module": "favorite",
        "base_path": "/favorite",
        "description": "사용자 즐겨찾기 및 북마크 관리",
        "endpoints": [
            {
                "path": "/favorite",
                "method": "GET",
                "auth_required": True,
                "description": "현재 사용자의 즐겨찾기 조회",
                "query_params": {
                    "item_type": "타입별 필터 (STORY, ROUTE, REVIEW, REPORT, PRODUCT, PLACE)",
                    "page": "페이지 번호 (기본: 1)",
                    "per_page": "페이지당 항목 수 (기본: 20)",
                },
            },
            {
                "path": "/favorite/me/<item_type>",
                "method": "GET",
                "auth_required": True,
                "description": "특정 타입의 즐겨찾기 상세 조회 (실제 아이템 정보 포함)",
                "path_params": {
                    "item_type": "story, route, review, report, product, place"
                },
            },
            {
                "path": "/favorite/<item_type>/<item_id>",
                "method": "PATCH",
                "auth_required": True,
                "description": "즐겨찾기 토글 (추가/제거)",
                "path_params": {
                    "item_type": "story, route, review, report, product, place",
                    "item_id": "아이템 ID",
                },
            },
            {
                "path": "/favorite/<item_type>/<item_id>",
                "method": "DELETE",
                "auth_required": True,
                "description": "즐겨찾기 제거",
            },
            {
                "path": "/favorite/check/<item_type>/<item_id>",
                "method": "GET",
                "auth_required": True,
                "description": "즐겨찾기 여부 확인",
            },
            {
                "path": "/favorite/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


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
                "per_page": per_page,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            }
        ),
        200,
    )


@bp.get("/me/<string:item_type>")
@jwt_required()
def get_favorites_by_type(item_type):
    """
    현재 사용자의 특정 타입 즐겨찾기 조회 (실제 Post/Product 목록 반환)
    Path params:
        - item_type: story, route, review, report, product, place
    """
    current_user_id = int(get_jwt_identity())

    # item_type을 FavoriteType으로 매핑
    type_mapping = {
        "story": FavoriteType.STORY,
        "route": FavoriteType.ROUTE,
        "review": FavoriteType.REVIEW,
        "report": FavoriteType.REPORT,
        "product": FavoriteType.PRODUCT,
        "place": FavoriteType.PLACE,
    }

    favorite_type = type_mapping.get(item_type.lower())
    if not favorite_type:
        return jsonify({"message": f"유효하지 않은 타입: {item_type}"}), 400

    # 즐겨찾기 목록 조회
    favorites = (
        Favorite.query.filter_by(user_id=current_user_id, item_type=favorite_type)
        .order_by(Favorite.created_at.desc())
        .all()
    )

    items_list = []

    # Product 타입인 경우
    if favorite_type == FavoriteType.PRODUCT:
        for fav in favorites:
            product = Product.query.get(fav.item_id)
            if product:
                items_list.append(
                    {
                        "product_id": product.product_id,
                        "name": product.name,
                        "description": product.description,
                        "price": float(product.price),
                        "stock": product.stock,
                        "is_active": product.is_active,
                        "created_at": product.created_at.isoformat(),
                        "updated_at": product.updated_at.isoformat(),
                        "favorited_at": fav.created_at.isoformat(),
                    }
                )
    elif favorite_type == FavoriteType.PLACE:
        for fav in favorites:
            place = Place.query.get(fav.item_id)
            if place:
                items_list.append(
                    {
                        "place_id":place.place_id,
                        "name":place.name,
                        "alt_name":place.alt_name,
                        "coordinate":place.coordinate,
                        "geom":place.geom,
                        "description":place.description,
                        "created_at":place.created_at
                    }
                )

    # Post 타입인 경우 (story, route, review, report)
    else:
        for fav in favorites:
            post = Post.query.get(fav.item_id)
            if post and post.category:
                # Post의 실제 카테고리와 요청한 타입이 일치하는지 확인
                if post.category.category_name.upper() != favorite_type.name.upper():
                    continue

                like_count = PostLike.query.filter_by(post_id=post.post_id).count()
                is_liked = (
                    PostLike.query.filter_by(
                        post_id=post.post_id, user_id=current_user_id
                    ).first()
                    is not None
                )
                images = Image.query.filter_by(post_id=post.post_id).all()

                items_list.append(
                    {
                        "post_id": post.post_id,
                        "content": post.content,
                        "category": post.category.category_name,
                        "view_counts": post.view_counts,
                        "like_count": like_count,
                        "isLiked": is_liked,
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
                        "updated_at": post.updated_at.isoformat(),
                        "favorited_at": fav.created_at.isoformat(),
                    }
                )

    return jsonify({"items": items_list, "count": len(items_list)}), 200


@bp.patch("/<string:item_type>/<int:item_id>")
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
        "place": FavoriteType.PLACE,
    }

    favorite_type = type_mapping.get(item_type.lower())
    if not favorite_type:
        return jsonify({"message": f"유효하지 않은 타입: {item_type}"}), 400

    # 아이템 존재 확인 및 실제 타입 결정
    if favorite_type == FavoriteType.PRODUCT:
        item = Product.query.get(item_id)
        if not item:
            return jsonify({"message": "상품을 찾을 수 없습니다"}), 404
        actual_favorite_type = FavoriteType.PRODUCT
    elif favorite_type == FavoriteType.PLACE:
        item = Place.query.get(item_id)
        if item:
            actual_favorite_type= FavoriteType.PLACE
    else:
        # Post인 경우 실제 카테고리 확인
        item = Post.query.get(item_id)
        if not item:
            return jsonify({"message": "게시글을 찾을 수 없습니다"}), 404

        if not item.category:
            return jsonify({"message": "게시글 카테고리가 없습니다"}), 400

        # Post의 실제 카테고리로 FavoriteType 결정
        try:
            actual_favorite_type = FavoriteType[item.category.category_name.upper()]
        except KeyError:
            return (
                jsonify(
                    {
                        "message": f"유효하지 않은 카테고리: {item.category.category_name}"
                    }
                ),
                400,
            )

    # 이미 즐겨찾기 했는지 확인 (실제 타입으로)
    existing = Favorite.query.filter_by(
        user_id=current_user_id, item_type=actual_favorite_type, item_id=item_id
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
        # 즐겨찾기 추가 (실제 카테고리로 저장)
        favorite = Favorite(
            user_id=current_user_id, item_type=actual_favorite_type, item_id=item_id
        )
        db.session.add(favorite)
        db.session.commit()

        result = []
        # item_type별 item_id의 리스트 반환
        for favorite_type_ in FavoriteType:
            # 특정 favorite type의 item_id 리스트
            favorite_ = Favorite.query.filter_by(
                user_id=current_user_id, item_type=favorite_type_
            ).all()
            item_ids = []
            for fav in favorite_:
                item_ids.append(fav.item_id)
            result.append({favorite_type_.name: item_ids})

        return (
            jsonify({"message": "즐겨찾기에 추가되었습니다", "item_ids": result}),
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
        "place": FavoriteType.PLACE,
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
