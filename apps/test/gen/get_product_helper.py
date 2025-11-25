"""워드 파일에서 제품 정보와 이미지를 추출하여 JSON 생성"""

import argparse
import json
import re
import uuid as uuid_lib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph


def generate_product_code(category: str, index: int) -> str:
    """
    제품 코드 생성: <CATEGORY_PREFIX>-<YYYYMMDD>-<INDEX>
    예: FISH-20251124-001
    """
    from datetime import datetime

    prefix_map = {
        "fishing": "FISH",
        "motorcycle": "MOTO",
        "car": "CAR",
        "bicycle": "BIKE",
        "camping": "CAMP",
    }

    prefix = prefix_map.get(category, "PROD")
    date_str = datetime.now().strftime("%Y%m%d")
    return f"{prefix}-{date_str}-{index:03d}"


@dataclass
class ProductOption:
    option_name: str
    option_values: List[str]


@dataclass
class Product:
    id: int
    uuid: str
    code: str
    name: str
    category: str
    current_price: Optional[int] = None
    currency: str = "원"
    original_price: Optional[int] = None
    discount_percentage: Optional[int] = None
    rocket_delivery: bool = False
    rocket_delivery_valid_until: Optional[str] = None
    rocket_delivery_estimation_region: Optional[str] = None
    arrival_eta: Optional[str] = None
    arrival_date: Optional[str] = None
    out_of_stock_alert: bool = False
    remaining_stock: Optional[int] = None
    mall_name: Optional[str] = None
    mall_url: Optional[str] = None
    seller_name: Optional[str] = None
    seller_url: Optional[str] = None
    brand: Optional[str] = None
    model_number: Optional[str] = None
    rating: Optional[float] = None
    n_reviews: Optional[int] = None
    n_satisfied_customers: Optional[int] = None
    n_repeated_customers: Optional[int] = None
    product_img: Optional[str] = None  # 메인 이미지 UUID
    product_detail_img: List[str] = None  # 상세 이미지 UUID 리스트
    product_url: Optional[str] = None
    reward_points: Optional[int] = None
    options: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.product_detail_img is None:
            self.product_detail_img = []
        if self.options is None:
            self.options = []


def extract_images_from_docx(
    doc_path: Path, output_dir: Path, product_code: str
) -> List[str]:
    """
    워드 파일에서 이미지를 추출하여 output_dir에 저장하고 UUID 리스트 반환

    Args:
        doc_path: 워드 파일 경로
        output_dir: 이미지 저장 폴더
        product_code: 제품 코드 (파일명 prefix로 사용)

    Returns:
        List[str]: 저장된 이미지들의 UUID 리스트
    """
    doc = Document(doc_path)
    image_uuids = []

    # 이미지 추출
    rels = doc.part.rels
    image_counter = 1

    for rel_id, rel in rels.items():
        if "image" in rel.target_ref:
            try:
                image_data = rel.target_part.blob
                # 확장자 추출
                ext = Path(rel.target_ref).suffix
                if not ext:
                    ext = ".png"  # 기본값

                # 파일명 생성 (상품코드 포함) - 파일명 자체가 식별자 역할
                image_filename = f"{product_code}_{image_counter}{ext}"
                image_path = output_dir / image_filename

                # 이미지 저장
                output_dir.mkdir(parents=True, exist_ok=True)
                with open(image_path, "wb") as f:
                    f.write(image_data)

                # 파일명(확장자 제외)을 식별자로 사용
                image_identifier = f"{product_code}_{image_counter}"
                image_uuids.append(image_identifier)
                image_counter += 1

            except Exception as e:
                print(f"이미지 추출 실패 ({rel.target_ref}): {e}")
                continue

    return image_uuids


def extract_product_name_from_filename(filename: str) -> str:
    """파일명에서 제품명 추출 (.docx 제거)"""
    return filename.replace(".docx", "").strip()


def parse_price(text: str) -> Optional[int]:
    """텍스트에서 가격 추출"""
    # 숫자와 쉼표만 남기고 제거
    cleaned = re.sub(r"[^\d,]", "", text)
    cleaned = cleaned.replace(",", "")
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def extract_text_from_docx(doc_path: Path) -> str:
    """워드 문서의 모든 텍스트 추출"""
    doc = Document(doc_path)
    full_text = []

    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    full_text.append(cell.text.strip())

    return "\n".join(full_text)


def create_product_from_docx(
    doc_path: Path, output_image_dir: Path, category: str, product_id: int
) -> Product:
    """
    워드 파일에서 Product 객체 생성

    Args:
        doc_path: 워드 파일 경로
        output_image_dir: 이미지 저장 폴더
        category: 카테고리 (영문)
        product_id: 제품 ID (0부터 증가)

    Returns:
        Product: 제품 객체
    """
    # UUID 및 코드 생성
    product_uuid = str(uuid_lib.uuid4())
    product_code = generate_product_code(category, product_id)

    # 제품명: 파일명에서 추출
    product_name = extract_product_name_from_filename(doc_path.name)

    # 이미지 추출 (UUID 기반)
    image_uuids = extract_images_from_docx(doc_path, output_image_dir, product_code)

    # 텍스트 추출 (향후 가격, 옵션 등 파싱에 사용 가능)
    text_content = extract_text_from_docx(doc_path)

    # Product 객체 생성
    product = Product(
        id=product_id,
        uuid=product_uuid,
        code=product_code,
        name=product_name,
        category=category,
        product_img=image_uuids[0] if image_uuids else None,
        product_detail_img=image_uuids[1:] if len(image_uuids) > 1 else [],
    )

    return product


def process_category_folder(
    category_path: Path, output_image_dir: Path, category_key: str
) -> List[Product]:
    """
    카테고리 폴더 내 모든 워드 파일 처리

    Args:
        category_path: 카테고리 폴더 경로
        output_image_dir: 이미지 저장 루트 폴더
        category_key: 카테고리 영문 키 (fishing, camping 등)

    Returns:
        List[Product]: 제품 리스트
    """
    products = []

    if not category_path.exists():
        print(f"경로를 찾을 수 없습니다: {category_path}")
        return products

    docx_files = list(category_path.glob("*.docx"))
    print(f"\n{category_key} 카테고리: {len(docx_files)}개 파일 발견")

    # extracted_product_images/<category> 폴더에 저장
    category_output_dir = output_image_dir / category_key

    for idx, doc_file in enumerate(docx_files):
        if doc_file.name.startswith("~$"):  # 임시 파일 제외
            continue

        try:
            print(f"  처리 중: {doc_file.name}")
            product = create_product_from_docx(
                doc_file, category_output_dir, category=category_key, product_id=idx
            )
            products.append(product)
        except Exception as e:
            print(f"  ❌ 실패: {doc_file.name} - {e}")
            continue

    return products


def generate_product_json(
    source_root: Path,
    output_json: Path,
    output_image_dir: Path,
    categories: Optional[List[str]] = None,
) -> None:
    """모든 카테고리 폴더를 순회하며 제품 JSON 생성"""

    if categories is None:
        # 폴더 이름으로 카테고리 자동 감지
        categories = [
            d.name
            for d in source_root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    result = {}

    for category in categories:
        category_path = source_root / category
        if not category_path.exists():
            print(f"⚠️  카테고리 폴더를 찾을 수 없습니다: {category}")
            continue

        # 영문 키 매핑 (선택사항)
        category_key = category
        if category == "낚시":
            category_key = "fishing"
        elif category == "오토바이":
            category_key = "motorcycle"
        elif category == "자동차":
            category_key = "car"
        elif category == "자전거":
            category_key = "bicycle"
        elif category == "캠핑":
            category_key = "camping"

        # 이미지는 extracted/<영문 카테고리> 폴더에 저장되므로 영문 키로 처리
        products = process_category_folder(
            category_path, output_image_dir, category_key
        )

        result[category_key] = {
            "source": str(category_path).replace("\\", "\\\\"),
            "items": [asdict(p) for p in products],
        }

    # JSON 저장
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 생성 완료: {output_json}")
    print(f"   총 카테고리: {len(result)}")
    for key, data in result.items():
        print(f"   - {key}: {len(data['items'])}개 제품")


def main():
    parser = argparse.ArgumentParser(
        description="워드 파일에서 제품 정보와 이미지를 추출하여 JSON 생성"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(r"\\192.168.1.89\share\dummy data\products"),
        help="제품 워드 파일이 있는 루트 폴더",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("apps/test/json/product_data.json"),
        help="생성할 JSON 파일 경로",
    )
    parser.add_argument(
        "--output-images",
        type=Path,
        default=Path("apps/static/extracted_product_images"),
        help="이미지를 저장할 폴더",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="처리할 카테고리 폴더 이름 (지정하지 않으면 전체)",
    )

    args = parser.parse_args()

    generate_product_json(
        source_root=args.source,
        output_json=args.output_json,
        output_image_dir=args.output_images,
        categories=args.categories,
    )


if __name__ == "__main__":
    main()
