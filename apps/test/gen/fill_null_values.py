"""
product_data.json의 null 값들을 적절한 랜덤 값으로 채우는 스크립트
"""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta


def generate_arrival_date_text(hours: int) -> str:
    """arrival_eta(시간)를 기준으로 날짜 텍스트 생성"""
    days = hours // 24

    if days == 0:
        return "오늘 중"
    elif days == 1:
        return "내일"
    else:
        return f"{days}일 뒤"


def generate_brand_name(product_name: str, category: str) -> str:
    """제품명과 카테고리를 기반으로 브랜드명 생성"""

    # 제품명에서 브랜드처럼 보이는 단어 추출
    words = product_name.split()
    if words:
        # 첫 번째 단어를 브랜드로 사용
        return words[0]

    # 카테고리별 기본 브랜드명
    category_brands = {
        "fishing": ["피싱존", "낚시마트", "해양낚시", "바다낚시"],
        "motorcycle": ["모토라이프", "바이커존", "라이더스", "모터스"],
        "car": ["카라이프", "오토존", "드라이브", "카마트"],
        "bicycle": ["바이크샵", "사이클", "페달", "자전거나라"],
        "camping": ["캠핑존", "아웃도어", "캠프라이프", "야외활동"],
    }

    return random.choice(category_brands.get(category, ["브랜드A", "브랜드B"]))


def generate_mall_name() -> str:
    """쇼핑몰명 생성"""
    malls = [
        "쿠팡",
        "11번가",
        "G마켓",
        "옥션",
        "네이버쇼핑",
        "인터파크",
        "위메프",
        "티몬",
    ]
    return random.choice(malls)


def generate_seller_name(product_name: str) -> str:
    """판매자명 생성"""
    prefixes = ["", "공식", "정품", "프리미엄"]
    suffixes = ["스토어", "샵", "마켓", "몰", "상사", "무역"]

    prefix = random.choice(prefixes)
    words = product_name.split()
    base = words[0] if words else "셀러"
    suffix = random.choice(suffixes)

    return f"{prefix}{base}{suffix}".strip()


def generate_model_number(code: str) -> str:
    """제품 코드를 기반으로 모델번호 생성"""
    # code 예시: FISH-20251124-000
    parts = code.split("-")
    if len(parts) >= 3:
        category_prefix = parts[0][:2].upper()  # FI, MO, CA, BI, CA
        date_part = parts[1][-4:]  # 1124
        serial = parts[2]  # 000

        return f"{category_prefix}-{date_part}-{serial}-{random.randint(1000, 9999)}"

    return f"MODEL-{random.randint(10000, 99999)}"


def generate_price_variation(base_price: float) -> int:
    """가격 변동률 생성: -30% ~ +80%, 평균 20%, 분산 10%, 1000원 단위"""
    # 정규분포로 생성 (평균 20%, 표준편차 10%)
    percentage = random.gauss(20, 10)

    # -30% ~ +80% 범위로 제한
    percentage = max(-30, min(80, percentage))

    # 가격 변동 계산
    variation = base_price * (percentage / 100)

    # 1000원 단위로 반올림
    variation = round(variation / 1000) * 1000

    return int(variation)


def generate_product_options(
    product_name: str, category: str, base_price: float
) -> list:
    """제품명과 카테고리를 기반으로 적절한 옵션 생성 (가격 변동 포함)"""
    options = []

    # 색상 옵션 (대부분의 제품에 적용)
    if random.random() > 0.3:  # 70% 확률로 색상 옵션 추가
        color_pool = [
            "블랙",
            "화이트",
            "레드",
            "블루",
            "그린",
            "오렌지",
            "옐로우",
            "핑크",
            "그레이",
            "네이비",
        ]
        num_colors = random.randint(2, 5)
        selected_colors = random.sample(color_pool, num_colors)

        # 각 색상에 가격 변동 추가
        color_options = []
        for color in selected_colors:
            price_variation = generate_price_variation(base_price)
            color_options.append([color, price_variation])

        options.append({"색상": color_options})

    # 카테고리별 특화 옵션
    if category == "fishing":
        # 낚시용품: 사이즈, 길이, 무게 등
        if "가방" in product_name or "통" in product_name or "케이스" in product_name:
            size_list = ["소형", "중형", "대형", "특대형"]
            selected_sizes = random.sample(size_list, random.randint(2, 3))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})
        elif "낚싯대" in product_name or "대" in product_name:
            length_list = ["1.8m", "2.1m", "2.4m", "2.7m", "3.0m"]
            selected_lengths = random.sample(length_list, random.randint(2, 4))
            length_options = [
                [length, generate_price_variation(base_price)]
                for length in selected_lengths
            ]
            options.append({"길이": length_options})
        elif "릴" in product_name:
            model_list = ["1000", "2000", "3000", "4000", "5000"]
            selected_models = random.sample(model_list, random.randint(2, 3))
            model_options = [
                [model, generate_price_variation(base_price)]
                for model in selected_models
            ]
            options.append({"모델": model_options})

    elif category == "motorcycle":
        # 오토바이: 사이즈, 타입
        if "헬멧" in product_name:
            size_list = ["S", "M", "L", "XL", "XXL"]
            selected_sizes = random.sample(size_list, random.randint(3, 4))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})
        elif "장갑" in product_name or "글러브" in product_name:
            size_list = ["S", "M", "L", "XL"]
            selected_sizes = random.sample(size_list, random.randint(2, 3))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})
        elif "자켓" in product_name or "재킷" in product_name:
            size_list = ["85", "90", "95", "100", "105"]
            selected_sizes = random.sample(size_list, random.randint(3, 4))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})

    elif category == "car":
        # 자동차: 사이즈, 수량, 타입
        if "매트" in product_name or "커버" in product_name:
            type_list = ["운전석", "조수석", "뒷좌석", "풀세트"]
            selected_types = random.sample(type_list, random.randint(2, 3))
            type_options = [
                [t, generate_price_variation(base_price)] for t in selected_types
            ]
            options.append({"구성": type_options})
        elif "오일" in product_name or "액" in product_name:
            volume_list = ["1L", "2L", "4L", "5L"]
            selected_volumes = random.sample(volume_list, random.randint(2, 3))
            volume_options = [
                [v, generate_price_variation(base_price)] for v in selected_volumes
            ]
            options.append({"용량": volume_options})
        elif "타이어" in product_name:
            size_list = ["175/70R14", "185/65R15", "195/65R15", "205/55R16"]
            selected_sizes = random.sample(size_list, random.randint(2, 3))
            size_options = [
                [s, generate_price_variation(base_price)] for s in selected_sizes
            ]
            options.append({"규격": size_options})

    elif category == "bicycle":
        # 자전거: 사이즈, 타입
        if "자전거" in product_name and (
            "인치" in product_name or "산악" in product_name or "로드" in product_name
        ):
            size_list = ["24인치", "26인치", "27.5인치", "29인치"]
            selected_sizes = random.sample(size_list, random.randint(2, 3))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})
        elif "헬멧" in product_name:
            size_list = ["S(52-56cm)", "M(55-59cm)", "L(58-62cm)"]
            selected_sizes = random.sample(size_list, random.randint(2, 3))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})
        elif "의류" in product_name or "저지" in product_name or "바지" in product_name:
            size_list = ["S", "M", "L", "XL", "XXL"]
            selected_sizes = random.sample(size_list, random.randint(3, 4))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})

    elif category == "camping":
        # 캠핑: 사이즈, 인원, 타입
        if "텐트" in product_name:
            capacity_list = ["1-2인용", "2-3인용", "3-4인용", "4-5인용"]
            selected_capacities = random.sample(capacity_list, random.randint(2, 3))
            capacity_options = [
                [cap, generate_price_variation(base_price)]
                for cap in selected_capacities
            ]
            options.append({"인원": capacity_options})
        elif "침낭" in product_name or "슬리핑백" in product_name:
            temp_list = ["-5℃", "0℃", "5℃", "10℃", "15℃"]
            selected_temps = random.sample(temp_list, random.randint(2, 3))
            temp_options = [
                [temp, generate_price_variation(base_price)] for temp in selected_temps
            ]
            options.append({"온도": temp_options})
        elif "테이블" in product_name or "의자" in product_name:
            size_list = ["소형", "중형", "대형"]
            selected_sizes = random.sample(size_list, random.randint(2, 3))
            size_options = [
                [size, generate_price_variation(base_price)] for size in selected_sizes
            ]
            options.append({"사이즈": size_options})

    # 옵션이 없으면 최소한 색상이라도 추가
    if not options:
        color_list = ["블랙", "화이트", "레드", "블루"]
        selected_colors = random.sample(color_list, random.randint(2, 3))
        color_options = [
            [color, generate_price_variation(base_price)] for color in selected_colors
        ]
        options.append({"색상": color_options})

    return options


def fill_null_values(json_path: str):
    """product_data.json의 null 값들을 채움"""

    # JSON 파일 로드
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_products = 0
    filled_counts = {
        "rating": 0,
        "original_price": 0,
        "discount_percentage": 0,
        "rocket_delivery_valid_until": 0,
        "rocket_delivery_estimation_region": 0,
        "arrival_eta": 0,
        "arrival_date": 0,
        "remaining_stock": 0,
        "mall_name": 0,
        "seller_name": 0,
        "brand": 0,
        "model_number": 0,
        "n_satisfied_customers": 0,
        "n_repeated_customers": 0,
        "reward_points": 0,
        "options": 0,
    }

    today = datetime.now()

    # 각 카테고리 처리
    for category, category_data in data.items():
        if not isinstance(category_data, dict) or "items" not in category_data:
            continue

        print(f"\n[{category}] 카테고리 처리 중...")

        for item in category_data["items"]:
            total_products += 1

            # 1. rating이 null이면 1.0~5.0 사이 랜덤값 (소수점 1자리)
            if item.get("rating") is None:
                item["rating"] = round(random.uniform(1.0, 5.0), 1)
                filled_counts["rating"] += 1

            # 2. original_price가 null이면 current_price와 동일하게 설정
            if item.get("original_price") is None:
                if item.get("current_price") is not None:
                    item["original_price"] = item["current_price"]
                    filled_counts["original_price"] += 1

            # 3. discount_percentage 계산
            current = item.get("current_price")
            original = item.get("original_price")

            if current is not None and original is not None:
                if current == original:
                    item["discount_percentage"] = 0
                else:
                    discount = round((1 - current / original) * 100)
                    item["discount_percentage"] = discount
                filled_counts["discount_percentage"] += 1

            # 4. rocket_delivery_valid_until: 1일~30일 뒤 날짜
            if item.get("rocket_delivery_valid_until") is None and item.get(
                "rocket_delivery"
            ):
                days_ahead = random.randint(1, 30)
                valid_date = today + timedelta(days=days_ahead)
                item["rocket_delivery_valid_until"] = valid_date.strftime("%Y-%m-%d")
                filled_counts["rocket_delivery_valid_until"] += 1

            # 5. arrival_eta: 12~72시간 랜덤 정수
            if item.get("arrival_eta") is None:
                item["arrival_eta"] = random.randint(12, 72)
                filled_counts["arrival_eta"] += 1

            # 6. arrival_date: arrival_eta 기준으로 날짜 텍스트
            if item.get("arrival_date") is None:
                eta = item.get("arrival_eta", 24)
                item["arrival_date"] = generate_arrival_date_text(eta)
                filled_counts["arrival_date"] += 1

            # 7. remaining_stock: out_of_stock_alert가 true면 1~49 정수
            if item.get("remaining_stock") is None:
                if item.get("out_of_stock_alert"):
                    item["remaining_stock"] = random.randint(1, 49)
                    filled_counts["remaining_stock"] += 1

            # 8. mall_name 생성
            if item.get("mall_name") is None:
                item["mall_name"] = generate_mall_name()
                filled_counts["mall_name"] += 1

            # 9. seller_name 생성
            if item.get("seller_name") is None:
                item["seller_name"] = generate_seller_name(item.get("name", ""))
                filled_counts["seller_name"] += 1

            # 10. brand 생성
            if item.get("brand") is None:
                item["brand"] = generate_brand_name(item.get("name", ""), category)
                filled_counts["brand"] += 1

            # 11. model_number 생성
            if item.get("model_number") is None:
                item["model_number"] = generate_model_number(item.get("code", ""))
                filled_counts["model_number"] += 1

            # 12. n_satisfied_customers: 1~300 정수 (평균 10)
            if item.get("n_satisfied_customers") is None:
                # 지수 분포를 사용해서 평균 10 정도로 설정
                value = int(random.expovariate(1 / 10))
                item["n_satisfied_customers"] = min(max(value, 1), 300)
                filled_counts["n_satisfied_customers"] += 1

            # 13. n_repeated_customers: 1~300 정수 (평균 10)
            if item.get("n_repeated_customers") is None:
                value = int(random.expovariate(1 / 10))
                item["n_repeated_customers"] = min(max(value, 1), 300)
                filled_counts["n_repeated_customers"] += 1

            # 14. reward_points: current_price의 5%
            if item.get("reward_points") is None:
                current = item.get("current_price")
                if current is not None:
                    item["reward_points"] = int(current * 0.05)
                    filled_counts["reward_points"] += 1

            # 15. options: 제품에 맞는 옵션 생성 (가격 변동 포함)
            if not item.get("options") or len(item.get("options", [])) == 0:
                # original_price를 기준으로 옵션 생성
                base_price = item.get("original_price") or item.get(
                    "current_price", 10000
                )
                item["options"] = generate_product_options(
                    item.get("name", ""), category, base_price
                )
                filled_counts["options"] += 1

            # 16. rocket_delivery_estimation_region: 로켓배송 지역 ("서울/경기" 또는 "전국")
            if item.get("rocket_delivery_estimation_region") is None and item.get(
                "rocket_delivery"
            ):
                item["rocket_delivery_estimation_region"] = random.choice(
                    ["서울/경기", "전국"]
                )
                filled_counts["rocket_delivery_estimation_region"] += 1

    # 결과를 JSON 파일에 저장
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("✅ 완료: null 값 채우기 완료")
    print("=" * 60)
    print(f"총 제품 수: {total_products}개")
    for field, count in filled_counts.items():
        if count > 0:
            print(f"{field}: {count}개 채움")
    print("=" * 60)


if __name__ == "__main__":
    json_path = Path(__file__).parent.parent / "json" / "product_data.json"
    print(f"JSON 파일: {json_path}")
    fill_null_values(str(json_path))
