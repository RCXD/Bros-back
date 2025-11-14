"""
게시글 이미지 생성기
"""
from pathlib import Path
import sys
import random

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from app.models.user import User
from app.models.post import Post
from app.models.category import Category
from app.models.image import Image
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.image_processing import resize_post_image, get_image_files
from helpers.image_api import ImageAPIClient
from helpers.auth import get_all_user_tokens


# 폴더와 카테고리 매핑
FOLDER_CATEGORY_MAP = {
    'daily': 'STORY',
    'route': 'ROUTE',
    'review': 'REVIEW',
    'report': 'REPORT'
}


def get_categorized_images(dummy_dir):
    """
    카테고리 폴더별로 정리된 이미지 가져오기
    
    Args:
        dummy_dir: 카테고리 폴더를 포함한 루트 디렉토리
        
    Returns:
        카테고리 이름을 이미지 파일 리스트에 매핑한 Dict
    """
    dummy_dir = Path(dummy_dir)
    folder_images = {}
    
    for folder_name, category_name in FOLDER_CATEGORY_MAP.items():
        folder_path = dummy_dir / folder_name
        if not folder_path.exists():
            continue
        
        images = get_image_files(folder_path, recursive=True)
        folder_images[category_name] = images
    
    return folder_images


def generate_post_images_direct(app_context, dummy_dir, storage_dir):
    """
    직접 파일 저장 방식으로 게시글 이미지 생성 (테스트 환경)
    
    Args:
        app_context: Flask 앱 컨텍스트
        dummy_dir: 카테고리별 더미 이미지가 있는 원본 디렉토리
        storage_dir: 처리된 이미지를 저장할 디렉토리
        
    Returns:
        Tuple of (성공 수, 실패 수)
    """
    with app_context:
        storage_dir = Path(storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 기존 게시글 이미지 레코드 삭제
        Image.query.delete()
        db.session.commit()
        
        posts = Post.query.all()
        if not posts:
            raise ValueError("게시글을 찾을 수 없습니다. 먼저 게시글을 생성하세요.")
        
        folder_images = get_categorized_images(dummy_dir)
        if not folder_images:
            raise FileNotFoundError(f"{dummy_dir}에서 카테고리별 이미지를 찾을 수 없습니다")
        
        # 카테고리별로 게시글 그룹화
        posts_by_category = {}
        for post in posts:
            category = Category.query.get(post.category_id)
            if category:
                cat_name = category.category_name
                posts_by_category.setdefault(cat_name, []).append(post)
        
        success = 0
        failed = 0
        
        for category_name, post_list in posts_by_category.items():
            if category_name not in folder_images:
                continue
            
            available_images = folder_images[category_name]
            if not available_images:
                continue
            
            for post in post_list:
                num_images = random.choice([0, 1, 1, 2, 2, 3])
                if num_images == 0:
                    continue
                
                num_images = min(num_images, len(available_images))
                selected_images = random.sample(available_images, num_images)
                
                user = User.query.get(post.user_id)
                if not user:
                    continue
                
                for image_file in selected_images:
                    image_record = Image(
                        post_id=post.post_id,
                        user_id=user.user_id,
                        directory=str(storage_dir),
                        original_image_name=image_file.name,
                        ext="png"
                    )
                    db.session.add(image_record)
                    db.session.flush()
                    
                    dest_path = storage_dir / f"{image_record.uuid}.png"
                    result = resize_post_image(image_file, dest_path)
                    
                    if result:
                        success += 1
                    else:
                        db.session.delete(image_record)
                        failed += 1
        
        db.session.commit()
        return success, failed


def generate_post_images_api(app_context, base_url, dummy_dir, num_users):
    """
    API 업로드 방식으로 게시글 이미지 생성 (프로덕션 환경)
    
    Args:
        app_context: Flask 앱 컨텍스트
        base_url: API 서버 URL
        dummy_dir: 카테고리별 더미 이미지가 있는 원본 디렉토리
        num_users: 토큰을 가져올 사용자 수
        
    Returns:
        Tuple of (성공 수, 실패 수)
    """
    with app_context:
        posts = Post.query.all()
        if not posts:
            raise ValueError("게시글을 찾을 수 없습니다. 먼저 게시글을 생성하세요.")
        
        folder_images = get_categorized_images(dummy_dir)
        if not folder_images:
            raise FileNotFoundError(f"{dummy_dir}에서 카테고리별 이미지를 찾을 수 없습니다")
        
        # 카테고리별로 게시글 그룹화
        posts_by_category = {}
        for post in posts:
            category = Category.query.get(post.category_id)
            if category:
                cat_name = category.category_name
                posts_by_category.setdefault(cat_name, []).append(post)
        
        user_tokens = get_all_user_tokens(base_url, num_users)
        if not user_tokens:
            raise RuntimeError("사용자 토큰 획득 실패")
        
        client = ImageAPIClient(base_url)
        
        success = 0
        failed = 0
        
        for category_name, post_list in posts_by_category.items():
            if category_name not in folder_images:
                continue
            
            available_images = folder_images[category_name]
            if not available_images:
                continue
            
            for post in post_list:
                num_images = random.choice([0, 1, 1, 2, 2, 3])
                if num_images == 0:
                    continue
                
                num_images = min(num_images, len(available_images))
                selected_images = random.sample(available_images, num_images)
                
                user = User.query.get(post.user_id)
                if not user:
                    continue
                
                user_token = user_tokens.get(user.email)
                if not user_token:
                    failed += len(selected_images)
                    continue
                
                image_paths = [str(img) for img in selected_images]
                result = client.update_post_images(user_token, post.post_id, image_paths)
                
                if result and result.get('message') == '게시글 수정 완료':
                    uploaded = result.get('uploaded_images', [])
                    success += len(uploaded)
                else:
                    failed += len(image_paths)
        
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
        success, failed = generate_post_images_direct(
            app.app_context(),
            config.dummy_post_img_dir,
            config.post_img_folder
        )
    else:
        success, failed = generate_post_images_api(
            app.app_context(),
            config.api_backend_url,
            config.dummy_post_img_dir,
            config.num_users
        )
    
    print(f"\n게시글 이미지: 성공 {success}개, 실패 {failed}개")
