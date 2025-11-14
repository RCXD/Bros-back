"""
데이터베이스 검증 유틸리티
"""
from pathlib import Path
import sys

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply
from app.models.category import Category
from app.models.image import Image


def verify_all(app_context):
    """
    생성된 모든 데이터 검증
    
    Args:
        app_context: Flask 앱 컨텍스트
        
    Returns:
        검증 통계가 담긴 Dict
    """
    with app_context:
        stats = {}
        
        # 사용자
        total_users = User.query.count()
        regular_users = User.query.filter_by(account_type=AccountType.USER).count()
        admins = User.query.filter_by(account_type=AccountType.ADMIN).count()
        users_with_profile = User.query.filter(User.profile_img != None).count()
        
        stats['users'] = {
            'total': total_users,
            'regular': regular_users,
            'admins': admins,
            'with_profile_image': users_with_profile
        }
        
        # 게시글
        total_posts = Post.query.count()
        posts_by_category = {}
        for category in Category.query.all():
            count = Post.query.filter_by(category_id=category.category_id).count()
            posts_by_category[category.category_name] = count
        
        posts_with_images = db.session.query(Post).join(Image).distinct().count()
        
        stats['posts'] = {
            'total': total_posts,
            'by_category': posts_by_category,
            'with_images': posts_with_images
        }
        
        # 댓글
        total_replies = Reply.query.count()
        main_replies = Reply.query.filter_by(parent_id=None).count()
        nested_replies = Reply.query.filter(Reply.parent_id.isnot(None)).count()
        
        stats['replies'] = {
            'total': total_replies,
            'main': main_replies,
            'nested': nested_replies
        }
        
        # 이미지
        total_images = Image.query.count()
        profile_images = Image.query.filter(Image.post_id == None).count()
        post_images = Image.query.filter(Image.post_id != None).count()
        
        stats['images'] = {
            'total': total_images,
            'profile': profile_images,
            'post': post_images
        }
        
        # 카테고리
        stats['categories'] = Category.query.count()
        
        return stats


def print_verification_report(stats):
    """검증 리포트를 포맷에 맞춰 출력"""
    print("\n" + "="*60)
    print("데이터베이스 검증 리포트")
    print("="*60)
    
    print("\n사용자:")
    print(f"  총 사용자: {stats['users']['total']}명")
    print(f"  일반 사용자: {stats['users']['regular']}명")
    print(f"  관리자: {stats['users']['admins']}명")
    print(f"  프로필 이미지 있음: {stats['users']['with_profile_image']}명")
    
    print("\n게시글:")
    print(f"  총 게시글: {stats['posts']['total']}개")
    print(f"  이미지 있는 게시글: {stats['posts']['with_images']}개")
    print(f"  카테고리별:")
    for cat, count in stats['posts']['by_category'].items():
        print(f"    {cat}: {count}개")
    
    print("\n댓글:")
    print(f"  총 댓글: {stats['replies']['total']}개")
    print(f"  일반 댓글: {stats['replies']['main']}개")
    print(f"  중첩 댓글: {stats['replies']['nested']}개")
    
    print("\n이미지:")
    print(f"  총 이미지: {stats['images']['total']}개")
    print(f"  프로필 이미지: {stats['images']['profile']}개")
    print(f"  게시글 이미지: {stats['images']['post']}개")
    
    print(f"\n카테고리: {stats['categories']}개")
    print("="*60)


if __name__ == "__main__":
    from app import create_app
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import GeneratorConfig
    
    use_test = '--test' in sys.argv
    config = GeneratorConfig(use_test_env=use_test)
    config.print_config()
    
    app = create_app()
    
    stats = verify_all(app.app_context())
    print_verification_report(stats)
