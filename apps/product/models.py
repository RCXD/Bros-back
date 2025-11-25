"""
상품 모델
"""

import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from sqlalchemy.dialects.mysql import CHAR
from apps.config.server import db


class Product(db.Model):
    """상품 모델"""

    __tablename__ = "products"

    product_id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(
        CHAR(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4())
    )
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(50), nullable=False, default="general")

    # 가격 정보
    price = db.Column(db.Numeric(10, 2), nullable=False)  # current_price
    original_price = db.Column(db.Numeric(10, 2), nullable=True)
    discount_percentage = db.Column(db.Integer, nullable=True)
    currency = db.Column(db.String(10), default="원")
    reward_points = db.Column(db.Integer, nullable=True)

    # 배송 정보
    rocket_delivery = db.Column(db.Boolean, default=False)
    rocket_delivery_valid_until = db.Column(db.Date, nullable=True)
    rocket_delivery_estimation_region = db.Column(db.String(50), nullable=True)
    arrival_eta = db.Column(db.Integer, nullable=True)  # 시간 단위
    arrival_date = db.Column(db.String(50), nullable=True)

    # 재고 정보
    stock = db.Column(db.Integer, default=0)  # remaining_stock
    out_of_stock_alert = db.Column(db.Boolean, default=False)

    # 판매자 정보
    mall_name = db.Column(db.String(100), nullable=True)
    mall_url = db.Column(db.String(500), nullable=True)
    seller_name = db.Column(db.String(100), nullable=True)
    seller_url = db.Column(db.String(500), nullable=True)

    # 상품 정보
    brand = db.Column(db.String(100), nullable=True)
    model_number = db.Column(db.String(100), nullable=True)

    # 리뷰 정보
    rating = db.Column(db.Numeric(3, 1), nullable=True)
    n_reviews = db.Column(db.Integer, nullable=True)
    n_satisfied_customers = db.Column(db.Integer, nullable=True)
    n_repeated_customers = db.Column(db.Integer, nullable=True)

    # URL
    product_url = db.Column(db.String(500), nullable=True)

    # 옵션 (JSON 형태)
    options = db.Column(db.JSON, nullable=True)

    # 상태
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __init__(self, code, name, category, price, **kwargs):
        self.uuid = str(uuid_lib.uuid4())
        self.code = code
        self.name = name
        self.category = category
        self.price = Decimal(str(price))

        # 선택적 필드들
        self.description = kwargs.get("description", "")
        self.original_price = (
            Decimal(str(kwargs.get("original_price", price)))
            if kwargs.get("original_price")
            else None
        )
        self.discount_percentage = kwargs.get("discount_percentage")
        self.currency = kwargs.get("currency", "원")
        self.reward_points = kwargs.get("reward_points")

        self.rocket_delivery = kwargs.get("rocket_delivery", False)
        self.rocket_delivery_valid_until = kwargs.get("rocket_delivery_valid_until")
        self.rocket_delivery_estimation_region = kwargs.get(
            "rocket_delivery_estimation_region"
        )
        self.arrival_eta = kwargs.get("arrival_eta")
        self.arrival_date = kwargs.get("arrival_date")

        self.stock = kwargs.get("stock", 0)
        self.out_of_stock_alert = kwargs.get("out_of_stock_alert", False)

        self.mall_name = kwargs.get("mall_name")
        self.mall_url = kwargs.get("mall_url")
        self.seller_name = kwargs.get("seller_name")
        self.seller_url = kwargs.get("seller_url")

        self.brand = kwargs.get("brand")
        self.model_number = kwargs.get("model_number")

        self.rating = (
            Decimal(str(kwargs.get("rating"))) if kwargs.get("rating") else None
        )
        self.n_reviews = kwargs.get("n_reviews")
        self.n_satisfied_customers = kwargs.get("n_satisfied_customers")
        self.n_repeated_customers = kwargs.get("n_repeated_customers")

        self.product_url = kwargs.get("product_url")
        self.options = kwargs.get("options")

        self.is_active = kwargs.get("is_active", True)

    def __repr__(self):
        return f"<Product {self.product_id}: {self.name}>"

    def update(self):
        """업데이트 시각 갱신"""
        self.updated_at = datetime.now()
