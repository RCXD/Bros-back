# 상품이미지 목록 가져오기
from typing import List
from apps.image.models import Image


# 상품아이디로 이미지 조회하고 상품코드로 정렬하기
def get_product_images(product_id) -> List[str]:
    images = (
        Image.query.filter_by(product_id=product_id).order_by(Image.directory).all()
    )
    return [image.uuid for image in images]
