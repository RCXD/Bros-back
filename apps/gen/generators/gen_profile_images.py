"""
프로필 이미지 생성기
"""
from pathlib import Path
import sys
import random

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from app.models.user import User
from app.models.image import Image
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.image_processing import resize_profile_image, get_image_files
from helpers.image_api import ImageAPIClient
from helpers.auth import get_all_user_tokens


def generate_profile_images_direct(app_context, dummy_dir, storage_dir):
    """
    직접 파일 저장 방식으로 프로필 이미지 생성 (테스트 환경)
    
    Args:
        app_context: Flask 앱 컨텍스트
        dummy_dir: 더미 이미지가 있는 원본 디렉토리
        storage_dir: 처리된 이미지를 저장할 디렉토리
        
    Returns:
        Tuple of (성공 수, 실패 수)
    """
    with app_context:
        storage_dir = Path(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 기존 프로필 이미지 레코드 삭제
        Image.query.filter(Image.post_id == None).delete()
        db.session.commit()
        
        users = User.query.all()
        if not users:
            raise ValueError("사용자를 찾을 수 없습니다. 먼저 사용자를 생성하세요.")
        
        profile_images = get_image_files(dummy_dir)
        if not profile_images:
            raise FileNotFoundError(f"{dummy_dir}에서 이미지를 찾을 수 없습니다")
        
        random.shuffle(profile_images)
        
        success = 0
        failed = 0
        
        for idx, user in enumerate(users):
            source_image = profile_images[idx % len(profile_images)]
            
            # Image 레코드 생성
            image_record = Image(
                post_id=None,
                user_id=user.user_id,
                directory=str(storage_dir),
                original_image_name=source_image.name,
                ext="png"
            )
            db.session.add(image_record)
            db.session.flush()
            
            # 이미지 처리 및 저장
            dest_path = storage_dir / f"{image_record.uuid}.png"
            result = resize_profile_image(source_image, dest_path)
            
            if result:
                user.profile_img = image_record.uuid
                success += 1
            else:
                db.session.delete(image_record)
                failed += 1
        
        db.session.commit()
        return success, failed


def generate_profile_images_api(app_context, base_url, dummy_dir, num_users):
    """
    API 업로드 방식으로 프로필 이미지 생성 (프로덕션 환경)
    
    Args:
        app_context: Flask 앱 컨텍스트
        base_url: API 서버 URL
        dummy_dir: 더미 이미지가 있는 원본 디렉토리
        num_users: 토큰을 가져올 사용자 수
        
    Returns:
        Tuple of (성공 수, 실패 수)
    """
    with app_context:
        users = User.query.all()
        if not users:
            raise ValueError("사용자를 찾을 수 없습니다. 먼저 사용자를 생성하세요.")
        
        profile_images = get_image_files(dummy_dir)
        if not profile_images:
            raise FileNotFoundError(f"{dummy_dir}에서 이미지를 찾을 수 없습니다")
        
        user_tokens = get_all_user_tokens(base_url, num_users)
        if not user_tokens:
            raise RuntimeError("사용자 토큰 획득 실패")
        
        client = ImageAPIClient(base_url)
        random.shuffle(profile_images)
        
        success = 0
        failed = 0
        
        for idx, user in enumerate(users):
            user_token = user_tokens.get(user.email)
            if not user_token:
                failed += 1
                continue
            
            source_image = profile_images[idx % len(profile_images)]
            result = client.upload_profile_image(user_token, str(source_image))
            
            if result and result.get('message') == '회원 정보가 수정되었습니다.':
                success += 1
            else:
                failed += 1
        
        db.session.expire_all()
        return success, failed


if __name__ == "__main__":
    from app import create_app
    from config import GeneratorConfig
    
    use_test = '--test' in sys.argv
    config = GeneratorConfig(use_test_env=use_test)
    config.print_config()
    
    app = create_app()
    
    if use_test:
        success, failed = generate_profile_images_direct(
            app.app_context(),
            config.dummy_profile_img_dir,
            config.profile_img_folder
        )
    else:
        success, failed = generate_profile_images_api(
            app.app_context(),
            config.api_backend_url,
            config.dummy_profile_img_dir,
            config.num_users
        )
    
    print(f"\n프로필 이미지: 성공 {success}개, 실패 {failed}개")
