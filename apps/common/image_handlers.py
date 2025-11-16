"""
이미지 처리 공통 모듈
- 이미지 압축, 저장, 삭제 기능 제공
"""
import os
import uuid
import shutil
import requests
from io import BytesIO
from datetime import datetime
from flask import current_app
from PIL import Image as PILImage

from apps.config.server import db


# 이미지 확장자 목록
IMAGE_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "jfif", "pjpeg", "pjp", 
    "webp", "avif", "apng", "svg"
}

# 기본 프로필 이미지 경로
DEFAULT_PROFILE_PATH = "static/default_profile.jpg"

# 이미지 타입별 규칙
IMAGE_RULES = {
    "default": {
        "max_size": (1024, 1024),
        "max_bytes": 1 * 1024 * 1024  # 1MB
    },
    "post": {
        "max_size": (2048, 2048),
        "max_bytes": 2 * 1024 * 1024  # 2MB
    },
    "profile": {
        "max_size": (512, 512),
        "max_bytes": 500 * 1024  # 500KB
    },
    "reply": {
        "max_size": (1024, 1024),
        "max_bytes": 1 * 1024 * 1024  # 1MB
    }
}


def compress_image(file, image_type="default"):
    """
    이미지 압축 및 리사이즈 공용 함수
    - IMAGE_RULES[image_type]에 따라 크기와 용량 제한 적용
    - 반환: (BytesIO 압축 데이터, 확장자, 원본 파일명)
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

    if current_app:
        current_app.logger.info(
            f"[✓] {image_type} 이미지 압축 완료 ({len(output.getvalue()) / 1024:.1f} KB, 품질={quality})"
        )

    return output, fmt, file.filename


def save_to_disk(output_stream, ext, filename, category="post"):
    """
    카테고리/날짜별로 이미지 저장
    - category: post / reply / profile
    - 날짜별 폴더 생성 (ex: static/post_images/2025-10-30/)
    - 반환: 상대경로 (ex: static/post_images/2025-10-30/uuid.jpg)
    """
    category_folder = f"static/{category}_images"
    if not os.path.exists(os.path.join(current_app.root_path, category_folder)):
        os.makedirs(os.path.join(current_app.root_path, category_folder), exist_ok=True)

    # 1️⃣ 날짜 폴더 생성
    date_folder = datetime.now().strftime("%Y-%m-%d")
    base_folder = f"static/{category}_images/{date_folder}"
    abs_folder = os.path.join(current_app.root_path, base_folder)
    if not os.path.exists(abs_folder):
        os.makedirs(abs_folder, exist_ok=True)

    # 2️⃣ 파일 경로
    abs_path = os.path.join(abs_folder, filename)
    rel_path = f"{base_folder}/{filename}"

    # 3️⃣ 실제 파일 저장
    with open(abs_path, "wb") as f:
        f.write(output_stream.read())

    if current_app:
        current_app.logger.info(f"[✓] 이미지 저장 완료 → {rel_path}")
    
    return rel_path


def delete_image(image, category="post"):
    """
    이미지를 서버에서 삭제 (DB는 Blueprint에서 처리)
    
    Args:
        image: Image 모델 객체 또는 directory 속성이 있는 객체
        category: 이미지 카테고리 (post, profile, reply)
    
    Returns:
        bool: 삭제 성공 여부
    """
    if not image:
        if current_app:
            current_app.logger.warning("존재하지 않는 이미지 객체입니다.")
        return False

    try:
        # directory 경로에서 파일 경로 추출
        if hasattr(image, 'directory'):
            rel_path = image.directory
        else:
            return False
        
        # 절대 경로로 변환
        if os.path.isabs(rel_path):
            abs_path = rel_path
        else:
            abs_path = os.path.join(current_app.root_path, rel_path.lstrip("/\\"))

        # 파일 존재 시 삭제
        if os.path.exists(abs_path):
            os.remove(abs_path)
            if current_app:
                current_app.logger.info(f"[✓] 이미지 파일 삭제 완료: {abs_path}")
            return True
        else:
            if current_app:
                current_app.logger.warning(f"[!] 삭제 대상 이미지 파일이 존재하지 않음: {abs_path}")
            return False

    except Exception as e:
        if current_app:
            current_app.logger.warning(f"[!] 이미지 삭제 실패: {e}")
        return False


def upload_profile(user, file=None, url=None):
    """
    프로필 이미지 업로드 및 DB 반영
    
    Args:
        user: User 모델 객체
        file: 업로드 파일 객체
        url: 소셜 로그인 프로필 이미지 URL
    
    Returns:
        str: 저장된 이미지 상대 경로
    """
    folder = "static/profile_images"
    backup_folder = os.path.join(folder, "backup")

    if not file and not url:
        if not user.profile_img:
            user.profile_img = DEFAULT_PROFILE_PATH
            db.session.add(user)
            db.session.commit()
        return user.profile_img

    # URL에서 이미지 다운로드
    if url and not file:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                raise ValueError("이미지 다운로드 실패")
            file = BytesIO(resp.content)
            file.filename = f"{uuid.uuid4()}.jpg"
        except Exception as e:
            if current_app:
                current_app.logger.warning(f"소셜 이미지 다운로드 실패: {e}")
            user.profile_img = DEFAULT_PROFILE_PATH
            db.session.commit()
            return user.profile_img

    # 기존 프로필 이미지 백업
    if user.profile_img and user.profile_img != DEFAULT_PROFILE_PATH:
        try:
            old_path = os.path.join(current_app.root_path, user.profile_img)
            if os.path.exists(old_path):
                os.makedirs(
                    os.path.join(current_app.root_path, backup_folder), exist_ok=True
                )
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}{os.path.splitext(old_path)[1]}"
                backup_path = os.path.join(
                    current_app.root_path, backup_folder, filename
                )
                shutil.move(old_path, backup_path)
                if current_app:
                    current_app.logger.info(f"이전 프로필 백업 완료: {backup_path}")
        except Exception as e:
            if current_app:
                current_app.logger.warning(f"이전 프로필 백업 실패: {e}")

    # 새 프로필 이미지 저장
    try:
        # 파일 확장자 추출
        ext = file.filename.rsplit(".", 1)[-1] if hasattr(file, 'filename') else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        
        # BytesIO 처리
        if hasattr(file, 'read'):
            file.seek(0)
        
        relative_path = save_to_disk(
            file, ext, filename, category="profile"
        )
        if current_app:
            current_app.logger.info(f"새 프로필 이미지 저장 완료: {relative_path}")
    except Exception as e:
        if current_app:
            current_app.logger.warning(f"프로필 이미지 저장 실패: {e}")
        relative_path = DEFAULT_PROFILE_PATH

    user.profile_img = relative_path
    db.session.add(user)
    db.session.commit()
    return relative_path
