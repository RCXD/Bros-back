import os
import sys
from pathlib import Path
import pytest
from apps.config.server import db
from apps.auth.models import User
from apps.image.models import Image
import random
from PIL import Image as PILImage

# 현재 스크립트의 디렉토리를 sys.path에 추가
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from gen_image_helper import ImageAPIUploader
    from gen_user_helper import get_all_user_tokens_from_db
    from logger import get_logger
except ImportError:
    from apps.test.gen.gen_image_helper import ImageAPIUploader
    from apps.test.gen.gen_user_helper import get_all_user_tokens_from_db
    from apps.common.logger import get_logger


def get_config_paths(app):
    """앱 설정에서 경로 가져오기"""
    return {
        "dummy_profile_dir": Path(
            app.config.get(
                "DUMMY_PROFILE_IMG_DIR",
                r"\\192.168.1.89\share\dummy data\profile_images",
            )
        ),
        "profile_storage_dir": Path(
            app.config.get("PROFILE_IMG_UPLOAD_FOLDER", "test/uploads/profile_images")
        ),
        "dummy_image_dir": Path(
            app.config.get(
                "DUMMY_POST_IMG_DIR", r"\\192.168.1.89\share\dummy data\images"
            )
        ),
        "image_storage_dir": Path(
            app.config.get("POST_IMG_UPLOAD_FOLDER", "test/uploads/post_images")
        ),
    }


# 프로필 이미지 크기 (정사각형)
PROFILE_SIZE = 512

# 게시글 이미지 최대 너비
MAX_WIDTH = 1024

# 폴더명과 카테고리 매핑
FOLDER_CATEGORY_MAP = {
    "daily": "STORY",
    "route": "ROUTE",
    "review": "REVIEW",
    "report": "REPORT",
}


def resize_and_convert_profile_image(source_path, dest_path):
    """
    프로필 이미지를 리사이즈하고 PNG로 변환
    - 512x512 정사각형으로 크롭
    - PNG 포맷으로 통일
    """
    try:
        # 애니메이션 포맷 제외
        if source_path.suffix.lower() in [".gif", ".webp"]:
            return None

        with PILImage.open(source_path) as img:
            # 애니메이션 이미지 체크
            if hasattr(img, "is_animated") and img.is_animated:
                return None

            # RGB 모드로 변환
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # 정사각형으로 중앙 크롭
            width, height = img.size

            # 짧은 쪽을 기준으로 정사각형 크롭
            if width > height:
                left = (width - height) // 2
                img = img.crop((left, 0, left + height, height))
            elif height > width:
                top = (height - width) // 2
                img = img.crop((0, top, width, top + width))

            # 512x512로 리사이즈
            img = img.resize((PROFILE_SIZE, PROFILE_SIZE), PILImage.Resampling.LANCZOS)

            # PNG로 저장
            img.save(dest_path, "PNG", optimize=True)
            return dest_path

    except Exception as e:
        print(f"    이미지 처리 실패 ({source_path.name}): {e}")
        return None


def get_profile_images(dummy_profile_dir):
    """프로필 이미지 파일 목록 가져오기 (재귀 검색, webp/gif 제외)"""
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

    image_files = []

    if not dummy_profile_dir.exists():
        return image_files

    # 재귀적으로 모든 하위 폴더에서 이미지 수집
    for ext in valid_extensions:
        image_files.extend(dummy_profile_dir.rglob(f"*{ext}"))
        image_files.extend(dummy_profile_dir.rglob(f"*{ext.upper()}"))

    return image_files


@pytest.mark.no_cleanup
def test_generate_profile_images(fixture_app):
    """사용자에게 프로필 이미지 할당 (512x512 정사각형, PNG)"""

    log = get_logger()

    with fixture_app.app_context():
        log.info("\n[2/5] 프로필 이미지 할당")

        # 설정에서 경로 가져오기
        paths = get_config_paths(fixture_app)
        dummy_profile_dir = paths["dummy_profile_dir"]
        profile_storage_dir = paths["profile_storage_dir"]

        # 환경 확인
        use_test_env = "--use-test-env" in os.sys.argv

        if use_test_env:
            # 테스트 환경: 직접 파일 저장
            log.debug("  테스트 환경: 직접 파일 저장 모드")
            _generate_profile_images_direct(
                fixture_app, dummy_profile_dir, profile_storage_dir
            )
        else:
            # 프로덕션 환경: API를 통한 업로드
            log.debug("  프로덕션 환경: API 업로드 모드")
            _generate_profile_images_via_api(fixture_app, dummy_profile_dir)


def _generate_profile_images_direct(app, dummy_profile_dir, profile_storage_dir):
    """테스트 환경: 직접 파일 저장 (기존 로직)"""
    log = get_logger()

    # 프로필 이미지 저장 디렉토리 생성
    profile_storage_dir.mkdir(parents=True, exist_ok=True)

    # 기존 프로필 이미지 레코드 삭제 (post_id가 NULL인 이미지)
    log.debug("  기존 프로필 이미지 레코드 정리 중...")
    Image.query.filter(Image.post_id == None).delete()
    db.session.commit()
    log.debug("  기존 프로필 이미지 레코드 삭제 완료")

    # 모든 사용자 가져오기
    users = User.query.all()

    if not users:
        log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
        pytest.skip("프로필 이미지를 할당할 사용자가 없습니다")

    # 프로필 이미지 파일 목록
    log.debug("  프로필 이미지 폴더 스캔 중...")
    profile_images = get_profile_images(dummy_profile_dir)

    if not profile_images:
        log.warning(f"  {dummy_profile_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("프로필 이미지 파일이 없습니다")

    log.debug(f"  {len(profile_images)}개의 프로필 이미지 발견")

    # 하위 폴더 정보 출력
    subfolders = [d.name for d in dummy_profile_dir.iterdir() if d.is_dir()]
    if subfolders:
        log.debug(f"  하위 폴더: {', '.join(subfolders)}")

    total_success = 0
    total_failed = 0

    log.debug("  프로필 이미지 할당 시작...")

    # 이미지를 섞어서 랜덤하게 할당 (중복 가능)
    random.shuffle(profile_images)

    # 사용자 수가 이미지 수보다 많으면 이미지를 반복 사용
    image_index = 0

    for user in users:
        # 순환하여 이미지 선택 (모든 이미지가 최소 한 번씩 사용되도록)
        source_image = profile_images[image_index % len(profile_images)]
        image_index += 1

        # Image 레코드 생성 (UUID 자동 생성)
        image_record = Image(
            post_id=None,  # 프로필 이미지는 post와 연결되지 않음
            user_id=user.user_id,
            directory="",  # 임시값, 나중에 상대 경로로 업데이트
            original_image_name=source_image.name,
            ext="png",
        )
        db.session.add(image_record)
        db.session.flush()  # UUID 생성을 위해 flush

        # UUID를 포함한 파일명 생성
        image_uuid = image_record.uuid
        new_filename = f"{image_uuid}.png"
        dest_path = profile_storage_dir / new_filename

        # 이미지 크롭 및 PNG 변환
        result = resize_and_convert_profile_image(source_image, dest_path)

        if result:
            # 상대 경로 + 파일명을 directory에 저장 (레거시 방식과 동일)
            # 예: "test/uploads/profile_images/uuid.png"
            rel_path = str(dest_path).replace("\\", "/")
            image_record.directory = rel_path
            # User 모델의 profile_img 필드를 UUID로 업데이트
            user.profile_img = image_uuid
            total_success += 1
        else:
            # 실패 시 Image 레코드 삭제
            db.session.delete(image_record)
            total_failed += 1

    db.session.commit()

    log.success(f"  성공: {total_success}개")
    if total_failed > 0:
        log.warning(f"  실패: {total_failed}개")
    log.debug(f"  이미지 레코드: {Image.query.filter(Image.post_id == None).count()}개")


def _generate_profile_images_via_api(app, dummy_profile_dir):
    """프로덕션 환경: API를 통한 프로필 이미지 업로드"""
    log = get_logger()

    # API 서버 주소 (앱 설정에서 가져오기)
    base_url = app.config.get("API_BACKEND_URL", "http://192.168.1.86:8002")

    # 모든 사용자 가져오기
    users = User.query.all()

    if not users:
        log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
        pytest.skip("프로필 이미지를 업로드할 사용자가 없습니다")

    # 프로필 이미지 파일 목록
    log.debug("  프로필 이미지 폴더 스캔 중...")
    profile_images = get_profile_images(dummy_profile_dir)

    if not profile_images:
        log.warning(f"  {dummy_profile_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("프로필 이미지 파일이 없습니다")

    log.debug(f"  {len(profile_images)}개의 프로필 이미지 발견")

    # 하위 폴더 정보 출력
    subfolders = [d.name for d in dummy_profile_dir.iterdir() if d.is_dir()]
    if subfolders:
        log.debug(f"  하위 폴더: {', '.join(subfolders)}")

    # 사용자 토큰 획득 (DB에서 실제 사용자 조회)
    log.debug("  사용자 토큰 획득 중...")
    num_users = app.config.get("NUM_USERS", 10)
    num_admins = app.config.get("NUM_ADMINS", 2)
    user_tokens = get_all_user_tokens_from_db(
        app, base_url, expected_users=num_users, expected_admins=num_admins
    )

    if not user_tokens:
        log.error("  사용자 토큰을 획득할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        pytest.skip("API 인증 실패")

    # API Uploader 초기화 (API 버전 전달)
    api_version = app.config.get("API_VERSION", "v1")
    uploader = ImageAPIUploader(base_url, api_version=api_version)

    total_success = 0
    total_failed = 0
    uploaded_users = []  # 업로드 성공한 사용자 정보 저장

    log.debug("  API를 통한 프로필 이미지 업로드 시작...")

    # 이미지를 섞어서 랜덤하게 할당
    random.shuffle(profile_images)

    # 사용자 수가 이미지 수보다 많으면 이미지를 반복 사용
    image_index = 0

    for idx, user in enumerate(users):
        # 사용자 토큰 확인
        user_token = user_tokens.get(user.email)
        if not user_token:
            log.debug(f"  ✗ {user.email}: 토큰 없음")
            total_failed += 1
            continue

        # 순환하여 이미지 선택
        source_image = profile_images[image_index % len(profile_images)]
        image_index += 1

        # API를 통해 프로필 이미지 업로드 (원본 이미지 전송, 리사이즈는 helper에서 처리)
        api_result = uploader.upload_profile_image(
            user_token=user_token, image_path=str(source_image)
        )

        if api_result:
            response_message = api_result.get("message", "")

            # V1 API 응답: "프로필이 성공적으로 업데이트되었습니다"
            # Legacy API 응답: "회원 정보가 수정되었습니다."
            if "업데이트" in response_message or "수정" in response_message:
                total_success += 1
                uploaded_users.append(user)
                log.debug(f"  ✓ {user.nickname}")

                # 100개마다 검증
                if (idx + 1) % 100 == 0:
                    log.debug(f"\n  🔍 중간 검증 ({idx + 1}번째)...")
                    verified = uploader.verify_profile_image(user.user_id)
                    if verified:
                        log.debug(
                            f"    ✅ 프로필 이미지 조회 성공: user_id={user.user_id}"
                        )
                    else:
                        log.warning(
                            f"    ❌ 프로필 이미지 조회 실패: user_id={user.user_id}"
                        )
            else:
                total_failed += 1
                log.debug(f"  ✗ {user.nickname}: 예상치 못한 응답 - {response_message}")
        else:
            total_failed += 1
            log.debug(f"  ✗ {user.nickname}: API 응답 없음")

    # 최종 일괄 검증
    log.debug("\n  🔍 최종 일괄 검증 중...")
    verified_count = 0
    failed_verify_count = 0

    for user in uploaded_users:
        if uploader.verify_profile_image(user.user_id):
            verified_count += 1
        else:
            failed_verify_count += 1
            log.warning(f"    ❌ 검증 실패: {user.nickname} (user_id={user.user_id})")

    log.debug(f"    검증 성공: {verified_count}/{len(uploaded_users)}개")
    if failed_verify_count > 0:
        log.warning(f"    검증 실패: {failed_verify_count}개")

    # 검증: 업로드된 이미지 확인
    log.debug("\n  📊 데이터베이스 검증 중...")
    db.session.expire_all()  # 캐시 무효화
    users_with_images = User.query.filter(User.profile_img != None).count()
    profile_images_in_db = Image.query.filter(Image.post_id == None).count()

    log.success(f"  성공: {total_success}개")
    if total_failed > 0:
        log.warning(f"  실패: {total_failed}개")
    log.debug(f"  이미지 있는 사용자: {users_with_images}명")
    log.debug(f"  이미지 레코드: {profile_images_in_db}개")


def resize_and_convert_image(source_path, dest_path):
    """게시글 이미지를 리사이즈하고 PNG로 변환"""
    log = get_logger()
    try:
        # 애니메이션 포맷 제외
        if source_path.suffix.lower() in [".gif", ".webp"]:
            return None

        with PILImage.open(source_path) as img:
            if hasattr(img, "is_animated") and img.is_animated:
                return None

            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "transparency" in img.info else "RGB")

            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                new_height = int(img.height * ratio)
                img = img.resize((MAX_WIDTH, new_height), PILImage.Resampling.LANCZOS)

            img.save(dest_path, "PNG", optimize=True)
            return dest_path

    except Exception as e:
        log.debug(f"이미지 처리 실패 ({source_path.name}): {e}")
        return None


def get_valid_image_files(dummy_image_dir):
    """유효한 이미지 파일 목록을 폴더별로 가져오기"""
    log = get_logger()
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    folder_images = {}

    for folder_name, category_name in FOLDER_CATEGORY_MAP.items():
        folder_path = dummy_image_dir / folder_name

        if not folder_path.exists():
            log.warning(f"폴더를 찾을 수 없습니다: {folder_path}")
            continue

        image_files = []
        for ext in valid_extensions:
            image_files.extend(folder_path.rglob(f"*{ext}"))
            image_files.extend(folder_path.rglob(f"*{ext.upper()}"))

        folder_images[category_name] = image_files
        log.debug(f"{folder_name}/ ({category_name}): {len(image_files)}개 이미지")

    return folder_images


@pytest.mark.no_cleanup
def test_generate_images(fixture_app):
    """Post 객체에 이미지 연결"""
    log = get_logger()

    with fixture_app.app_context():
        log.info("[5/5] 게시글 이미지 할당")

        paths = get_config_paths(fixture_app)
        dummy_image_dir = paths["dummy_image_dir"]
        image_storage_dir = paths["image_storage_dir"]

        use_test_env = "--use-test-env" in os.sys.argv

        if use_test_env:
            log.debug("테스트 환경: 직접 파일 저장 모드")
            _generate_images_direct(fixture_app, dummy_image_dir, image_storage_dir)
        else:
            log.debug("프로덕션 환경: API 업로드 모드")
            _generate_images_via_api(fixture_app, dummy_image_dir)


def _generate_images_direct(app, dummy_image_dir, image_storage_dir):
    """테스트 환경: 직접 파일 저장"""
    log = get_logger()

    from apps.post.models import Category, Post

    image_storage_dir.mkdir(parents=True, exist_ok=True)

    log.info("기존 게시글 이미지 레코드 정리 중...")
    Image.query.filter(Image.post_id != None).delete()
    db.session.commit()
    log.info("기존 게시글 이미지 레코드 삭제 완료")

    posts = Post.query.all()

    if not posts:
        log.warning("게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
        pytest.skip("이미지를 연결할 게시글이 없습니다")

    log.info("이미지 폴더 스캔 중...")
    folder_images = get_valid_image_files(dummy_image_dir)

    if not folder_images or all(len(imgs) == 0 for imgs in folder_images.values()):
        log.warning(f"{dummy_image_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("더미 이미지 파일이 없습니다")

    posts_by_category = {}
    for post in posts:
        category = Category.query.get(post.category_id)
        if category:
            cat_name = category.category_name
            if cat_name not in posts_by_category:
                posts_by_category[cat_name] = []
            posts_by_category[cat_name].append(post)

    log.info("카테고리별 게시글 수:")
    for cat_name, post_list in posts_by_category.items():
        log.debug(f"  {cat_name}: {len(post_list)}개 게시글")

    total_images = 0
    failed_images = 0

    log.info("이미지 연결 시작...")

    for category_name, post_list in posts_by_category.items():
        if category_name not in folder_images:
            log.warning(f"{category_name} 카테고리에 매칭되는 이미지 폴더가 없습니다.")
            continue

        available_images = folder_images[category_name]

        if not available_images:
            log.warning(f"{category_name} 폴더에 이미지가 없습니다.")
            continue

        log.info(f"{category_name} 카테고리 처리 중...")
        category_image_count = 0

        for post in post_list:
            num_images = random.choice(
                [0, 0, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3]
            )

            if num_images == 0:
                continue

            num_images = min(num_images, len(available_images))
            selected_images = random.sample(available_images, num_images)

            user = User.query.get(post.user_id)
            if not user:
                log.debug(
                    f"Post {post.post_id}의 작성자를 찾을 수 없습니다. 건너뜁니다."
                )
                continue

            for idx, image_file in enumerate(selected_images):
                image_record = Image(
                    post_id=post.post_id,
                    user_id=user.user_id,
                    directory="",
                    original_image_name=image_file.name,
                    ext="png",
                )
                db.session.add(image_record)
                db.session.flush()

                image_uuid = image_record.uuid
                new_filename = f"{image_uuid}.png"
                dest_path = image_storage_dir / new_filename

                result = resize_and_convert_image(image_file, dest_path)

                if result:
                    rel_path = str(dest_path).replace("\\", "/")
                    image_record.directory = rel_path
                    total_images += 1
                    category_image_count += 1
                else:
                    db.session.delete(image_record)
                    failed_images += 1

        log.info(f"{category_image_count}개 이미지 연결됨")

    db.session.commit()

    log.info("이미지-게시글 관계 검증 중...")
    from apps.post.models import Post

    orphan_images = (
        db.session.query(Image).outerjoin(Post).filter(Post.post_id == None).count()
    )
    if orphan_images > 0:
        log.warning(f"{orphan_images}개의 이미지가 존재하지 않는 게시글을 참조합니다!")
    else:
        log.info("모든 이미지가 올바른 게시글에 연결되었습니다")

    log.info("=" * 60)
    log.info("이미지 연결 완료 (직접 저장)")
    log.info("=" * 60)
    log.info(f"성공: {total_images}개")
    if failed_images > 0:
        log.warning(f"실패: {failed_images}개")
    log.info(f"총 게시글: {len(Post.query.all())}개")
    log.info(
        f"이미지가 있는 게시글: {db.session.query(Post).join(Image).distinct().count()}개"
    )
    log.info("=" * 60)


def _generate_images_via_api(app, dummy_image_dir):
    """프로덕션 환경: API를 통한 이미지 업로드"""
    log = get_logger()

    from apps.post.models import Category, Post

    base_url = app.config.get("API_BACKEND_URL", "http://192.168.1.86:8002")

    posts = Post.query.all()

    if not posts:
        log.warning("게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
        pytest.skip("이미지를 업로드할 게시글이 없습니다")

    log.info("이미지 폴더 스캔 중...")
    folder_images = get_valid_image_files(dummy_image_dir)

    if not folder_images or all(len(imgs) == 0 for imgs in folder_images.values()):
        log.warning(f"{dummy_image_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("더미 이미지 파일이 없습니다")

    posts_by_category = {}
    for post in posts:
        category = Category.query.get(post.category_id)
        if category:
            cat_name = category.category_name
            if cat_name not in posts_by_category:
                posts_by_category[cat_name] = []
            posts_by_category[cat_name].append(post)

    log.info("카테고리별 게시글 수:")
    for cat_name, post_list in posts_by_category.items():
        log.debug(f"  {cat_name}: {len(post_list)}개 게시글")

    num_users = app.config.get("NUM_USERS", 10)
    num_admins = app.config.get("NUM_ADMINS", 2)
    user_tokens = get_all_user_tokens_from_db(
        app, base_url, expected_users=num_users, expected_admins=num_admins
    )

    if not user_tokens:
        log.error("사용자 토큰을 획득할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        pytest.skip("API 인증 실패")

    api_version = app.config.get("API_VERSION", "v1")
    uploader = ImageAPIUploader(base_url, api_version=api_version)

    total_uploaded = 0
    total_failed = 0
    uploaded_image_info = []
    upload_counter = 0

    log.info("API를 통한 이미지 업로드 시작...")

    for category_name, post_list in posts_by_category.items():
        if category_name not in folder_images:
            log.warning(f"{category_name} 카테고리에 매칭되는 이미지 폴더가 없습니다.")
            continue

        available_images = folder_images[category_name]

        if not available_images:
            log.warning(f"{category_name} 폴더에 이미지가 없습니다.")
            continue

        log.info(f"{category_name} 카테고리 처리 중...")
        category_upload_count = 0

        for post in post_list:
            num_images = random.choice([0, 1, 1, 2, 2, 3])

            if num_images == 0:
                continue

            num_images = min(num_images, len(available_images))
            selected_images = random.sample(available_images, num_images)

            user = User.query.get(post.user_id)
            if not user:
                log.debug(
                    f"Post {post.post_id}의 작성자를 찾을 수 없습니다. 건너뜁니다."
                )
                continue

            user_token = user_tokens.get(user.email)
            if not user_token:
                log.debug(f"{user.email}의 토큰이 없습니다. 건너뜁니다.")
                continue

            image_paths = [str(img) for img in selected_images]

            log.debug(
                f"Post {post.post_id} ({user.nickname}): {len(image_paths)}개 이미지 업로드 시도..."
            )

            result = uploader.update_post_images(
                user_token=user_token, post_id=post.post_id, new_image_paths=image_paths
            )

            if result:
                response_message = result.get("message", "")
                log.debug(f"응답: {response_message}")

                if (
                    "수정" in response_message
                    or "완료" in response_message
                    or "uploaded" in response_message.lower()
                ):
                    uploaded_images = result.get("uploaded_images", [])
                    if uploaded_images:
                        count = len(uploaded_images)
                        for img_info in uploaded_images:
                            uploaded_image_info.append(
                                {"post_id": post.post_id, "uuid": img_info.get("uuid")}
                            )
                    else:
                        count = len(image_paths)

                    category_upload_count += count
                    total_uploaded += count
                    upload_counter += count
                    log.debug(f"{count}개 업로드 성공")

                    if upload_counter >= 100 and uploaded_image_info:
                        log.info("중간 검증 (100개째)...")
                        last_img = uploaded_image_info[-1]
                        if last_img["uuid"]:
                            verified = uploader.verify_post_image(last_img["uuid"])
                            if verified:
                                log.debug(
                                    f"이미지 조회 성공: post_id={last_img['post_id']}, uuid={last_img['uuid']}"
                                )
                            else:
                                log.warning(
                                    f"이미지 조회 실패: post_id={last_img['post_id']}, uuid={last_img['uuid']}"
                                )
                        upload_counter = 0
                else:
                    total_failed += len(image_paths)
                    log.debug("예상치 못한 응답")
            else:
                total_failed += len(image_paths)
                log.debug("API 응답 없음")

        log.info(f"{category_upload_count}개 이미지 업로드됨")

    if uploaded_image_info:
        log.info("최종 일괄 검증 중...")
        verified_count = 0
        failed_verify_count = 0
        sample_size = min(50, len(uploaded_image_info))

        import random as rand_module

        sample_images = rand_module.sample(uploaded_image_info, sample_size)

        for img_info in sample_images:
            if img_info["uuid"]:
                if uploader.verify_post_image(img_info["uuid"]):
                    verified_count += 1
                else:
                    failed_verify_count += 1
                    log.warning(
                        f"검증 실패: post_id={img_info['post_id']}, uuid={img_info['uuid']}"
                    )

        log.info(f"샘플 검증 결과: {verified_count}/{sample_size}개 성공")
        if failed_verify_count > 0:
            log.warning(f"검증 실패: {failed_verify_count}개")

    log.info("데이터베이스 검증 중...")
    db.session.expire_all()
    total_images_in_db = Image.query.filter(Image.post_id.isnot(None)).count()
    posts_with_images = db.session.query(Post).join(Image).distinct().count()

    log.info("=" * 60)
    log.info("이미지 업로드 완료 (API)")
    log.info("=" * 60)
    log.info(f"업로드 성공: {total_uploaded}개")
    if total_failed > 0:
        log.warning(f"실패: {total_failed}개")
    log.info(f"DB 이미지 레코드: {total_images_in_db}개")
    log.info(f"이미지가 있는 게시글: {posts_with_images}개")
    log.info("=" * 60)


if __name__ == "__main__":
    # 직접 실행할 경우
    log = get_logger()
    log.info("pytest를 사용하여 실행하세요:")
    log.info("pytest test/database/gen_images.py -v -s")
