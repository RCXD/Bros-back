"""
제품(Product) 테스트 데이터 생성
product_data.json 기반으로 제품과 이미지 생성
"""

import json
import pytest
from pathlib import Path
from apps.product.models import Product
from apps.image.models import Image
from apps.config.server import db

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


@pytest.mark.no_cleanup
def test_generate_products(fixture_app):
    """JSON 파일에서 제품 데이터 읽어서 DB에 생성"""

    log = get_logger()

    with fixture_app.app_context():
        verbosity = fixture_app.config.get("VERBOSITY", 1)

        log.info("\n[5/6] 제품 데이터 생성")

        # JSON 파일 읽기
        json_path = Path("apps/test/json/product_data.json")

        if not json_path.exists():
            log.warning("  product_data.json 파일이 없습니다. 제품 생성 건너뜀.")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            product_data = json.load(f)

        total_created = 0
        category_counts = {}

        for category_key, category_info in product_data.items():
            items = category_info.get("items", [])
            created_count = 0

            for item in items:
                try:
                    # rocket_delivery_valid_until을 date 객체로 변환
                    from datetime import datetime

                    rocket_valid = item.get("rocket_delivery_valid_until")
                    if rocket_valid and isinstance(rocket_valid, str):
                        rocket_valid = datetime.strptime(
                            rocket_valid, "%Y-%m-%d"
                        ).date()

                    # Product 객체 생성
                    product = Product(
                        code=item["code"],
                        name=item["name"],
                        category=item["category"],
                        price=item.get("current_price", 0) or 0,
                        description=item.get("description", ""),
                        stock=item.get("remaining_stock", 0) or 0,
                        is_active=True,
                        # 추가 필드들
                        original_price=item.get("original_price"),
                        discount_percentage=item.get("discount_percentage"),
                        currency=item.get("currency", "원"),
                        reward_points=item.get("reward_points"),
                        rocket_delivery=item.get("rocket_delivery", False),
                        rocket_delivery_valid_until=rocket_valid,
                        rocket_delivery_estimation_region=item.get(
                            "rocket_delivery_estimation_region"
                        ),
                        arrival_eta=item.get("arrival_eta"),
                        arrival_date=item.get("arrival_date"),
                        out_of_stock_alert=item.get("out_of_stock_alert", False),
                        mall_name=item.get("mall_name"),
                        mall_url=item.get("mall_url"),
                        seller_name=item.get("seller_name"),
                        seller_url=item.get("seller_url"),
                        brand=item.get("brand"),
                        model_number=item.get("model_number"),
                        rating=item.get("rating"),
                        n_reviews=item.get("n_reviews"),
                        n_satisfied_customers=item.get("n_satisfied_customers"),
                        n_repeated_customers=item.get("n_repeated_customers"),
                        product_url=item.get("product_url"),
                        options=item.get("options"),
                    )

                    db.session.add(product)
                    db.session.flush()  # product_id 생성

                    # 메인 이미지 추가
                    product_img = item.get("product_img")
                    if product_img:
                        # 파일 확장자 찾기
                        ext = ".jpeg"
                        for test_ext in [".jpeg", ".jpg", ".png"]:
                            test_path = Path(
                                f"apps/static/extracted_product_images/{category_key}/{product_img}{test_ext}"
                            )
                            if test_path.exists():
                                ext = test_ext
                                break

                        # 상대 경로 생성
                        relative_path = f"static/extracted_product_images/{category_key}/{product_img}{ext}"

                        main_image = Image(
                            product_id=product.product_id,
                            user_id=None,
                            post_id=None,
                            directory=relative_path,
                            original_image_name=f"{product_img}{ext}",
                            ext=ext.lstrip("."),
                            image_type="main",
                            display_order=0,
                        )
                        db.session.add(main_image)

                    # 상세 이미지 추가
                    product_detail_imgs = item.get("product_detail_img", [])
                    for idx, img_identifier in enumerate(product_detail_imgs, start=1):
                        # 파일 확장자 찾기
                        ext = ".jpeg"
                        for test_ext in [".jpeg", ".jpg", ".png"]:
                            test_path = Path(
                                f"apps/static/extracted_product_images/{category_key}/{img_identifier}{test_ext}"
                            )
                            if test_path.exists():
                                ext = test_ext
                                break

                        # 상대 경로 생성
                        relative_path = f"static/extracted_product_images/{category_key}/{img_identifier}{ext}"

                        detail_image = Image(
                            product_id=product.product_id,
                            user_id=None,
                            post_id=None,
                            directory=relative_path,
                            original_image_name=f"{img_identifier}{ext}",
                            ext=ext.lstrip("."),
                            image_type="detail",
                            display_order=idx,
                        )
                        db.session.add(detail_image)

                    created_count += 1

                    if verbosity >= 2:
                        log.debug(f"    [{category_key}] {item['name'][:30]}...")

                except Exception as e:
                    log.warning(
                        f"    ❌ 제품 생성 실패: {item.get('name', 'unknown')} - {e}"
                    )
                    db.session.rollback()
                    continue

            db.session.commit()
            total_created += created_count
            category_counts[category_key] = created_count

            if verbosity >= 1:
                log.info(f"  [{category_key}] {created_count}개 제품 생성")

        log.success(f"  총 {total_created}개 제품 생성 완료")

        if verbosity >= 1:
            for cat, count in category_counts.items():
                log.debug(f"    - {cat}: {count}개")


if __name__ == "__main__":
    print("pytest를 사용하여 실행하세요:")
    print("pytest apps/test/gen/gen_product.py -v -s")
