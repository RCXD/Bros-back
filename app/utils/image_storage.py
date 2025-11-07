# utils/image_storage.py
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from datetime import datetime


# 전역 스레드 풀 (이미지 병렬 처리)
executor = ThreadPoolExecutor(max_workers=4)


def save_to_disk(output_stream, ext, filename, category="post"):
    """
     카테고리/날짜별로 이미지 저장
    - category: post / reply / profile
    - 날짜별 폴더 생성 (ex: static/post_images/2025-10-30/)
    - 반환: (절대경로, 상대경로)
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

    # 2️⃣ 파일명 UUID
    # filename = f"{uuid.uuid4()}.{ext.lower()}"
    abs_path = os.path.join(abs_folder, filename)
    rel_path = f"{base_folder}/{filename}"

    # 3️⃣ 실제 파일 저장
    with open(abs_path, "wb") as f:
        f.write(output_stream.read())

    current_app.logger.info(f"[✓] 이미지 저장 완료 → {rel_path}")
    return rel_path


def delete_image(image, category="post"):
    """
    이미지를 서버에서 삭제 (DB는 Blueprint에서 처리)
    """
    if not image:
        current_app.logger.warning("존재하지 않는 이미지 객체입니다.")
        return False

    try:
        # 날짜별 폴더 구조 계산
        date = image.created_at.strftime("%Y-%m-%d")
        base_folder = f"static/{category}_images/{date}"
        abs_folder = os.path.join(current_app.root_path, base_folder)

        # 파일 이름은 실제 저장된 것과 동일하게 사용
        # save_to_disk에서 filename = f"{uuid4()}.{ext}" 형태로 저장했으므로
        filename = os.path.basename(image.directory)
        abs_path = os.path.join(abs_folder, filename)

        # 파일 존재 시 삭제
        if os.path.exists(abs_path):
            os.remove(abs_path)
            current_app.logger.info(f"[✓] 이미지 파일 삭제 완료: {abs_path}")
        else:
            current_app.logger.warning(f"[!] 삭제 대상 이미지 파일이 존재하지 않음: {abs_path}")

        return True

    except Exception as e:
        current_app.logger.warning(f"[!] 이미지 삭제 실패: {e}")
        return False
