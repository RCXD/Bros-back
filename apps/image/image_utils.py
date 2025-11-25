"""
Image utilities
이미지 저장, 압축, 처리 유틸리티
"""

import os
import uuid
from datetime import datetime
from flask import current_app
from apps.image.models import Image
from apps.config.server import db


def save_profile_image(file, user_id=None):
    """
    프로필 이미지를 저장하고 Image 레코드 생성

    Args:
        file: 업로드된 파일 객체
        user_id: 사용자 ID (선택)

    Returns:
        str: 저장된 이미지의 UUID
    """
    original_name = file.filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    today = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(current_app.root_path, "static/profile_images", today)
    os.makedirs(folder_path, exist_ok=True)

    uuid_val = uuid.uuid4()
    filename = f"{uuid_val}.{ext}"
    file_path = os.path.join(folder_path, filename)

    file.save(file_path)

    relative_path = f"static/profile_images/{today}/{filename}"

    if user_id:
        new_image = Image(
            uuid=str(uuid_val),
            user_id=user_id,
            directory=relative_path,
            original_image_name=original_name,
            updated_at=datetime.now(),
            post_id=None,
            product_id=None,
            ext=ext,
        )
        db.session.add(new_image)

    return str(uuid_val)


def save_post_image(file, user_id, post_id=None):
    """
    게시글 이미지를 저장하고 Image 레코드 생성

    Args:
        file: 업로드된 파일 객체
        user_id: 사용자 ID
        post_id: 게시글 ID (선택)

    Returns:
        Image: 생성된 Image 객체
    """
    original_name = file.filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    today = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(current_app.root_path, "static/post_images", today)
    os.makedirs(folder_path, exist_ok=True)

    uuid_val = uuid.uuid4()
    filename = f"{uuid_val}.{ext}"
    file_path = os.path.join(folder_path, filename)

    file.save(file_path)

    relative_path = f"static/post_images/{today}/{filename}"

    new_image = Image(
        uuid=str(uuid_val),
        user_id=user_id,
        post_id=post_id,
        product_id=None,
        directory=relative_path,
        original_image_name=original_name,
        ext=ext,
    )
    db.session.add(new_image)

    return new_image


def save_product_image(file_path, product_id, image_type="main", display_order=0):
    """
    상품 이미지 레코드 생성 (이미 저장된 파일)

    Args:
        file_path: 저장된 파일의 상대 경로
        product_id: 상품 ID
        image_type: 이미지 타입 ('main' or 'detail')
        display_order: 표시 순서

    Returns:
        Image: 생성된 Image 객체
    """
    # 파일명에서 UUID와 확장자 추출
    filename = os.path.basename(file_path)
    name_without_ext = filename.rsplit(".", 1)[0]
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

    uuid_val = uuid.uuid4()

    new_image = Image(
        uuid=str(uuid_val),
        product_id=product_id,
        user_id=None,
        post_id=None,
        directory=file_path,
        original_image_name=filename,
        ext=ext,
        image_type=image_type,
        display_order=display_order,
    )
    db.session.add(new_image)

    return new_image
