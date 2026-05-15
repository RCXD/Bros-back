"""
상품 모델
"""

import re
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.dialects.mysql import CHAR

from apps.config.server import db


def _slugify_value(value: str) -> str:
    """Convert a string into a URL-friendly slug.

    Args:
        value: The raw string to slugify.

    Returns:
        A lowercase, hyphen-separated slug derived from ``value``.
        Falls back to ``"meta"`` if the result would be empty.
    """
    cleaned = re.sub(r"[^\w]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-")
    return cleaned or "meta"


class ProductMetadataMixin:
    """Abstract mixin providing shared name/slug/logo behaviour for product metadata models."""

    __abstract__ = True

    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    logo_filename = db.Column(db.String(255), nullable=True)
    id_field = None

    @classmethod
    def _build_unique_slug(cls, base: str) -> str:
        """Generate a slug that does not already exist in the database.

        Args:
            base: The initial candidate slug string.

        Returns:
            A unique slug derived from ``base``, appending a numeric suffix
            (``-2``, ``-3``, …) when collisions are detected.
        """
        suffix = 1
        while cls.query.filter_by(slug=candidate).first():
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    @classmethod
    def get_or_create(cls, name: str, logo_filename: str = None):
        """Fetch an existing metadata entry by name, or create one if absent.

        Args:
            name: The display name to look up or create (case-insensitive match).
            logo_filename: Optional explicit logo file name. Defaults to
                ``<slug>.png`` when omitted.

        Returns:
            The existing or newly created model instance, or ``None`` if
            ``name`` is falsy.
        """
        if not name:
            return None
        normalized = name.strip()
        existing = cls.query.filter(func.lower(cls.name) == normalized.lower()).first()
        if existing:
            return existing
        base_slug = _slugify_value(normalized)
        slug = cls._build_unique_slug(base_slug)
        logo = logo_filename or f"{slug}.png"
        entry = cls(name=normalized, slug=slug, logo_filename=logo)
        db.session.add(entry)
        db.session.flush()
        return entry

    def to_dict(self):
        """Serialize the metadata entry to a JSON-compatible dictionary.

        Returns:
            A dictionary with ``id``, ``name``, ``slug``, and ``logo_url`` keys.

        Raises:
            NotImplementedError: If ``id_field`` is not defined on the subclass.
        """
        if not self.id_field:
            raise NotImplementedError("id_field must be defined on metadata subclasses")
        return {
            "id": getattr(self, self.id_field),
            "name": self.name,
            "slug": self.slug,
            "logo_url": self.logo_url,
        }

    @property
    def logo_url(self):
        """Return the URL path for this entry's logo image."""
        filename = self.logo_filename or f"{self.slug}.png"
        return f"/static/logo_images/{filename}"

    def __repr__(self):
        """Return a developer-readable representation of the metadata entry."""
        return f"<{self.__class__.__name__} {self.name}>"


class ProductSeller(ProductMetadataMixin, db.Model):
    """SQLAlchemy model representing a product seller/vendor entity."""

    __tablename__ = "product_sellers"
    id_field = "seller_id"

    seller_id = db.Column(db.Integer, primary_key=True)
    products = db.relationship("Product", back_populates="seller_entity")


class ProductMall(ProductMetadataMixin, db.Model):
    """SQLAlchemy model representing an online shopping mall entity."""

    __tablename__ = "product_malls"
    id_field = "mall_id"

    mall_id = db.Column(db.Integer, primary_key=True)
    products = db.relationship("Product", back_populates="mall_entity")


class ProductBrand(ProductMetadataMixin, db.Model):
    """SQLAlchemy model representing a product brand entity."""

    __tablename__ = "product_brands"
    id_field = "brand_id"

    brand_id = db.Column(db.Integer, primary_key=True)
    products = db.relationship("Product", back_populates="brand_entity")


class Product(db.Model):
    """SQLAlchemy model representing a purchasable product."""

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

    # 판매자/몰/브랜드 참조
    seller_id = db.Column(
        db.Integer, db.ForeignKey("product_sellers.seller_id"), nullable=True
    )
    mall_id = db.Column(db.Integer, db.ForeignKey("product_malls.mall_id"), nullable=True)
    brand_id = db.Column(
        db.Integer, db.ForeignKey("product_brands.brand_id"), nullable=True
    )

    seller_entity = db.relationship(
        "ProductSeller",
        back_populates="products",
        lazy="joined",
        foreign_keys=[seller_id],
    )
    mall_entity = db.relationship(
        "ProductMall",
        back_populates="products",
        lazy="joined",
        foreign_keys=[mall_id],
    )
    brand_entity = db.relationship(
        "ProductBrand",
        back_populates="products",
        lazy="joined",
        foreign_keys=[brand_id],
    )

    seller_url = db.Column(db.String(500), nullable=True)
    mall_url = db.Column(db.String(500), nullable=True)

    # 상품 정보
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
        """Initialize a Product instance with required and optional attributes.

        Args:
            code: Unique product code string.
            name: Human-readable product name.
            category: Product category string (e.g. ``"general"``).
            price: Current selling price; converted to ``Decimal`` internally.
            **kwargs: Optional product attributes including ``description``,
                ``original_price``, ``discount_percentage``, ``currency``,
                ``reward_points``, ``rocket_delivery``, ``stock``,
                ``seller_entity``/``seller_name``, ``mall_entity``/``mall_name``,
                ``brand_entity``/``brand``, ``mall_url``, ``seller_url``,
                ``model_number``, ``rating``, ``n_reviews``,
                ``n_satisfied_customers``, ``n_repeated_customers``,
                ``product_url``, ``options``, and ``is_active``.
        """
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

        # 메타 엔티티 (seller, mall, brand)
        if "seller_entity" in kwargs and kwargs["seller_entity"] is not None:
            self.seller_entity = kwargs["seller_entity"]
        else:
            self.seller_name = kwargs.get("seller_name")

        if "mall_entity" in kwargs and kwargs["mall_entity"] is not None:
            self.mall_entity = kwargs["mall_entity"]
        else:
            self.mall_name = kwargs.get("mall_name")

        if "brand_entity" in kwargs and kwargs["brand_entity"] is not None:
            self.brand_entity = kwargs["brand_entity"]
        else:
            self.brand = kwargs.get("brand")

        self.mall_url = kwargs.get("mall_url")
        self.seller_url = kwargs.get("seller_url")

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

    @property
    def seller_name(self):
        """Return the name of the associated seller, or ``None`` if unset."""
        return self.seller_entity.name if self.seller_entity else None

    @seller_name.setter
    def seller_name(self, value):
        """Set the seller by name string or ``ProductSeller`` instance."""
        if isinstance(value, ProductSeller):
            self.seller_entity = value
        elif value:
            self.seller_entity = ProductSeller.get_or_create(value)
        else:
            self.seller_entity = None

    @property
    def mall_name(self):
        """Return the name of the associated mall, or ``None`` if unset."""
        return self.mall_entity.name if self.mall_entity else None

    @mall_name.setter
    def mall_name(self, value):
        """Set the mall by name string or ``ProductMall`` instance."""
        if isinstance(value, ProductMall):
            self.mall_entity = value
        elif value:
            self.mall_entity = ProductMall.get_or_create(value)
        else:
            self.mall_entity = None

    @property
    def brand(self):
        """Return the name of the associated brand, or ``None`` if unset."""
        return self.brand_entity.name if self.brand_entity else None

    @brand.setter
    def brand(self, value):
        """Set the brand by name string or ``ProductBrand`` instance."""
        if isinstance(value, ProductBrand):
            self.brand_entity = value
        elif value:
            self.brand_entity = ProductBrand.get_or_create(value)
        else:
            self.brand_entity = None

    def __repr__(self):
        """Return a developer-readable representation of the product."""
        return f"<Product {self.product_id}: {self.name}>"

    def update(self):
        """Refresh the ``updated_at`` timestamp to the current time."""
        self.updated_at = datetime.now()
