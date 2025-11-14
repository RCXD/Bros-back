"""
모든 테스트 데이터를 한 번에 생성하는 마스터 스크립트
테스트 데이터베이스를 사용자, 게시글, 댓글로 채우려면 이것을 실행하세요
"""
import pytest
from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply
from app.models.category import Category


@pytest.mark.no_cleanup
def test_generate_all_data(fixture_app):
    """모든 테스트 데이터 생성: 사용자, 게시글, 댓글, 이미지"""
    import sys
    import os
    
    # 임포트를 위해 테스트 디렉토리를 경로에 추가
    test_dir = os.path.dirname(os.path.abspath(__file__))
    if test_dir not in sys.path:
        sys.path.insert(0, test_dir)
    
    from gen_user import test_generate_users
    from gen_post import test_generate_posts
    from gen_reply import test_generate_replies
    from gen_profile_images import test_generate_profile_images
    from gen_images import test_generate_images
    
    with fixture_app.app_context():
        print("\n" + "="*60)
        print("테스트 데이터 생성 중")
        print("="*60)
        
        # 기존 데이터 정리 (외래 키 제약 조건 처리)
        print("\n[0/5] 기존 데이터 정리 중...")
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))
        db.session.commit()
        print("✓ 기존 데이터 정리 완료")
        
        # 사용자 생성
        print("\n[1/5] 사용자 생성 중...")
        test_generate_users(fixture_app)
        
        # 프로필 이미지 할당
        print("\n[2/5] 프로필 이미지 할당 중...")
        test_generate_profile_images(fixture_app)
        
        # 게시글 생성
        print("\n[3/5] 게시글 생성 중...")
        test_generate_posts(fixture_app)
        
        # 게시글 이미지 할당
        print("\n[4/5] 게시글 이미지 할당 중...")
        test_generate_images(fixture_app)
        
        # 댓글 생성
        print("\n[5/5] 댓글 생성 중...")
        test_generate_replies(fixture_app)
        
        # 요약
        print("\n" + "="*60)
        print("요약")
        print("="*60)
        
        total_users = User.query.count()
        total_posts = Post.query.count()
        total_replies = Reply.query.count()
        total_categories = Category.query.count()
        
        print(f"✓ 총 사용자: {total_users}")
        print(f"✓ 총 게시글: {total_posts}")
        print(f"✓ 총 댓글: {total_replies}")
        print(f"✓ 총 카테고리: {total_categories}")
        print("\n✅ 모든 테스트 데이터 생성 완료!")
        print("="*60 + "\n")
