import os
import sys
from pathlib import Path
import pytest
from app.extensions import db
from app.models.user import User
from app.models.image import Image
import random
from PIL import Image as PILImage

# 현재 스크립트의 디렉토리를 sys.path에 추가
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from image_api_helper import ImageAPIUploader
    from auth_helper import get_all_user_tokens
except ImportError:
    from test.database.image_api_helper import ImageAPIUploader
    from test.database.auth_helper import get_all_user_tokens


def get_config_paths(app):
    """앱 설정에서 경로 가져오기"""
    return {
        'dummy_profile_dir': Path(app.config.get('DUMMY_PROFILE_IMG_DIR', r"D:\share\dummy data\profile_images")),
        'profile_storage_dir': Path(app.config.get('PROFILE_IMG_UPLOAD_FOLDER', "test/uploads/profile_images")),
    }


# 프로필 이미지 크기 (정사각형)
PROFILE_SIZE = 512


def resize_and_convert_profile_image(source_path, dest_path):
    """
    프로필 이미지를 리사이즈하고 PNG로 변환
    - 512x512 정사각형으로 크롭
    - PNG 포맷으로 통일
    """
    try:
        # 애니메이션 포맷 제외
        if source_path.suffix.lower() in ['.gif', '.webp']:
            return None
        
        with PILImage.open(source_path) as img:
            # 애니메이션 이미지 체크
            if hasattr(img, 'is_animated') and img.is_animated:
                return None
            
            # RGB 모드로 변환
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            
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
            img.save(dest_path, 'PNG', optimize=True)
            return dest_path
            
    except Exception as e:
        print(f"    이미지 처리 실패 ({source_path.name}): {e}")
        return None


def get_profile_images(dummy_profile_dir):
    """프로필 이미지 파일 목록 가져오기 (재귀 검색, webp/gif 제외)"""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
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
    
    with fixture_app.app_context():
        # 설정에서 경로 가져오기
        paths = get_config_paths(fixture_app)
        dummy_profile_dir = paths['dummy_profile_dir']
        profile_storage_dir = paths['profile_storage_dir']
        
        # 환경 확인
        use_test_env = '--use-test-env' in os.sys.argv
        
        if use_test_env:
            # 테스트 환경: 직접 파일 저장
            print("\n🔧 테스트 환경: 직접 파일 저장 모드")
            _generate_profile_images_direct(fixture_app, dummy_profile_dir, profile_storage_dir)
        else:
            # 프로덕션 환경: API를 통한 업로드
            print("\n🚀 프로덕션 환경: API 업로드 모드")
            _generate_profile_images_via_api(fixture_app, dummy_profile_dir)


def _generate_profile_images_direct(app, dummy_profile_dir, profile_storage_dir):
    """테스트 환경: 직접 파일 저장 (기존 로직)"""
    # 프로필 이미지 저장 디렉토리 생성
    profile_storage_dir.mkdir(parents=True, exist_ok=True)
    
    # 기존 프로필 이미지 레코드 삭제 (post_id가 NULL인 이미지)
    print("\n🗑️  기존 프로필 이미지 레코드 정리 중...")
    Image.query.filter(Image.post_id == None).delete()
    db.session.commit()
    print("  ✓ 기존 프로필 이미지 레코드 삭제 완료")
    
    # 모든 사용자 가져오기
    users = User.query.all()
    
    if not users:
        print("\n⚠ 사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
        pytest.skip("프로필 이미지를 할당할 사용자가 없습니다")
    
    # 프로필 이미지 파일 목록
    print("\n📁 프로필 이미지 폴더 스캔 중...")
    profile_images = get_profile_images(dummy_profile_dir)
    
    if not profile_images:
        print(f"⚠ {dummy_profile_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("프로필 이미지 파일이 없습니다")
    
    print(f"  ✓ {len(profile_images)}개의 프로필 이미지 발견")
    
    # 하위 폴더 정보 출력
    subfolders = [d.name for d in dummy_profile_dir.iterdir() if d.is_dir()]
    if subfolders:
        print(f"    하위 폴더: {', '.join(subfolders)}")
    
    total_success = 0
    total_failed = 0
    
    print(f"\n🖼️ 프로필 이미지 할당 시작...")
    
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
            ext="png"
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
    
    print(f"\n{'='*60}")
    print(f"✅ 프로필 이미지 할당 완료 (직접 저장)")
    print(f"{'='*60}")
    print(f"  성공: {total_success}개")
    if total_failed > 0:
        print(f"  실패: {total_failed}개")
    print(f"  총 사용자: {len(User.query.all())}명")
    print(f"  이미지 레코드: {Image.query.filter(Image.post_id == None).count()}개")
    print(f"{'='*60}\n")


def _generate_profile_images_via_api(app, dummy_profile_dir):
    """프로덕션 환경: API를 통한 프로필 이미지 업로드"""
    
    # API 서버 주소
    base_url = "http://192.168.1.86:8000"
    
    # 모든 사용자 가져오기
    users = User.query.all()
    
    if not users:
        print("\n⚠ 사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
        pytest.skip("프로필 이미지를 업로드할 사용자가 없습니다")
    
    # 프로필 이미지 파일 목록
    print("\n📁 프로필 이미지 폴더 스캔 중...")
    profile_images = get_profile_images(dummy_profile_dir)
    
    if not profile_images:
        print(f"⚠ {dummy_profile_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("프로필 이미지 파일이 없습니다")
    
    print(f"  ✓ {len(profile_images)}개의 프로필 이미지 발견")
    
    # 하위 폴더 정보 출력
    subfolders = [d.name for d in dummy_profile_dir.iterdir() if d.is_dir()]
    if subfolders:
        print(f"    하위 폴더: {', '.join(subfolders)}")
    
    # 사용자 토큰 획득 (NUM_USERS + NUM_ADMINS)
    num_users = app.config.get('NUM_USERS', 10)
    num_admins = app.config.get('NUM_ADMINS', 2)
    user_tokens = get_all_user_tokens(base_url, num_users=num_users + num_admins)
    
    if not user_tokens:
        print("❌ 사용자 토큰을 획득할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        pytest.skip("API 인증 실패")
    
    # API Uploader 초기화
    uploader = ImageAPIUploader(base_url)
    
    total_success = 0
    total_failed = 0
    
    print(f"\n🖼️ API를 통한 프로필 이미지 업로드 시작...")
    
    # 이미지를 섞어서 랜덤하게 할당
    random.shuffle(profile_images)
    
    # 사용자 수가 이미지 수보다 많으면 이미지를 반복 사용
    image_index = 0
    
    for user in users:
        # 사용자 토큰 확인
        user_token = user_tokens.get(user.email)
        if not user_token:
            print(f"  ✗ {user.email}: 토큰 없음")
            total_failed += 1
            continue
        
        # 순환하여 이미지 선택
        source_image = profile_images[image_index % len(profile_images)]
        image_index += 1
        
        # API를 통해 프로필 이미지 업로드 (원본 이미지 전송, 리사이즈는 helper에서 처리)
        api_result = uploader.upload_profile_image(
            user_token=user_token,
            image_path=str(source_image)
        )
        
        if api_result and api_result.get('message') == '회원 정보가 수정되었습니다.':
            total_success += 1
            print(f"  ✓ {user.nickname}")
        else:
            total_failed += 1
            print(f"  ✗ {user.nickname}: API 업로드 실패")
    
    # 검증: 업로드된 이미지 확인
    print(f"\n🔍 업로드 결과 검증 중...")
    db.session.expire_all()  # 캐시 무효화
    users_with_images = User.query.filter(User.profile_img != None).count()
    profile_images_in_db = Image.query.filter(Image.post_id == None).count()
    
    print(f"\n{'='*60}")
    print(f"✅ 프로필 이미지 업로드 완료 (API)")
    print(f"{'='*60}")
    print(f"  성공: {total_success}개")
    if total_failed > 0:
        print(f"  실패: {total_failed}개")
    print(f"  총 사용자: {len(users)}명")
    print(f"  이미지 있는 사용자: {users_with_images}명")
    print(f"  이미지 레코드: {profile_images_in_db}개")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # 직접 실행할 경우
    print("pytest를 사용하여 실행하세요:")
    print("pytest test/database/gen_profile_images.py -v -s")
