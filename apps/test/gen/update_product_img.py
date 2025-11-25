"""
product_data.json에서 모든 product_img 필드의 _1을 _0으로 변경
"""

import json

json_path = "apps/test/json/product_data.json"

# JSON 파일 읽기
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 모든 카테고리의 제품 순회하며 product_img 수정
total_updated = 0
for category_name, category_data in data.items():
    if "items" in category_data:
        for item in category_data["items"]:
            if "product_img" in item and item["product_img"]:
                old_value = item["product_img"]
                if "_1" in old_value:
                    item["product_img"] = old_value.replace("_1", "_0")
                    total_updated += 1
                    print(f"✓ {old_value} → {item['product_img']}")

# 수정된 내용을 파일에 저장
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n총 {total_updated}개의 product_img 업데이트 완료")
