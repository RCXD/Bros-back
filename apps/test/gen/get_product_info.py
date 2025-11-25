"""
쿠팡 제품 페이지 캡처 이미지에서 OCR을 이용해 제품 정보 추출
첫 번째 이미지는 쿠팡 제품 판매 페이지 캡처본으로 가정
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import easyocr


def extract_price(text: str) -> Optional[int]:
    """
    텍스트에서 가격 추출
    예: "12,990원" -> 12990
    """
    # 여러 가격 패턴 시도
    patterns = [
        r"([\d,]+)\s*원",  # 12,990원
        r"([\d,]+)원",  # 12,990원 (공백 없음)
        r"원\s*([\d,]+)",  # 원 12,990
        r"(\d{1,3}(?:,\d{3})+)",  # 12,990 (원 없이)
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            price_str = match.group(1).replace(",", "").replace(" ", "")
            try:
                price = int(price_str)
                # 가격이 너무 작거나 큰 경우 제외 (100원 ~ 10,000,000원)
                if 100 <= price <= 10000000:
                    return price
            except ValueError:
                continue
    return None


def extract_discount_percentage(text: str) -> Optional[int]:
    """
    할인율 추출
    예: "10%" -> 10
    """
    discount_pattern = r"(\d+)\s*%"
    match = re.search(discount_pattern, text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def extract_rating(text: str) -> Optional[float]:
    """
    별점 추출
    예: "4.5" -> 4.5, "별점 4.5" -> 4.5
    """
    # 여러 별점 패턴 시도
    patterns = [
        r"([1-5]\.\d{1,2})",  # 4.5, 4.52
        r"([1-5]\s*점\s*\d{1,2})",  # 4점5
        r"별점[:\s]*([1-5]\.\d{1,2})",  # 별점: 4.5
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                rating_str = match.group(1).replace("점", ".").replace(" ", "")
                rating = float(rating_str)
                if 1.0 <= rating <= 5.0:
                    return round(rating, 2)
            except ValueError:
                continue
    return None


def extract_review_count(text: str) -> Optional[int]:
    """
    리뷰 수 추출
    예: "(1,234)", "1,234개", "리뷰 1234" -> 1234
    """
    patterns = [
        r"\(([\d,]+)\)",  # (1,234)
        r"([\d,]+)\s*개",  # 1,234개
        r"리뷰[:\s]*([\d,]+)",  # 리뷰: 1,234
        r"([\d,]{4,})",  # 1,234 (4자리 이상)
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            num_str = match.replace(",", "")
            try:
                num = int(num_str)
                # 리뷰 수 범위 검증 (1 ~ 100만)
                if 1 <= num <= 1000000:
                    return num
            except ValueError:
                continue
    return None


def parse_coupang_screenshot(
    image_path: Path, reader: easyocr.Reader
) -> Dict[str, Any]:
    """
    쿠팡 제품 페이지 스크린샷에서 정보 추출

    Args:
        image_path: 이미지 파일 경로
        reader: EasyOCR Reader 인스턴스

    Returns:
        Dict: 추출된 제품 정보
    """
    result = {
        "current_price": None,
        "original_price": None,
        "discount_percentage": None,
        "rating": None,
        "n_reviews": None,
        "rocket_delivery": False,
    }

    try:
        # OCR 실행
        ocr_results = reader.readtext(str(image_path))

        # 모든 텍스트 수집
        all_text = " ".join([text for _, text, _ in ocr_results])

        # 로켓배송 확인
        if "로켓배송" in all_text or "로켓" in all_text or "rocket" in all_text.lower():
            result["rocket_delivery"] = True

        # 각 텍스트 라인별로 정보 추출
        prices = []
        for _, text, confidence in ocr_results:
            if confidence < 0.3:  # 낮은 신뢰도 제외 (0.5 -> 0.3으로 완화)
                continue  # 가격 추출
            price = extract_price(text)
            if price:
                prices.append(price)

            # 할인율 추출
            if result["discount_percentage"] is None:
                discount = extract_discount_percentage(text)
                if discount:
                    result["discount_percentage"] = discount

            # 별점 추출
            if result["rating"] is None:
                rating = extract_rating(text)
                if rating:
                    result["rating"] = rating

            # 리뷰 수 추출
            if result["n_reviews"] is None:
                n_reviews = extract_review_count(text)
                if n_reviews:
                    result["n_reviews"] = n_reviews

        # 가격 처리: 가장 큰 값을 original_price, 작은 값을 current_price로
        if prices:
            prices.sort()
            if len(prices) >= 2:
                result["current_price"] = prices[0]
                result["original_price"] = prices[-1]
            else:
                result["current_price"] = prices[0]

    except Exception as e:
        print(f"  ⚠️ OCR 실패: {image_path.name} - {e}")

    return result


def update_product_data_with_ocr(
    product_data_path: Path,
    extracted_images_root: Path,
    output_path: Optional[Path] = None,
) -> None:
    """
    product_data.json의 각 제품에 대해 첫 번째 이미지에서 OCR 정보 추출 및 업데이트

    Args:
        product_data_path: product_data.json 경로
        extracted_images_root: 추출된 이미지 루트 폴더 (extracted_product_images)
        output_path: 출력 JSON 경로 (None이면 product_data_path 덮어쓰기)
    """
    # EasyOCR Reader 초기화 (한국어 + 영어)
    print("EasyOCR 초기화 중...")
    reader = easyocr.Reader(["ko", "en"], gpu=True)

    # product_data.json 로드
    with open(product_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_products = sum(len(cat_data["items"]) for cat_data in data.values())
    processed = 0

    print(f"\n총 {total_products}개 제품의 이미지 분석 시작...\n")

    for category, cat_data in data.items():
        print(f"[{category}] 카테고리 처리 중...")
        category_dir = extracted_images_root / category

        for product in cat_data["items"]:
            product_code = product["code"]

            # 첫 번째 이미지 경로 찾기
            first_image_pattern = f"{product_code}_1.*"
            first_images = list(category_dir.glob(first_image_pattern))

            if not first_images:
                print(f"  ⚠️ {product_code}: 첫 번째 이미지 없음")
                processed += 1
                continue

            first_image_path = first_images[0]

            # OCR 정보 추출
            ocr_info = parse_coupang_screenshot(first_image_path, reader)

            # product_data 업데이트
            product.update(ocr_info)

            processed += 1
            print(
                f"  ✓ {product_code} ({processed}/{total_products}): "
                f"가격={ocr_info.get('current_price')}, "
                f"별점={ocr_info.get('rating')}, "
                f"리뷰={ocr_info.get('n_reviews')}"
            )

    # 업데이트된 데이터 저장
    output_file = output_path or product_data_path
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료: {output_file}")
    print(f"   총 {total_products}개 제품 정보 업데이트")


def verify_extracted_info(product_data_path: Path) -> None:
    """
    추출된 정보 검증 및 통계 출력
    """
    with open(product_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = {
        "total": 0,
        "has_price": 0,
        "has_discount": 0,
        "has_rating": 0,
        "has_reviews": 0,
        "has_rocket": 0,
    }

    print("\n" + "=" * 60)
    print("추출 정보 검증")
    print("=" * 60)

    for category, cat_data in data.items():
        print(f"\n[{category}] 카테고리:")
        for product in cat_data["items"]:
            stats["total"] += 1
            if product.get("current_price"):
                stats["has_price"] += 1
            if product.get("discount_percentage"):
                stats["has_discount"] += 1
            if product.get("rating"):
                stats["has_rating"] += 1
            if product.get("n_reviews"):
                stats["has_reviews"] += 1
            if product.get("rocket_delivery"):
                stats["has_rocket"] += 1

            # 샘플 출력 (각 카테고리 첫 3개)
            if product["id"] < 3:
                print(
                    f"  {product['code']}: "
                    f"가격={product.get('current_price')}, "
                    f"할인={product.get('discount_percentage')}%, "
                    f"별점={product.get('rating')}, "
                    f"리뷰={product.get('n_reviews')}, "
                    f"로켓={'O' if product.get('rocket_delivery') else 'X'}"
                )

    print("\n" + "=" * 60)
    print("전체 통계:")
    print(f"  총 제품 수: {stats['total']}개")
    print(
        f"  가격 정보: {stats['has_price']}개 ({stats['has_price']/stats['total']*100:.1f}%)"
    )
    print(
        f"  할인율: {stats['has_discount']}개 ({stats['has_discount']/stats['total']*100:.1f}%)"
    )
    print(
        f"  별점: {stats['has_rating']}개 ({stats['has_rating']/stats['total']*100:.1f}%)"
    )
    print(
        f"  리뷰 수: {stats['has_reviews']}개 ({stats['has_reviews']/stats['total']*100:.1f}%)"
    )
    print(
        f"  로켓배송: {stats['has_rocket']}개 ({stats['has_rocket']/stats['total']*100:.1f}%)"
    )
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="쿠팡 제품 페이지 캡처 이미지에서 OCR로 정보 추출"
    )
    parser.add_argument(
        "--product-json",
        type=Path,
        default=Path("apps/test/json/product_data.json"),
        help="product_data.json 경로",
    )
    parser.add_argument(
        "--images-root",
        type=Path,
        default=Path("apps/static/extracted_product_images"),
        help="추출된 이미지 루트 폴더",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="출력 JSON 경로 (지정 안 하면 원본 덮어쓰기)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="OCR 실행 없이 기존 데이터 검증만 수행",
    )

    args = parser.parse_args()

    if args.verify_only:
        verify_extracted_info(args.product_json)
    else:
        update_product_data_with_ocr(args.product_json, args.images_root, args.output)
        verify_extracted_info(args.output or args.product_json)
