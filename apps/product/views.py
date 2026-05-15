"""
Product module - Product management and queries
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy import or_, and_
from decimal import Decimal

from apps.config.server import db
from apps.product.models import (
    Product,
    ProductSeller,
    ProductMall,
    ProductBrand,
)
from apps.image.models import Image
from apps.favorite.models import Favorite, FavoriteType
from apps.auth.models import User, AccountType
from apps.product.utils import get_product_images

bp = Blueprint("product", __name__)


def _serialize_metadata(entity):
    """Serialize a metadata entity to a dict, returning None if absent.

    Args:
        entity: A model instance with a ``to_dict`` method, or None.

    Returns:
        The entity dict, or None if ``entity`` is None.
    """
    return entity.to_dict() if entity else None


def _assign_metadata_from_data(product, data, id_key, name_key, entity_attr, model):
    """Assign a single metadata relationship or name field to a product from request data.

    Prefers the relationship entity (looked up via ``id_key``) over the plain name
    field (``name_key``).  If ``id_key`` is present but its value is falsy the
    relationship is cleared.

    Args:
        product: The Product instance to mutate.
        data: Dict of raw request data.
        id_key: Key in ``data`` that holds the foreign-key ID.
        name_key: Key in ``data`` that holds the plain name string fallback.
        entity_attr: Attribute name on ``product`` to set the entity instance.
        model: SQLAlchemy model class to look up by ID.
    """
    if id_key in data:
        raw_id = data.get(id_key)
        entity = model.query.get(raw_id) if raw_id else None
        setattr(product, entity_attr, entity)
    elif name_key in data:
        setattr(product, name_key, data.get(name_key))


def _apply_metadata_updates(product, data):
    """Apply seller, mall, and brand metadata updates from request data to a product.

    Args:
        product: The Product instance to mutate.
        data: Dict of raw request data containing optional metadata keys.
    """
    _assign_metadata_from_data(
        product, data, "seller_id", "seller_name", "seller_entity", ProductSeller
    )
    _assign_metadata_from_data(
        product, data, "mall_id", "mall_name", "mall_entity", ProductMall
    )
    _assign_metadata_from_data(
        product, data, "brand_id", "brand", "brand_entity", ProductBrand
    )


@bp.get("/api_info")
def api_info():
    """Return product module API metadata for development reference.

    Returns:
        JSON response with module info and endpoint list, HTTP 200.
    """
    info = {
        "module": "product",
        "base_path": "/product",
        "description": "상품 조회 및 관리",
        "endpoints": [
            {
                "path": "/product",
                "method": "GET",
                "auth_required": False,
                "description": "상품 목록 조회",
                "query_params": {
                    "category": "카테고리 필터 (fishing, motorcycle, car, bicycle, camping)",
                    "search": "검색어",
                    "page": "페이지 번호 (기본: 1)",
                    "per_page": "페이지당 개수 (기본: 20)",
                },
            },
            {
                "path": "/product",
                "method": "POST",
                "auth_required": True,
                "description": "상품 생성 (관리자 전용)",
                "json_body": {
                    "name": "상품명 (필수)",
                    "description": "설명 (필수)",
                    "category": "카테고리 (필수)",
                    "price": "가격 (선택)",
                },
            },
            {
                "path": "/product/<product_id>",
                "method": "GET",
                "auth_required": False,
                "description": "특정 상품 상세 조회",
            },
            {
                "path": "/product/<product_id>",
                "method": "PUT",
                "auth_required": True,
                "description": "상품 수정 (관리자 전용)",
            },
            {
                "path": "/product/<product_id>",
                "method": "DELETE",
                "auth_required": True,
                "description": "상품 삭제 (소프트 삭제, 관리자 전용)",
            },
            {
                "path": "/product/categories",
                "method": "GET",
                "auth_required": False,
                "description": "카테고리 목록 및 상품 수 조회",
            },
            {
                "path": "/product/search",
                "method": "GET",
                "auth_required": False,
                "description": "상품 검색 (GET /product와 동일)",
            },
            {
                "path": "/product/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
            # 메타데이터 기반 조회
            {
                "path": "/product/brands",
                "method": "GET",
                "auth_required": False,
                "description": "모든 브랜드 목록 및 상품 수 조회",
            },
            {
                "path": "/product/brand/<brand_id>",
                "method": "GET",
                "auth_required": False,
                "description": "브랜드 ID로 상품 목록 조회",
                "query_params": {
                    "page": "페이지 번호",
                    "per_page": "페이지당 개수",
                    "sort": "정렬",
                },
            },
            {
                "path": "/product/brand/slug/<slug>",
                "method": "GET",
                "auth_required": False,
                "description": "브랜드 슬러그로 상품 목록 조회",
            },
            {
                "path": "/product/sellers",
                "method": "GET",
                "auth_required": False,
                "description": "모든 판매자 목록 및 상품 수 조회",
            },
            {
                "path": "/product/seller/<seller_id>",
                "method": "GET",
                "auth_required": False,
                "description": "판매자 ID로 상품 목록 조회",
            },
            {
                "path": "/product/seller/slug/<slug>",
                "method": "GET",
                "auth_required": False,
                "description": "판매자 슬러그로 상품 목록 조회",
            },
            {
                "path": "/product/malls",
                "method": "GET",
                "auth_required": False,
                "description": "모든 몰 목록 및 상품 수 조회",
            },
            {
                "path": "/product/mall/<mall_id>",
                "method": "GET",
                "auth_required": False,
                "description": "몰 ID로 상품 목록 조회",
            },
            {
                "path": "/product/mall/slug/<slug>",
                "method": "GET",
                "auth_required": False,
                "description": "몰 슬러그로 상품 목록 조회",
            },
        ],
    }
    return jsonify(info), 200


@bp.get("")
def get_products():
    """Return a paginated, filtered, and sorted list of products.

    Args (query string):
        category: Category filter (e.g., ``fishing``, ``motorcycle``, ``car``,
            ``bicycle``, ``camping``).
        search: Keyword searched against name, description, brand, and model number.
        min_price: Minimum price filter.
        max_price: Maximum price filter.
        sort: Sort order — ``price_asc``, ``price_desc``, ``rating_desc``,
            ``name_asc``, or ``created_desc`` (default).
        page: Page number (default 1).
        per_page: Items per page (default 20, max 100).
        is_active: Include only active products when ``true`` (default ``true``).

    Returns:
        JSON with ``items`` list and pagination metadata, HTTP 200.
        HTTP 500 on unexpected error.
    """
    try:
        # 쿼리 파라미터 추출
        category = request.args.get("category")
        search = request.args.get("search")
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        sort = request.args.get("sort", "created_desc")
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 100)
        is_active = request.args.get("is_active", "true").lower() == "true"

        # 기본 쿼리
        query = Product.query

        # 활성 상태 필터
        if is_active:
            query = query.filter(Product.is_active == True)

        # 카테고리 필터
        if category:
            query = query.filter(Product.category == category)

        # 검색어 필터
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Product.name.like(search_pattern),
                    Product.description.like(search_pattern),
                    Product.brand.like(search_pattern),
                    Product.model_number.like(search_pattern),
                )
            )

        # 가격 범위 필터
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        # 정렬
        if sort == "price_asc":
            query = query.order_by(Product.price.asc())
        elif sort == "price_desc":
            query = query.order_by(Product.price.desc())
        elif sort == "rating_desc":
            query = query.order_by(Product.rating.desc().nullslast())
        elif sort == "name_asc":
            query = query.order_by(Product.name.asc())
        else:  # created_desc (기본)
            query = query.order_by(Product.created_at.desc())

        # 페이지네이션
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # 결과 직렬화
        products = []
        for product in pagination.items:
            # 상품이미지 가져오기
            images = get_product_images(product.product_id)

            product_data = {
                "product_id": product.product_id,
                "uuid": product.uuid,
                "code": product.code,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "price": float(product.price),
                "original_price": (
                    float(product.original_price) if product.original_price else None
                ),
                "discount_percentage": product.discount_percentage,
                "currency": product.currency,
                "brand": product.brand,
                "seller_name":product.seller_name,
                "mall_name":product.mall_name,
                "seller_meta": _serialize_metadata(product.seller_entity),
                "mall_meta": _serialize_metadata(product.mall_entity),
                "brand_meta": _serialize_metadata(product.brand_entity),
                "rating": float(product.rating) if product.rating else None,
                "n_reviews": product.n_reviews,
                "stock": product.stock,
                "out_of_stock_alert": product.out_of_stock_alert,
                "rocket_delivery": product.rocket_delivery,
                "is_active": product.is_active,
                "created_at": (
                    product.created_at.isoformat() if product.created_at else None
                ),
                "product_img": images[0] if images else None,
                "product_detail_img": (images[1:] if len(images) > 1 else []),
            }
            products.append(product_data)
        
        return (
            jsonify(
                {
                    "items": products,
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"message": f"상품 목록 조회 실패: {str(e)}"}), 500


@bp.post("")
@jwt_required()
def create_product():
    """Create a new Product (admin only).

    Expects a JSON body with ``code``, ``name``, ``category``, and ``price``
    (all required) plus optional fields for description, pricing, stock,
    seller/mall/brand metadata, and product URL.

    Returns:
        JSON with the new product's ``product_id``, ``uuid``, ``code``, and
        ``name``, HTTP 201.
        HTTP 400 if required fields are missing.
        HTTP 403 if the caller is not an admin.
        HTTP 409 if the product code already exists.
        HTTP 500 on unexpected error.
    """
    try:
        current_user = get_current_user()

        # 관리자 권한 확인
        if not current_user or current_user.account_type != AccountType.ADMIN:
            return jsonify({"message": "관리자 권한이 필요합니다"}), 403

        data = request.get_json()

        # 필수 필드 검증
        required_fields = ["code", "name", "category", "price"]
        for field in required_fields:
            if field not in data:
                return jsonify({"message": f"{field}는 필수 항목입니다"}), 400

        # 중복 코드 확인
        if Product.query.filter_by(code=data["code"]).first():
            return jsonify({"message": "이미 존재하는 상품 코드입니다"}), 409

        # 상품 생성
        product = Product(
            code=data["code"],
            name=data["name"],
            category=data["category"],
            price=data["price"],
            description=data.get("description", ""),
            original_price=data.get("original_price"),
            discount_percentage=data.get("discount_percentage"),
            currency=data.get("currency", "원"),
            reward_points=data.get("reward_points"),
            rocket_delivery=data.get("rocket_delivery", False),
            rocket_delivery_valid_until=data.get("rocket_delivery_valid_until"),
            rocket_delivery_estimation_region=data.get(
                "rocket_delivery_estimation_region"
            ),
            arrival_eta=data.get("arrival_eta"),
            arrival_date=data.get("arrival_date"),
            stock=data.get("stock", 0),
            out_of_stock_alert=data.get("out_of_stock_alert", False),
            mall_name=data.get("mall_name"),
            mall_url=data.get("mall_url"),
            seller_name=data.get("seller_name"),
            seller_url=data.get("seller_url"),
            brand=data.get("brand"),
            model_number=data.get("model_number"),
            rating=data.get("rating"),
            n_reviews=data.get("n_reviews"),
            n_satisfied_customers=data.get("n_satisfied_customers"),
            n_repeated_customers=data.get("n_repeated_customers"),
            product_url=data.get("product_url"),
            options=data.get("options"),
            is_active=data.get("is_active", True),
        )

        _apply_metadata_updates(product, data)

        db.session.add(product)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "상품이 생성되었습니다",
                    "product": {
                        "product_id": product.product_id,
                        "uuid": product.uuid,
                        "code": product.code,
                        "name": product.name,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"상품 생성 실패: {str(e)}"}), 500


@bp.get("/<int:product_id>")
def get_product(product_id):
    """Return full details for a single product including images.

    Args:
        product_id: Integer primary key of the Product.

    Returns:
        JSON with the full product dict including images, HTTP 200.
        HTTP 404 if the product is not found.
        HTTP 500 on unexpected error.
    """
    try:
        product = Product.query.get_or_404(product_id)

        # 이미지 조회
        images = get_product_images(product.product_id)

        product_data = {
            "product_id": product.product_id,
            "uuid": product.uuid,
            "code": product.code,
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "price": float(product.price),
            "original_price": (
                float(product.original_price) if product.original_price else None
            ),
            "discount_percentage": product.discount_percentage,
            "currency": product.currency,
            "reward_points": product.reward_points,
            "rocket_delivery": product.rocket_delivery,
            "rocket_delivery_valid_until": (
                product.rocket_delivery_valid_until.isoformat()
                if product.rocket_delivery_valid_until
                else None
            ),
            "rocket_delivery_estimation_region": product.rocket_delivery_estimation_region,
            "arrival_eta": product.arrival_eta,
            "arrival_date": product.arrival_date,
            "stock": product.stock,
            "out_of_stock_alert": product.out_of_stock_alert,
            "mall_name": product.mall_name,
            "mall_url": product.mall_url,
            "seller_name": product.seller_name,
            "seller_url": product.seller_url,
            "brand": product.brand,
            "seller_meta": _serialize_metadata(product.seller_entity),
            "mall_meta": _serialize_metadata(product.mall_entity),
            "brand_meta": _serialize_metadata(product.brand_entity),
            "model_number": product.model_number,
            "rating": float(product.rating) if product.rating else None,
            "n_reviews": product.n_reviews,
            "n_satisfied_customers": product.n_satisfied_customers,
            "n_repeated_customers": product.n_repeated_customers,
            "product_url": product.product_url,
            "options": product.options,
            "is_active": product.is_active,
            "created_at": (
                product.created_at.isoformat() if product.created_at else None
            ),
            "updated_at": (
                product.updated_at.isoformat() if product.updated_at else None
            ),
            "product_img": images[0] if images else None,
            "product_detail_img": (images[1:] if len(images) > 1 else []),
        }

        return jsonify(product_data), 200

    except Exception as e:
        return jsonify({"message": f"상품 조회 실패: {str(e)}"}), 500


@bp.put("/<int:product_id>")
@jwt_required()
def update_product(product_id):
    """Partially update an existing Product (admin only).

    Applies only the fields present in the JSON body.  Decimal fields
    (``price``, ``original_price``, ``rating``) are coerced correctly.

    Args:
        product_id: Integer primary key of the Product to update.

    Returns:
        JSON with the updated product's ``product_id`` and ``name``, HTTP 200.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the product is not found.
        HTTP 500 on unexpected error.
    """
    try:
        current_user = get_current_user()

        # 관리자 권한 확인
        if not current_user or current_user.account_type != AccountType.ADMIN:
            return jsonify({"message": "관리자 권한이 필요합니다"}), 403

        product = Product.query.get_or_404(product_id)
        data = request.get_json()

        # 업데이트 가능한 필드들
        updatable_fields = [
            "name",
            "description",
            "category",
            "price",
            "original_price",
            "discount_percentage",
            "currency",
            "reward_points",
            "rocket_delivery",
            "rocket_delivery_valid_until",
            "rocket_delivery_estimation_region",
            "arrival_eta",
            "arrival_date",
            "stock",
            "out_of_stock_alert",
            "mall_name",
            "mall_url",
            "seller_name",
            "seller_url",
            "brand",
            "model_number",
            "rating",
            "n_reviews",
            "n_satisfied_customers",
            "n_repeated_customers",
            "product_url",
            "options",
            "is_active",
        ]

        # 제공된 필드만 업데이트
        for field in updatable_fields:
            if field in data:
                # Decimal 필드 처리
                if (
                    field in ["price", "original_price", "rating"]
                    and data[field] is not None
                ):
                    setattr(product, field, Decimal(str(data[field])))
                else:
                    setattr(product, field, data[field])

        _apply_metadata_updates(product, data)

        product.update()  # updated_at 갱신
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "상품이 수정되었습니다",
                    "product": {
                        "product_id": product.product_id,
                        "name": product.name,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"상품 수정 실패: {str(e)}"}), 500


@bp.delete("/<int:product_id>")
@jwt_required()
def delete_product(product_id):
    """Soft-delete a Product by setting ``is_active`` to False (admin only).

    Args:
        product_id: Integer primary key of the Product to deactivate.

    Returns:
        JSON with a confirmation message, HTTP 200.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the product is not found.
        HTTP 500 on unexpected error.
    """
    try:
        current_user = get_current_user()

        # 관리자 권한 확인
        if not current_user or current_user.account_type != AccountType.ADMIN:
            return jsonify({"message": "관리자 권한이 필요합니다"}), 403

        product = Product.query.get_or_404(product_id)

        # 소프트 삭제 (is_active = False)
        product.is_active = False
        product.update()
        db.session.commit()

        return jsonify({"message": "상품이 비활성화되었습니다"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"상품 삭제 실패: {str(e)}"}), 500


@bp.get("/categories")
def get_categories():
    """Return a list of active product categories with their product counts.

    Returns:
        JSON with a ``categories`` list of ``{category, count}`` dicts, HTTP 200.
        HTTP 500 on unexpected error.
    """
    try:
        # 카테고리별 상품 수 집계
        categories = (
            db.session.query(Product.category, db.func.count(Product.product_id))
            .filter(Product.is_active == True)
            .group_by(Product.category)
            .all()
        )

        result = [{"category": cat, "count": count} for cat, count in categories]

        return jsonify({"categories": result}), 200

    except Exception as e:
        return jsonify({"message": f"카테고리 조회 실패: {str(e)}"}), 500


@bp.get("/search")
def search_products():
    """Alias for ``get_products`` providing an explicit search endpoint.

    Accepts the same query parameters as ``GET /product``.

    Returns:
        Delegates entirely to ``get_products``; see its documentation for the
        full response contract.
    """
    return get_products()


# =============================================================================
# 메타데이터 기반 상품 조회 엔드포인트
# =============================================================================


def _get_metadata_list(entity_class, id_field, fk_field, list_key):
    """Return a paginated, filtered list of metadata entities with active product counts.

    Args:
        entity_class: SQLAlchemy model class for the metadata entity.
        id_field: Primary-key attribute name on ``entity_class``.
        fk_field: Foreign-key attribute name on the Product model that references
            the entity.
        list_key: Key name used for the result list in the returned dict.

    Args (query string):
        search: Partial name search (case-insensitive).
        min_products: Minimum active product count required (default 0).
        sort: Sort field — ``product_count`` (default), ``name``, or ``created``.
        order: ``asc`` or ``desc`` (default ``desc``).
        page: Page number (default 1).
        per_page: Items per page (default 50, max 100).

    Returns:
        A dict with the entity list under ``list_key`` and pagination metadata.
    """
    search = request.args.get("search", "").strip()
    min_products = request.args.get("min_products", 0, type=int)
    sort = request.args.get("sort", "product_count")
    order = request.args.get("order", "desc")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    # 기본 쿼리: 엔티티 + 상품 수
    query = (
        db.session.query(
            entity_class,
            db.func.count(Product.product_id).label("product_count"),
        )
        .outerjoin(
            Product,
            and_(
                getattr(Product, fk_field) == getattr(entity_class, id_field),
                Product.is_active == True,
            ),
        )
        .group_by(getattr(entity_class, id_field))
    )

    # 검색 필터
    if search:
        query = query.filter(entity_class.name.ilike(f"%{search}%"))

    # 최소 상품 수 필터 (HAVING 사용)
    if min_products > 0:
        query = query.having(db.func.count(Product.product_id) >= min_products)

    # 정렬
    if sort == "name":
        order_col = entity_class.name
    elif sort == "created":
        order_col = getattr(entity_class, id_field)  # ID가 생성 순서 반영
    else:  # product_count (기본)
        order_col = db.literal_column("product_count")

    if order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    # 전체 개수 (페이지네이션 전)
    total_query = query.with_entities(db.func.count()).scalar_subquery()

    # 페이지네이션
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()

    # 전체 개수 계산 (별도 쿼리)
    total = query.count()
    pages = (total + per_page - 1) // per_page if total > 0 else 0

    result = []
    for entity, count in items:
        entity_dict = entity.to_dict()
        entity_dict["product_count"] = count
        result.append(entity_dict)

    return {
        list_key: result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }


def _get_products_by_metadata(entity_class, entity_id_field, entity_id, slug=None):
    """Return a paginated product list filtered by a metadata entity (brand/seller/mall).

    Args:
        entity_class: SQLAlchemy model class for the metadata entity.
        entity_id_field: Attribute name shared by the entity and Product for joining.
        entity_id: Integer primary key to look up the entity, or None when using
            ``slug``.
        slug: Slug string to look up the entity instead of ``entity_id``.

    Args (query string):
        page: Page number (default 1).
        per_page: Items per page (default 20, max 100).
        sort: ``price_asc``, ``price_desc``, ``rating_desc``, ``name_asc``, or
            ``created_desc`` (default).

    Returns:
        A dict with ``entity``, ``items`` list, and pagination metadata.
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    sort = request.args.get("sort", "created_desc")

    # 엔티티 조회
    if slug:
        entity = entity_class.query.filter_by(slug=slug).first_or_404()
    else:
        entity = entity_class.query.get_or_404(entity_id)

    # 상품 쿼리
    query = Product.query.filter(
        getattr(Product, entity_id_field) == getattr(entity, entity_id_field),
        Product.is_active == True,
    )

    # 정렬
    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "rating_desc":
        query = query.order_by(Product.rating.desc().nullslast())
    elif sort == "name_asc":
        query = query.order_by(Product.name.asc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    products = []
    for product in pagination.items:
        images = get_product_images(product.product_id)
        products.append(
            {
                "product_id": product.product_id,
                "uuid": product.uuid,
                "code": product.code,
                "name": product.name,
                "description": product.description,
                "category": product.category,
                "price": float(product.price),
                "original_price": (
                    float(product.original_price) if product.original_price else None
                ),
                "discount_percentage": product.discount_percentage,
                "brand": product.brand,
                "rating": float(product.rating) if product.rating else None,
                "n_reviews": product.n_reviews,
                "rocket_delivery": product.rocket_delivery,
                "product_img": images[0] if images else None,
            }
        )

    return {
        "entity": entity.to_dict(),
        "items": products,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


# === 브랜드별 상품 ===


@bp.get("/brands")
def get_all_brands():
    """Return a paginated list of brands with active product counts.

    Args (query string):
        search: Partial brand name search.
        min_products: Minimum active product count (default 0).
        sort: ``product_count`` (default), ``name``, or ``created``.
        order: ``asc`` or ``desc`` (default ``desc``).
        page: Page number.
        per_page: Items per page (max 100).

    Returns:
        JSON with ``brands`` list and pagination metadata, HTTP 200.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_metadata_list(ProductBrand, "brand_id", "brand_id", "brands")
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"브랜드 목록 조회 실패: {str(e)}"}), 500


@bp.get("/brand/<int:brand_id>")
def get_products_by_brand_id(brand_id):
    """Return a paginated product list for a brand identified by its integer ID.

    Args:
        brand_id: Integer primary key of the ProductBrand.

    Returns:
        JSON with ``entity``, ``items`` list, and pagination metadata, HTTP 200.
        HTTP 404 if the brand is not found.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_products_by_metadata(ProductBrand, "brand_id", brand_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"브랜드별 상품 조회 실패: {str(e)}"}), 500


@bp.get("/brand/slug/<slug>")
def get_products_by_brand_slug(slug):
    """Return a paginated product list for a brand identified by its slug.

    Args:
        slug: URL slug of the ProductBrand.

    Returns:
        JSON with ``entity``, ``items`` list, and pagination metadata, HTTP 200.
        HTTP 404 if the brand is not found.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_products_by_metadata(ProductBrand, "brand_id", None, slug=slug)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"브랜드별 상품 조회 실패: {str(e)}"}), 500


# === 판매자별 상품 ===


@bp.get("/sellers")
def get_all_sellers():
    """Return a paginated list of sellers with active product counts.

    Args (query string):
        search: Partial seller name search.
        min_products: Minimum active product count (default 0).
        sort: ``product_count`` (default), ``name``, or ``created``.
        order: ``asc`` or ``desc`` (default ``desc``).
        page: Page number.
        per_page: Items per page (max 100).

    Returns:
        JSON with ``sellers`` list and pagination metadata, HTTP 200.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_metadata_list(ProductSeller, "seller_id", "seller_id", "sellers")
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"판매자 목록 조회 실패: {str(e)}"}), 500


@bp.get("/seller/<int:seller_id>")
def get_products_by_seller_id(seller_id):
    """Return a paginated product list for a seller identified by its integer ID.

    Args:
        seller_id: Integer primary key of the ProductSeller.

    Returns:
        JSON with ``entity``, ``items`` list, and pagination metadata, HTTP 200.
        HTTP 404 if the seller is not found.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_products_by_metadata(ProductSeller, "seller_id", seller_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"판매자별 상품 조회 실패: {str(e)}"}), 500


@bp.get("/seller/slug/<slug>")
def get_products_by_seller_slug(slug):
    """Return a paginated product list for a seller identified by its slug.

    Args:
        slug: URL slug of the ProductSeller.

    Returns:
        JSON with ``entity``, ``items`` list, and pagination metadata, HTTP 200.
        HTTP 404 if the seller is not found.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_products_by_metadata(ProductSeller, "seller_id", None, slug=slug)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"판매자별 상품 조회 실패: {str(e)}"}), 500


# === 몰별 상품 ===


@bp.get("/malls")
def get_all_malls():
    """Return a paginated list of malls with active product counts.

    Args (query string):
        search: Partial mall name search.
        min_products: Minimum active product count (default 0).
        sort: ``product_count`` (default), ``name``, or ``created``.
        order: ``asc`` or ``desc`` (default ``desc``).
        page: Page number.
        per_page: Items per page (max 100).

    Returns:
        JSON with ``malls`` list and pagination metadata, HTTP 200.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_metadata_list(ProductMall, "mall_id", "mall_id", "malls")
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"몰 목록 조회 실패: {str(e)}"}), 500


@bp.get("/mall/<int:mall_id>")
def get_products_by_mall_id(mall_id):
    """Return a paginated product list for a mall identified by its integer ID.

    Args:
        mall_id: Integer primary key of the ProductMall.

    Returns:
        JSON with ``entity``, ``items`` list, and pagination metadata, HTTP 200.
        HTTP 404 if the mall is not found.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_products_by_metadata(ProductMall, "mall_id", mall_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"몰별 상품 조회 실패: {str(e)}"}), 500


@bp.get("/mall/slug/<slug>")
def get_products_by_mall_slug(slug):
    """Return a paginated product list for a mall identified by its slug.

    Args:
        slug: URL slug of the ProductMall.

    Returns:
        JSON with ``entity``, ``items`` list, and pagination metadata, HTTP 200.
        HTTP 404 if the mall is not found.
        HTTP 500 on unexpected error.
    """
    try:
        result = _get_products_by_metadata(ProductMall, "mall_id", None, slug=slug)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": f"몰별 상품 조회 실패: {str(e)}"}), 500
