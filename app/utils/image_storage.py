# utils/image_storage.py
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from datetime import datetime


# 전역 스레드 풀 (이미지 병렬 처리)
executor = ThreadPoolExecutor(max_workers=4)


def save_to_disk(output_stream, fmt, category="post"):
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
    filename = f"{uuid.uuid4()}.{fmt.lower()}"
    abs_path = os.path.join(abs_folder, filename)
    rel_path = f"{base_folder}/{filename}"

    # 3️⃣ 실제 파일 저장
    with open(abs_path, "wb") as f:
        f.write(output_stream.read())

    current_app.logger.info(f"[✓] 이미지 저장 완료 → {rel_path}")
    return abs_path, rel_path


def delete_image(image):
    """
     이미지를 서버에서 삭제 (DB 처리는 Blueprint에서 수행)
    - 실제 파일 삭제만 담당
    - DB 세션 변경은 하지 않음
    - 파일이 없어도 예외 없이 통과
    """
    if not image:
        current_app.logger.warning("[!] delete_image 호출: image 객체가 None입니다.")
        return False

    try:
        # 1️⃣ 실제 파일 절대 경로
        abs_path = os.path.join(current_app.root_path, image.directory)

        # 2️⃣ 파일 존재 여부 확인 후 삭제
        if os.path.exists(abs_path):
            os.remove(abs_path)
            current_app.logger.info(f"[✓] 이미지 파일 삭제 완료: {abs_path}")
        else:
            current_app.logger.warning(
                f"[!] 삭제 대상 이미지 파일이 존재하지 않음: {abs_path}"
            )

        return True

    except Exception as e:
        current_app.logger.warning(f"[!] 이미지 삭제 실패: {e}")
        return False
