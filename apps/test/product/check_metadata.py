"""
상품 메타데이터 상태 확인 및 마이그레이션 스크립트
"""

import sys

sys.path.insert(0, "c:/Users/M/Bros-back-clone2")

from apps.app import create_app
from apps.config.server import db
from apps.product.models import Product, ProductSeller, ProductMall, ProductBrand
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("=" * 60)
    print("상품 메타데이터 상태 확인")
    print("=" * 60)

    # 1. 기본 현황
    total = Product.query.count()
    print(f"\n전체 상품 수: {total}")

    # 2. FK 컬럼 상태
    no_seller_id = Product.query.filter(Product.seller_id == None).count()
    no_mall_id = Product.query.filter(Product.mall_id == None).count()
    no_brand_id = Product.query.filter(Product.brand_id == None).count()

    print(f"\n[FK 컬럼 상태]")
    print(f"  seller_id NULL: {no_seller_id}/{total}")
    print(f"  mall_id NULL: {no_mall_id}/{total}")
    print(f"  brand_id NULL: {no_brand_id}/{total}")

    # 3. 메타데이터 테이블 현황
    print(f"\n[메타데이터 테이블]")
    print(f"  ProductSeller: {ProductSeller.query.count()}개")
    print(f"  ProductMall: {ProductMall.query.count()}개")
    print(f"  ProductBrand: {ProductBrand.query.count()}개")

    # 4. 기존 문자열 컬럼 데이터 확인
    result = db.session.execute(
        text(
            "SELECT COUNT(*) FROM products WHERE mall_name IS NOT NULL AND mall_name != ''"
        )
    )
    mall_count = result.scalar()

    result = db.session.execute(
        text(
            "SELECT COUNT(*) FROM products WHERE seller_name IS NOT NULL AND seller_name != ''"
        )
    )
    seller_count = result.scalar()

    result = db.session.execute(
        text("SELECT COUNT(*) FROM products WHERE brand IS NOT NULL AND brand != ''")
    )
    brand_count = result.scalar()

    print(f"\n[기존 문자열 컬럼 데이터]")
    print(f"  mall_name 값 있음: {mall_count}개")
    print(f"  seller_name 값 있음: {seller_count}개")
    print(f"  brand 값 있음: {brand_count}개")

    # 5. 샘플 데이터
    print(f"\n[샘플 상품 5개]")
    result = db.session.execute(
        text(
            "SELECT product_id, name, mall_name, seller_name, brand FROM products LIMIT 5"
        )
    )
    for row in result:
        print(f"  [{row[0]}] {row[1][:25]}...")
        print(f"    mall={row[2]}, seller={row[3]}, brand={row[4]}")

    print("\n" + "=" * 60)
