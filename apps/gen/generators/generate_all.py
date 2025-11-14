"""
모든 테스트 데이터를 생성하는 마스터 스크립트
"""
from pathlib import Path
import sys

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db


def clear_database(app_context):
    """스키마는 유지하면서 데이터베이스의 모든 데이터 삭제"""
    with app_context:
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()


def generate_all(app_context, config, use_api=False):
    """
    모든 테스트 데이터 생성
    
    Args:
        app_context: Flask 앱 컨텍스트
        config: GeneratorConfig 인스턴스
        use_api: True이면 이미지 API 업로드, False이면 직접 저장
        
    Returns:
        생성 통계가 담긴 Dict
    """
    sys.path.insert(0, str(Path(__file__).parent))
    
    from gen_users import generate_users
    from gen_posts import generate_posts
    from gen_replies import generate_replies
    from gen_profile_images import (
        generate_profile_images_direct,
        generate_profile_images_api
    )
    from gen_post_images import (
        generate_post_images_direct,
        generate_post_images_api
    )
    
    stats = {}
    
    print("\n[1/5] 사용자 생성 중...")
    users, admins = generate_users(app_context, config.num_users, config.num_admins)
    stats['users'] = users
    stats['admins'] = admins
    print(f"생성됨: 사용자 {users}명, 관리자 {admins}명")
    
    print("\n[2/5] 프로필 이미지 생성 중...")
    if use_api:
        success, failed = generate_profile_images_api(
            app_context,
            config.api_backend_url,
            config.dummy_profile_img_dir,
            config.num_users
        )
    else:
        success, failed = generate_profile_images_direct(
            app_context,
            config.dummy_profile_img_dir,
            config.profile_img_folder
        )
    stats['profile_images'] = success
    print(f"생성됨: 프로필 이미지 {success}개 (실패: {failed}개)")
    
    print("\n[3/5] 게시글 생성 중...")
    posts = generate_posts(app_context, config.post_json_path)
    stats['posts'] = posts
    print(f"생성됨: 게시글 {posts}개")
    
    print("\n[4/5] 게시글 이미지 생성 중...")
    if use_api:
        success, failed = generate_post_images_api(
            app_context,
            config.api_backend_url,
            config.dummy_post_img_dir,
            config.num_users
        )
    else:
        success, failed = generate_post_images_direct(
            app_context,
            config.dummy_post_img_dir,
            config.post_img_folder
        )
    stats['post_images'] = success
    print(f"생성됨: 게시글 이미지 {success}개 (실패: {failed}개)")
    
    print("\n[5/5] 댓글 생성 중...")
    replies = generate_replies(app_context)
    stats['replies'] = replies
    print(f"생성됨: 댓글 {replies}개")
    
    return stats


if __name__ == "__main__":
    from app import create_app
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import GeneratorConfig
    
    use_test = '--test' in sys.argv
    use_api = '--api' in sys.argv
    clear = '--clear' in sys.argv
    
    config = GeneratorConfig(use_test_env=use_test)
    config.print_config()
    
    app = create_app()
    
    if clear:
        print("\n기존 데이터 삭제 중...")
        clear_database(app.app_context())
        print("데이터베이스 초기화 완료")
    
    print("\n데이터 생성 시작...")
    stats = generate_all(app.app_context(), config, use_api=use_api)
    
    print("\n" + "="*60)
    print("생성 요약")
    print("="*60)
    print(f"사용자: {stats['users']}명")
    print(f"관리자: {stats['admins']}명")
    print(f"프로필 이미지: {stats['profile_images']}개")
    print(f"게시글: {stats['posts']}개")
    print(f"게시글 이미지: {stats['post_images']}개")
    print(f"댓글: {stats['replies']}개")
    print("="*60)
