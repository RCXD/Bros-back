# utils/image_storage.py
from io import BytesIO
from flask import current_app
from .image_rules import IMAGE_RULES
from ..models.image import Image
from PIL import Image as PILImage


def compress_image(file, image_type="default"):
    """
     이미지 압축 및 리사이즈 공용 함수
    - IMAGE_RULES[image_type]에 따라 크기와 용량 제한 적용
    - 반환: (BytesIO 압축 데이터, 확장자/포맷)
    """
    rule = IMAGE_RULES.get(image_type, IMAGE_RULES["default"])
    max_size = rule["max_size"]
    max_bytes = rule["max_bytes"]

    image = PILImage.open(file)
    fmt = (image.format or "JPEG").lower()

    # 1️⃣ 리사이즈 (비율 유지)
    if max_size:
        image.thumbnail(max_size, PILImage.Resampling.LANCZOS)

    # 2️⃣ 압축 반복
    quality = 85
    output = BytesIO()
    image.save(output, format=fmt.upper(), optimize=True, quality=quality)
    output.seek(0)

    while len(output.getvalue()) > max_bytes and quality > 30:
        quality -= 10
        output = BytesIO()
        image.save(output, format=fmt.upper(), optimize=True, quality=quality)
        output.seek(0)

    current_app.logger.info(
        f"[✓] {image_type} 이미지 압축 완료 ({len(output.getvalue()) / 1024:.1f} KB, 품질={quality})"
    )

    return output, fmt
