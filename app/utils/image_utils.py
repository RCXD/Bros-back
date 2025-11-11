import os
import uuid
import shutil
import requests
from io import BytesIO
from datetime import datetime
from flask import current_app
from ..extensions import db
from .image_storage import save_to_disk  # 기존 저장 함수 사용

DEFAULT_PROFILE_PATH = "static/default_profile.jpg"

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "jfif", "pjpeg", "pjp", "webp", "avif", "apng", "svg", }

def upload_profile(user, file=None, url=None):
    """프로필 이미지 업로드 및 DB 반영"""
    folder = "static/profile_images"
    backup_folder = os.path.join(folder, "backup")

    if not file and not url:
        if not user.profile_img:
            user.profile_img = DEFAULT_PROFILE_PATH
            db.session.add(user)
            db.session.commit()
        return user.profile_img

    if url and not file:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                raise ValueError("이미지 다운로드 실패")
            file = BytesIO(resp.content)
            file.filename = f"{uuid.uuid4()}.jpg"
        except Exception as e:
            current_app.logger.warning(f"소셜 이미지 다운로드 실패: {e}")
            user.profile_img = DEFAULT_PROFILE_PATH
            db.session.commit()
            return user.profile_img

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
                current_app.logger.info(f"이전 프로필 백업 완료: {backup_path}")
        except Exception as e:
            current_app.logger.warning(f"이전 프로필 백업 실패: {e}")

    try:
        relative_path = save_to_disk(
            file, fmt=file.filename.rsplit(".", 1)[-1], category="profile"
        )
        current_app.logger.info(f"새 프로필 이미지 저장 완료: {relative_path}")
    except Exception as e:
        current_app.logger.warning(f"프로필 이미지 저장 실패: {e}")
        relative_path = DEFAULT_PROFILE_PATH

    user.profile_img = relative_path
    db.session.add(user)
    db.session.commit()
    return relative_path


def delete_image(image_obj):
    """DB 객체와 실제 파일을 같이 삭제 (날짜별 폴더 지원)"""
    if not image_obj or not getattr(image_obj, "directory", None):
        print("[WARN] image_obj 또는 directory 없음")
        return

    rel_path = image_obj.directory
    if os.path.isabs(rel_path):
        abs_path = rel_path
    else:
        abs_path = os.path.join(current_app.root_path, rel_path.lstrip("/\\"))

    print(f"[삭제 시도] {abs_path}")

    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
            print(f"[삭제 완료] {abs_path}")
        except Exception as e:
            print(f"[파일 삭제 실패] {abs_path}: {e}")
    else:
        print(f"[WARN] 파일 없음: {abs_path}")
