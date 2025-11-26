"""
상품 메타데이터 마이그레이션 스크립트

기존 products 테이블의 mall_name, seller_name, brand 문자열 값을
메타데이터 테이블(product_malls, product_sellers, product_brands)로 마이그레이션하고
FK 연결을 수행합니다.
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
    print("상품 메타데이터 마이그레이션 시작")
    print("=" * 60)

    # 1. 기존 문자열 데이터 수집
    result = db.session.execute(
        text(
            """
        SELECT DISTINCT mall_name FROM products 
        WHERE mall_name IS NOT NULL AND mall_name != ''
    """
        )
    )
    mall_names = [row[0] for row in result]

    result = db.session.execute(
        text(
            """
        SELECT DISTINCT seller_name FROM products 
        WHERE seller_name IS NOT NULL AND seller_name != ''
    """
        )
    )
    seller_names = [row[0] for row in result]

    result = db.session.execute(
        text(
            """
        SELECT DISTINCT brand FROM products 
        WHERE brand IS NOT NULL AND brand != ''
    """
        )
    )
    brand_names = [row[0] for row in result]

    print(f"\n[마이그레이션 대상]")
    print(f"  몰: {len(mall_names)}개")
    print(f"  판매자: {len(seller_names)}개")
    print(f"  브랜드: {len(brand_names)}개")

    # 2. 메타데이터 엔티티 생성
    print(f"\n[메타데이터 테이블 생성 중...]")

    mall_map = {}
    for name in mall_names:
        entity = ProductMall.get_or_create(name)
        mall_map[name] = entity.mall_id
        print(f"  + Mall: {name} -> ID {entity.mall_id}")

    seller_map = {}
    for name in seller_names:
        entity = ProductSeller.get_or_create(name)
        seller_map[name] = entity.seller_id
        print(f"  + Seller: {name} -> ID {entity.seller_id}")

    brand_map = {}
    for name in brand_names:
        entity = ProductBrand.get_or_create(name)
        brand_map[name] = entity.brand_id
        print(f"  + Brand: {name} -> ID {entity.brand_id}")

    db.session.commit()

    # 3. 상품에 FK 연결
    print(f"\n[상품 FK 연결 중...]")

    products = Product.query.all()
    updated = 0

    for product in products:
        changed = False

        # mall_name으로 원본 값 조회 (raw SQL로)
        result = db.session.execute(
            text(
                "SELECT mall_name, seller_name, brand FROM products WHERE product_id = :pid"
            ),
            {"pid": product.product_id},
        )
        row = result.fetchone()

        if row:
            raw_mall, raw_seller, raw_brand = row

            if raw_mall and raw_mall in mall_map:
                product.mall_id = mall_map[raw_mall]
                changed = True

            if raw_seller and raw_seller in seller_map:
                product.seller_id = seller_map[raw_seller]
                changed = True

            if raw_brand and raw_brand in brand_map:
                product.brand_id = brand_map[raw_brand]
                changed = True

        if changed:
            updated += 1

    db.session.commit()

    print(f"  업데이트된 상품: {updated}개")

    # 4. 검증
    print(f"\n[마이그레이션 검증]")

    no_seller_id = Product.query.filter(Product.seller_id == None).count()
    no_mall_id = Product.query.filter(Product.mall_id == None).count()
    no_brand_id = Product.query.filter(Product.brand_id == None).count()
    total = Product.query.count()

    print(f"  seller_id 연결됨: {total - no_seller_id}/{total}")
    print(f"  mall_id 연결됨: {total - no_mall_id}/{total}")
    print(f"  brand_id 연결됨: {total - no_brand_id}/{total}")

    print(f"\n[메타데이터 테이블 현황]")
    print(f"  ProductMall: {ProductMall.query.count()}개")
    print(f"  ProductSeller: {ProductSeller.query.count()}개")
    print(f"  ProductBrand: {ProductBrand.query.count()}개")

    # 5. 샘플 확인
    print(f"\n[마이그레이션 후 샘플 5개]")
    products = Product.query.limit(5).all()
    for p in products:
        print(f"  [{p.product_id}] {p.name[:25]}...")
        print(
            f"    mall_name={p.mall_name}, seller_name={p.seller_name}, brand={p.brand}"
        )
        print(
            f"    mall_id={p.mall_id}, seller_id={p.seller_id}, brand_id={p.brand_id}"
        )

    print("\n" + "=" * 60)
    print("마이그레이션 완료!")
    print("=" * 60)
