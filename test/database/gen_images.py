import os
import sys
import shutil
from pathlib import Path
import pytest
from app.extensions import db
from app.models.post import Post
from app.models.image import Image
from app.models.user import User
from app.models.category import Category
import random
from PIL import Image as PILImage

# 현재 스크립트의 디렉토리를 sys.path에 추가 (상대 import 가능하게)
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from image_api_helper import ImageAPIUploader
    from auth_helper import get_all_user_tokens
except ImportError:
    # pytest로 실행할 때는 절대 import 사용
    from test.database.image_api_helper import ImageAPIUploader
    from test.database.auth_helper import get_all_user_tokens


def get_config_paths(app):
    """앱 설정에서 경로 가져오기"""
    return {
        'dummy_image_dir': Path(app.config.get('DUMMY_POST_IMG_DIR', r"D:\share\dummy data\images")),
        'image_storage_dir': Path(app.config.get('POST_IMG_UPLOAD_FOLDER', "test/uploads/post_images")),
    }


# 최대 이미지 너비
MAX_WIDTH = 1024

# 폴더명과 카테고리 매핑
FOLDER_CATEGORY_MAP = {
    'daily': 'STORY',      # daily -> STORY
    'route': 'ROUTE',      # route -> ROUTE
    'review': 'REVIEW',    # review -> REVIEW
    'report': 'REPORT'     # report -> REPORT
}


def resize_and_convert_image(source_path, dest_path):
    """
    이미지를 리사이즈하고 PNG로 변환
    - 최대 가로 1024px
    - PNG 포맷으로 통일
    - webp, gif 같은 애니메이션 포맷은 제외
    """
    try:
        # 애니메이션 포맷 제외
        if source_path.suffix.lower() in ['.gif', '.webp']:
            return None
        
        with PILImage.open(source_path) as img:
            # 애니메이션 이미지 체크 (GIF의 경우)
            if hasattr(img, 'is_animated') and img.is_animated:
                return None
            
            # RGBA 또는 RGB 모드로 변환 (PNG 호환)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
            
            # 리사이즈 (가로가 MAX_WIDTH보다 크면)
            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                new_height = int(img.height * ratio)
                img = img.resize((MAX_WIDTH, new_height), PILImage.Resampling.LANCZOS)
            
            # PNG로 저장
            img.save(dest_path, 'PNG', optimize=True)
            return dest_path
            
    except Exception as e:
        print(f"이미지 처리 실패 ({source_path.name}): {e}")
        return None


def get_valid_image_files(dummy_image_dir):
    """유효한 이미지 파일 목록을 폴더별로 재귀적으로 가져오기 (webp, gif 제외)"""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    folder_images = {}
    
    # 각 폴더를 순회하며 이미지 수집 (하위 폴더 포함)
    for folder_name, category_name in FOLDER_CATEGORY_MAP.items():
        folder_path = dummy_image_dir / folder_name
        
        if not folder_path.exists():
            print(f"⚠ 폴더를 찾을 수 없습니다: {folder_path}")
            continue
        
        image_files = []
        
        # 재귀적으로 모든 하위 폴더에서 이미지 수집
        for ext in valid_extensions:
            # ** 패턴으로 재귀 검색
            image_files.extend(folder_path.rglob(f"*{ext}"))
            image_files.extend(folder_path.rglob(f"*{ext.upper()}"))
        
        folder_images[category_name] = image_files
        
        # 하위 폴더 정보 출력
        subfolders = [d.name for d in folder_path.iterdir() if d.is_dir()]
        if subfolders:
            print(f"  {folder_name}/ ({category_name}): {len(image_files)}개 이미지")
            print(f"    하위 폴더: {', '.join(subfolders)}")
        else:
            print(f"  {folder_name}/ ({category_name}): {len(image_files)}개 이미지")
    
    return folder_images


@pytest.mark.no_cleanup
def test_generate_images(fixture_app):
    """Post 객체에 이미지 연결 (리사이즈 및 PNG 변환, 폴더별 카테고리 매칭)"""
    
    with fixture_app.app_context():
        # 설정에서 경로 가져오기
        paths = get_config_paths(fixture_app)
        dummy_image_dir = paths['dummy_image_dir']
        image_storage_dir = paths['image_storage_dir']
        
        # 환경 확인
        use_test_env = '--use-test-env' in os.sys.argv
        
        if use_test_env:
            # 테스트 환경: 직접 파일 저장
            print("\n🔧 테스트 환경: 직접 파일 저장 모드")
            _generate_images_direct(fixture_app, dummy_image_dir, image_storage_dir)
        else:
            # 프로덕션 환경: API를 통한 업로드
            print("\n🚀 프로덕션 환경: API 업로드 모드")
            _generate_images_via_api(fixture_app, dummy_image_dir)


def _generate_images_direct(app, dummy_image_dir, image_storage_dir):
    """테스트 환경: 직접 파일 저장 (기존 로직)"""
    # 이미지 저장 디렉토리 생성
    image_storage_dir.mkdir(parents=True, exist_ok=True)
    
    # 기존 이미지 레코드 삭제 (post-image 관계 재설정)
    print("\n🗑️  기존 이미지 레코드 정리 중...")
    Image.query.delete()
    db.session.commit()
    print("  ✓ 기존 이미지 레코드 삭제 완료")
    
    # 모든 Post와 Category 가져오기
    posts = Post.query.all()
    categories = {cat.category_name: cat.category_id for cat in Category.query.all()}
    
    if not posts:
        print("\n⚠ 게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
        pytest.skip("이미지를 연결할 게시글이 없습니다")
    
    # 더미 이미지 파일 목록 (폴더별)
    print("\n📁 이미지 폴더 스캔 중...")
    folder_images = get_valid_image_files(dummy_image_dir)
    
    if not folder_images or all(len(imgs) == 0 for imgs in folder_images.values()):
        print(f"\n⚠ {dummy_image_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("더미 이미지 파일이 없습니다")
    
    # 카테고리별로 게시글 그룹화
    posts_by_category = {}
    for post in posts:
        category = Category.query.get(post.category_id)
        if category:
            cat_name = category.category_name
            if cat_name not in posts_by_category:
                posts_by_category[cat_name] = []
            posts_by_category[cat_name].append(post)
    
    print(f"\n📊 카테고리별 게시글 수:")
    for cat_name, post_list in posts_by_category.items():
        print(f"  {cat_name}: {len(post_list)}개 게시글")
    
    total_images = 0
    failed_images = 0
    
    print(f"\n🖼️ 이미지 연결 시작...")
    
    # 카테고리별로 게시글에 이미지 할당
    for category_name, post_list in posts_by_category.items():
        # 해당 카테고리에 매칭되는 이미지 폴더 찾기
        if category_name not in folder_images:
            print(f"⚠ {category_name} 카테고리에 매칭되는 이미지 폴더가 없습니다.")
            continue
        
        available_images = folder_images[category_name]
        
        if not available_images:
            print(f"⚠ {category_name} 폴더에 이미지가 없습니다.")
            continue
        
        print(f"\n  {category_name} 카테고리 처리 중...")
        category_image_count = 0
        
        for post in post_list:
            # 각 포스트에 랜덤하게 0-3개의 이미지 할당 (0개 가능)
            num_images = random.choice([0, 1, 1, 2, 2, 3])  # 0개 가능하지만 확률 낮게
            
            if num_images == 0:
                continue
            
            # 이미지가 충분하지 않으면 사용 가능한 만큼만
            num_images = min(num_images, len(available_images))
            selected_images = random.sample(available_images, num_images)
            
            # 게시글 작성자 가져오기
            user = User.query.get(post.user_id)
            if not user:
                print(f"    ⚠ Post {post.post_id}의 작성자를 찾을 수 없습니다. 건너뜁니다.")
                continue
            
            for idx, image_file in enumerate(selected_images):
                # Image 레코드 생성 (UUID 자동 생성)
                image_record = Image(
                    post_id=post.post_id,
                    user_id=user.user_id,
                    directory=str(image_storage_dir),
                    original_image_name=image_file.name,
                    ext="png"
                )
                db.session.add(image_record)
                db.session.flush()  # UUID 생성을 위해 flush
                
                # UUID를 포함한 파일명 생성
                image_uuid = image_record.uuid
                new_filename = f"{image_uuid}.png"
                dest_path = image_storage_dir / new_filename
                
                # 이미지 리사이즈 및 PNG 변환
                result = resize_and_convert_image(image_file, dest_path)
                
                if result:
                    total_images += 1
                    category_image_count += 1
                else:
                    # 실패 시 Image 레코드 삭제
                    db.session.delete(image_record)
                    failed_images += 1
        
        print(f"    ✓ {category_image_count}개 이미지 연결됨")
    
    db.session.commit()
    
    # 검증: post_id가 실제로 존재하는지 확인
    print(f"\n🔍 이미지-게시글 관계 검증 중...")
    orphan_images = db.session.query(Image).outerjoin(Post).filter(Post.post_id == None).count()
    if orphan_images > 0:
        print(f"  ⚠ 경고: {orphan_images}개의 이미지가 존재하지 않는 게시글을 참조합니다!")
    else:
        print(f"  ✓ 모든 이미지가 올바른 게시글에 연결되었습니다")
    
    print(f"\n{'='*60}")
    print(f"✅ 이미지 연결 완료 (직접 저장)")
    print(f"{'='*60}")
    print(f"  성공: {total_images}개")
    if failed_images > 0:
        print(f"  실패: {failed_images}개")
    print(f"  총 게시글: {len(Post.query.all())}개")
    print(f"  이미지가 있는 게시글: {db.session.query(Post).join(Image).distinct().count()}개")
    print(f"{'='*60}\n")


def _generate_images_via_api(app, dummy_image_dir):
    """프로덕션 환경: API를 통한 이미지 업로드"""
    
    # API 서버 주소 (앱 설정에서 가져오기)
    base_url = app.config.get('API_BACKEND_URL', 'http://192.168.1.86:8000')
    
    # 모든 Post와 Category 가져오기
    posts = Post.query.all()
    
    if not posts:
        print("\n⚠ 게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
        pytest.skip("이미지를 업로드할 게시글이 없습니다")
    
    # 더미 이미지 파일 목록 (폴더별)
    print("\n📁 이미지 폴더 스캔 중...")
    folder_images = get_valid_image_files(dummy_image_dir)
    
    if not folder_images or all(len(imgs) == 0 for imgs in folder_images.values()):
        print(f"\n⚠ {dummy_image_dir}에서 이미지 파일을 찾을 수 없습니다.")
        pytest.skip("더미 이미지 파일이 없습니다")
    
    # 카테고리별로 게시글 그룹화
    posts_by_category = {}
    for post in posts:
        category = Category.query.get(post.category_id)
        if category:
            cat_name = category.category_name
            if cat_name not in posts_by_category:
                posts_by_category[cat_name] = []
            posts_by_category[cat_name].append(post)
    
    print(f"\n📊 카테고리별 게시글 수:")
    for cat_name, post_list in posts_by_category.items():
        print(f"  {cat_name}: {len(post_list)}개 게시글")
    
    # 사용자 토큰 획득 (앱 설정에서 사용자 수 가져오기)
    num_users = app.config.get('NUM_USERS', 10)
    user_tokens = get_all_user_tokens(base_url, num_users=num_users)
    
    if not user_tokens:
        print("❌ 사용자 토큰을 획득할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        pytest.skip("API 인증 실패")
    
    # API Uploader 초기화
    uploader = ImageAPIUploader(base_url)
    
    total_uploaded = 0
    total_failed = 0
    
    print(f"\n🖼️ API를 통한 이미지 업로드 시작...")
    
    # 카테고리별로 게시글에 이미지 업로드
    for category_name, post_list in posts_by_category.items():
        # 해당 카테고리에 매칭되는 이미지 폴더 찾기
        if category_name not in folder_images:
            print(f"⚠ {category_name} 카테고리에 매칭되는 이미지 폴더가 없습니다.")
            continue
        
        available_images = folder_images[category_name]
        
        if not available_images:
            print(f"⚠ {category_name} 폴더에 이미지가 없습니다.")
            continue
        
        print(f"\n  {category_name} 카테고리 처리 중...")
        category_upload_count = 0
        
        for post in post_list:
            # 각 포스트에 랜덤하게 0-3개의 이미지 할당
            num_images = random.choice([0, 1, 1, 2, 2, 3])
            
            if num_images == 0:
                continue
            
            # 이미지가 충분하지 않으면 사용 가능한 만큼만
            num_images = min(num_images, len(available_images))
            selected_images = random.sample(available_images, num_images)
            
            # 게시글 작성자 가져오기
            user = User.query.get(post.user_id)
            if not user:
                print(f"    ⚠ Post {post.post_id}의 작성자를 찾을 수 없습니다. 건너뜁니다.")
                continue
            
            # 사용자 토큰 확인
            user_token = user_tokens.get(user.email)
            if not user_token:
                print(f"    ⚠ {user.email}의 토큰이 없습니다. 건너뜁니다.")
                continue
            
            # 이미지 경로 리스트 준비
            image_paths = [str(img) for img in selected_images]
            
            # API를 통해 이미지 업로드 (PUT 요청으로 기존 게시글에 이미지 추가)
            result = uploader.update_post_images(
                user_token=user_token,
                post_id=post.post_id,
                new_image_paths=image_paths
            )
            
            if result and result.get('message') == '게시글 수정 완료':
                uploaded_images = result.get('uploaded_images', [])
                category_upload_count += len(uploaded_images)
                total_uploaded += len(uploaded_images)
            else:
                total_failed += len(image_paths)
                print(f"    ✗ Post {post.post_id} 업로드 실패")
        
        print(f"    ✓ {category_upload_count}개 이미지 업로드됨")
    
    # 검증: 업로드된 이미지 확인
    print(f"\n🔍 업로드 결과 검증 중...")
    db.session.expire_all()  # 캐시 무효화
    total_images_in_db = Image.query.count()
    posts_with_images = db.session.query(Post).join(Image).distinct().count()
    
    print(f"\n{'='*60}")
    print(f"✅ 이미지 업로드 완료 (API)")
    print(f"{'='*60}")
    print(f"  성공: {total_uploaded}개")
    if total_failed > 0:
        print(f"  실패: {total_failed}개")
    print(f"  DB 이미지 레코드: {total_images_in_db}개")
    print(f"  이미지가 있는 게시글: {posts_with_images}개")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # 직접 실행할 경우
    print("pytest를 사용하여 실행하세요:")
    print("pytest test/database/gen_images.py -v -s")