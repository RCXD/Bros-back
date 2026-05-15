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
    "png",
    "jpg",
    "jpeg",
    "gif",
    "jfif",
    "pjpeg",
    "pjp",
    "webp",
    "avif",
    "apng",
    "svg",
}

# 기본 프로필 이미지 경로
DEFAULT_PROFILE_PATH = "static/default_profile.jpg"

# 이미지 타입별 규칙
IMAGE_RULES = {
    "default": {"max_size": (1024, 1024), "max_bytes": 1 * 1024 * 1024},  # 1MB
    "post": {"max_size": (2048, 2048), "max_bytes": 2 * 1024 * 1024},  # 2MB
    "profile": {"max_size": (512, 512), "max_bytes": 500 * 1024},  # 500KB
    "reply": {"max_size": (1024, 1024), "max_bytes": 1 * 1024 * 1024},  # 1MB
    "product": {"max_size": (2048, 2048), "max_bytes": 2 * 1024 * 1024},  # 2MB
}


def compress_image(file, image_type: str = "default"):
    """Compress and resize an image according to the rules for *image_type*.

    Applies the size and byte limits defined in :data:`IMAGE_RULES` for
    the given *image_type*.  Quality is reduced iteratively until the
    output fits within the byte limit.

    Args:
        file: File-like object (e.g. a Flask ``FileStorage``) with a
            ``filename`` attribute pointing to the original file name.
        image_type: Rule key in :data:`IMAGE_RULES`.  Defaults to
            ``"default"``.

    Returns:
        A three-tuple ``(output, fmt, original_filename)`` where
        *output* is a :class:`io.BytesIO` containing the compressed
        image data, *fmt* is the lowercase format string (e.g. ``"jpeg"``),
        and *original_filename* is ``file.filename``.
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


def save_to_disk(output_stream, ext: str, filename: str, category: str = "post") -> str:
    """Persist an image stream to disk under a date-partitioned folder.

    Creates ``static/<category>_images/<YYYY-MM-DD>/`` if it does not
    exist, writes the stream to ``<filename>`` inside that folder, and
    returns the relative path.

    Args:
        output_stream: Readable binary stream (e.g. :class:`io.BytesIO`)
            containing the image data.
        ext: File extension without the leading dot (e.g. ``"jpg"``).
        filename: Destination file name (including extension).
        category: Image category sub-folder prefix.  One of
            ``"post"``, ``"reply"``, or ``"profile"``.

    Returns:
        Relative path to the saved file, e.g.
        ``"static/post_images/2025-10-30/uuid.jpg"``.
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


def delete_image(image, category: str = "post") -> bool:
    """Delete an image file from disk.

    The database record deletion is the caller's responsibility.

    Args:
        image: An object that has a ``directory`` attribute containing
            the relative (or absolute) path to the image file.
        category: Image category, provided for contextual logging.

    Returns:
        ``True`` if the file was found and deleted successfully;
        ``False`` if the file did not exist, the *image* argument was
        ``None``, or an error occurred during deletion.
    """
    if not image:
        if current_app:
            current_app.logger.warning("존재하지 않는 이미지 객체입니다.")
        return False

    try:
        # directory 경로에서 파일 경로 추출
        if hasattr(image, "directory"):
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
                current_app.logger.warning(
                    f"[!] 삭제 대상 이미지 파일이 존재하지 않음: {abs_path}"
                )
            return False

    except Exception as e:
        if current_app:
            current_app.logger.warning(f"[!] 이미지 삭제 실패: {e}")
        return False


def upload_profile(user, file=None, url: str = None) -> str:
    """Upload a profile image and update the user record.

    Handles three cases:

    * **No file, no URL** – leaves the current profile image unchanged
      (or sets the default if the user has none).
    * **URL only** – downloads the image from *url* and saves it.
    * **File** – compresses and saves the uploaded file.

    The previous profile image (if any and not the default) is moved to
    a backup folder before the new one is saved.

    Args:
        user: :class:`~apps.auth.models.User` model instance to update.
        file: Optional file-like object (``FileStorage`` or
            ``BytesIO``) containing the new profile image.
        url: Optional URL to download the profile image from (used for
            social-login avatar images).

    Returns:
        Relative path to the saved (or unchanged) profile image.
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
        ext = file.filename.rsplit(".", 1)[-1] if hasattr(file, "filename") else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"

        # BytesIO 처리
        if hasattr(file, "read"):
            file.seek(0)

        relative_path = save_to_disk(file, ext, filename, category="profile")
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


def compress_product_image(file, max_size: tuple = (2048, 2048), max_bytes: int = 2 * 1024 * 1024):
    """Compress and resize a product image.

    Converts the image to RGB if necessary (handles RGBA/LA/P modes),
    resizes it to fit within *max_size* while preserving aspect ratio,
    then iteratively reduces JPEG quality until the output is within
    *max_bytes*.

    Args:
        file: Image file object (``FileStorage`` or ``BytesIO``).
        max_size: Maximum ``(width, height)`` in pixels.
        max_bytes: Maximum output size in bytes.

    Returns:
        A two-tuple ``(output, ext)`` where *output* is a
        :class:`io.BytesIO` of the compressed data and *ext* is the
        lowercase extension string (``"jpg"`` for JPEG).
    """
    # 파일 포인터를 처음으로 이동
    if hasattr(file, "seek"):
        file.seek(0)

    image = PILImage.open(file)
    fmt = (image.format or "JPEG").upper()

    # RGB 변환 (RGBA 등 처리)
    if image.mode in ("RGBA", "LA", "P"):
        background = PILImage.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(
            image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None
        )
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # 리사이즈
    if max_size:
        image.thumbnail(max_size, PILImage.Resampling.LANCZOS)

    # 압축 반복
    quality = 85
    output = BytesIO()
    image.save(output, format=fmt, optimize=True, quality=quality)
    output.seek(0)

    while len(output.getvalue()) > max_bytes and quality > 30:
        quality -= 10
        output = BytesIO()
        image.save(output, format=fmt, optimize=True, quality=quality)
        output.seek(0)

    ext = fmt.lower()
    if ext == "jpeg":
        ext = "jpg"

    if current_app:
        current_app.logger.info(
            f"[✓] 제품 이미지 압축 완료 ({len(output.getvalue()) / 1024:.1f} KB, 품질={quality})"
        )

    return output, ext


def save_product_image(file, category: str = "general") -> str:
    """Compress and save a product main image, returning its UUID.

    The image is stored at
    ``static/product_images/<category>/<YYYY-MM-DD>/<uuid>.<ext>``.

    Args:
        file: Image file object to compress and save.
        category: Product category sub-folder (e.g. ``"fishing"``).

    Returns:
        The UUID string assigned to the saved image file.
    """
    # 이미지 압축
    compressed, ext = compress_product_image(file)

    # UUID 생성
    image_uuid = str(uuid.uuid4())
    filename = f"{image_uuid}.{ext}"

    # 날짜별 폴더 경로 생성
    date_folder = datetime.now().strftime("%Y-%m-%d")
    base_folder = f"static/product_images/{category}/{date_folder}"

    if current_app:
        abs_folder = os.path.join(current_app.root_path, base_folder)
    else:
        abs_folder = base_folder

    os.makedirs(abs_folder, exist_ok=True)

    # 파일 저장
    abs_path = os.path.join(abs_folder, filename)
    with open(abs_path, "wb") as f:
        f.write(compressed.read())

    if current_app:
        current_app.logger.info(f"[✓] 제품 이미지 저장 완료 → {base_folder}/{filename}")

    return image_uuid


def save_product_detail_images(files, category: str = "general") -> list:
    """Compress and save multiple product detail images.

    Iterates over *files*, calling :func:`save_product_image` for each.
    Failures for individual files are logged and skipped.

    Args:
        files: Iterable of image file objects to save.
        category: Product category sub-folder.

    Returns:
        List of UUID strings for the successfully saved images.
    """
    if not files:
        return []

    uuids = []
    for file in files:
        try:
            image_uuid = save_product_image(file, category)
            uuids.append(image_uuid)
        except Exception as e:
            if current_app:
                current_app.logger.warning(f"[!] 상세 이미지 저장 실패: {e}")
            continue

    return uuids


def get_product_image_path(image_uuid: str, category: str, date: str = None) -> str:
    """Locate a product image file by its UUID.

    Searches for a filename that starts with *image_uuid* in the
    ``static/product_images/<category>/<date>/`` directory.

    Args:
        image_uuid: UUID prefix to search for.
        category: Product category sub-folder.
        date: Date string in ``"YYYY-MM-DD"`` format.  Defaults to
            today's date.

    Returns:
        Relative path to the matching image file, or ``None`` if not
        found.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    base_folder = f"static/product_images/{category}/{date}"

    if current_app:
        abs_folder = os.path.join(current_app.root_path, base_folder)
    else:
        abs_folder = base_folder

    # UUID로 시작하는 파일 검색
    if os.path.exists(abs_folder):
        for filename in os.listdir(abs_folder):
            if filename.startswith(image_uuid):
                return f"{base_folder}/{filename}"

    return None


def delete_product_image(image_uuid: str, category: str, date: str = None) -> bool:
    """Delete a product image file identified by its UUID.

    Args:
        image_uuid: UUID of the image to delete.
        category: Product category sub-folder.
        date: Date string in ``"YYYY-MM-DD"`` format used to locate the
            file.  Defaults to today's date.

    Returns:
        ``True`` if the file was found and deleted; ``False`` otherwise.
    """
    image_path = get_product_image_path(image_uuid, category, date)

    if not image_path:
        if current_app:
            current_app.logger.warning(
                f"[!] 삭제 대상 이미지를 찾을 수 없음: {image_uuid}"
            )
        return False

    if current_app:
        abs_path = os.path.join(current_app.root_path, image_path)
    else:
        abs_path = image_path

    try:
        if os.path.exists(abs_path):
            os.remove(abs_path)
            if current_app:
                current_app.logger.info(f"[✓] 제품 이미지 삭제 완료: {abs_path}")
            return True
        return False
    except Exception as e:
        if current_app:
            current_app.logger.warning(f"[!] 제품 이미지 삭제 실패: {e}")
        return False
