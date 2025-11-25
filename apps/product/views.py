"""
Product module - Product management and queries
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_current_user
from sqlalchemy import or_, and_
from decimal import Decimal

from apps.config.server import db
from apps.product.models import Product
from apps.image.models import Image
from apps.favorite.models import Favorite, FavoriteType
from apps.auth.models import User, AccountType

bp = Blueprint("product", __name__)


@bp.get("/api_info")
def api_info():
    """
    상품 API 정보 제공 (개발용)
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
        ],
    }
    return jsonify(info), 200


@bp.get("")
def get_products():
    """
    상품 목록 조회
    Query params:
        - category: 카테고리 필터 (fishing, motorcycle, car, bicycle, camping)
        - search: 검색어 (상품명, 설명, 브랜드 검색)
        - min_price: 최소 가격
        - max_price: 최대 가격
        - sort: 정렬 (price_asc, price_desc, rating_desc, created_desc, name_asc)
        - page: 페이지 번호 (기본: 1)
        - per_page: 페이지당 개수 (기본: 20, 최대: 100)
        - is_active: 활성 상태 필터 (기본: true)
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
                "rating": float(product.rating) if product.rating else None,
                "n_reviews": product.n_reviews,
                "stock": product.stock,
                "out_of_stock_alert": product.out_of_stock_alert,
                "rocket_delivery": product.rocket_delivery,
                "is_active": product.is_active,
                "created_at": (
                    product.created_at.isoformat() if product.created_at else None
                ),
            }
            products.append(product_data)

        return (
            jsonify(
                {
                    "items": products,
                    "pagination": {
                        "page": pagination.page,
                        "per_page": pagination.per_page,
                        "total": pagination.total,
                        "pages": pagination.pages,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"message": f"상품 목록 조회 실패: {str(e)}"}), 500


@bp.post("")
@jwt_required()
def create_product():
    """
    상품 생성 (관리자 전용)
    JSON body:
        - code: 필수 - 상품 코드 (고유)
        - name: 필수 - 상품명
        - category: 필수 - 카테고리
        - price: 필수 - 가격
        - description: 선택 - 설명
        - original_price: 선택 - 원래 가격
        - discount_percentage: 선택 - 할인율
        - stock: 선택 - 재고
        - brand: 선택 - 브랜드
        - options: 선택 - 옵션 (JSON)
        ... (기타 Product 모델 필드)
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
    """
    특정 상품 상세 조회
    """
    try:
        product = Product.query.get_or_404(product_id)

        # 이미지 조회 (product_img 필드에서 UUID 추출)
        # 예: "FISH-20251124-000_0" -> apps/static/extracted_product_images/FISH-20251124-000_0.png
        product_image_uuid = None
        if hasattr(product, "product_img"):
            # product_img가 있다면 해당 정보 포함
            product_image_uuid = product.product_img

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
        }

        return jsonify(product_data), 200

    except Exception as e:
        return jsonify({"message": f"상품 조회 실패: {str(e)}"}), 500


@bp.put("/<int:product_id>")
@jwt_required()
def update_product(product_id):
    """
    상품 수정 (관리자 전용)
    JSON body: Product 모델의 모든 필드 (선택적)
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
    """
    상품 삭제 (관리자 전용)
    실제로는 is_active를 False로 변경 (소프트 삭제)
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
    """
    상품 카테고리 목록 조회 및 카테고리별 상품 수
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
    """
    상품 검색 (get_products와 동일한 기능이지만 명시적인 검색 엔드포인트)
    Query params: get_products와 동일
    """
    return get_products()
