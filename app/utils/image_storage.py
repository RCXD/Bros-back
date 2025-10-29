# utils/image_storage.py
import os
import uuid
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, UnidentifiedImageError
from flask import current_app
from .image_rules import IMAGE_RULES

# 전역 스레드 풀 (이미지 병렬 처리)
executor = ThreadPoolExecutor(max_workers=4)


def _compress_and_resize(file_path, image_type="default"):
    """
    ✅ 내부용: 파일 경로를 받아 리사이즈 및 압축 실행
    - 백그라운드 스레드에서 실행됨
    """
    rule = IMAGE_RULES.get(image_type, IMAGE_RULES["default"])
    max_size = rule["max_size"]
    max_bytes = rule["max_bytes"]

    try:
        with Image.open(file_path) as image:
            ext = os.path.splitext(file_path)[1].lower()
            fmt = image.format or "JPEG"

            # 리사이즈
            if max_size:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # 압축 저장 반복
            quality = 85
            output = BytesIO()
            image.save(output, format=fmt, optimize=True, quality=quality)
            output.seek(0)

            while len(output.getvalue()) > max_bytes and quality > 30:
                quality -= 10
                output = BytesIO()
                image.save(output, format=fmt, optimize=True, quality=quality)
                output.seek(0)

            # 최종 저장 (덮어쓰기)
            with open(file_path, "wb") as f:
                f.write(output.read())

            current_app.logger.info(
                f"[✓] {file_path} 압축 완료 ({len(output.getvalue()) / 1024:.1f} KB)"
            )

    except Exception as e:
        current_app.logger.warning(f"[!] 이미지 압축 실패: {e}")


def save_image(file, folder="static/uploads", image_type="default"):
    """
    ✅ 이미지를 서버에 저장하고 경로 반환
    - 저장 후 즉시 응답 반환
    - 백그라운드에서 압축 및 리사이즈 수행
    """
    os.makedirs(os.path.join(current_app.root_path, folder), exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    allowed_ext = [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".apng",
        ".avif",
        ".jfif",
        "pjpeg",
        ".pjp",
    ]
    if ext not in allowed_ext:
        raise ValueError(f"❌ 지원하지 않는 이미지 형식: {ext}")

    # 파일 이름 및 경로
    filename = f"{uuid.uuid4()}{ext}"
    save_path = os.path.join(current_app.root_path, folder, filename)
    relative_path = f"{folder}/{filename}"

    # 즉시 저장 (압축 전 원본)
    file.save(save_path)

    # 비동기로 압축 처리
    executor.submit(_compress_and_resize, save_path, image_type)

    return relative_path
