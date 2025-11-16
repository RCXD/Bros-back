"""
모든 테스트 데이터를 한 번에 생성하는 마스터 스크립트
테스트 데이터베이스를 사용자, 게시글, 댓글로 채우려면 이것을 실행하세요
"""
import pytest
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply
from app.models.category import Category

try:
    from logger import get_logger
except ImportError:
    from test.database.logger import get_logger


@pytest.mark.no_cleanup
def test_generate_all_data(fixture_app):
    """모든 테스트 데이터 생성: 사용자, 게시글, 댓글, 이미지"""
    import sys
    import os
    
    log = get_logger()
    
    # 임포트를 위해 테스트 디렉토리를 경로에 추가
    test_dir = os.path.dirname(os.path.abspath(__file__))
    if test_dir not in sys.path:
        sys.path.insert(0, test_dir)
    
    from clear_db import test_clear_database
    from gen_user import test_generate_users
    from gen_post import test_generate_posts
    from gen_reply import test_generate_replies
    from gen_images import test_generate_profile_images, test_generate_images
    
    with fixture_app.app_context():
        verbosity = fixture_app.config.get('VERBOSITY', 1)
        
        log.section("테스트 데이터 생성")
        
        # --reset-prev-data 옵션이 있는 경우에만 기존 데이터 정리
        if fixture_app.config.get('RESET_PREV_DATA', False):
            log.info("\n기존 데이터 정리...")
            test_clear_database(fixture_app)
        else:
            log.debug("기존 데이터 유지 (--reset-prev-data 옵션 없음)")
        
        # 데이터 생성 단계들은 각 함수에서 자체 로깅
        test_generate_users(fixture_app)
        test_generate_profile_images(fixture_app)
        test_generate_posts(fixture_app)
        test_generate_images(fixture_app)
        test_generate_replies(fixture_app)
        
        # 요약
        total_users = User.query.count()
        total_posts = Post.query.count()
        total_replies = Reply.query.count()
        total_categories = Category.query.count()
        
        log.section("생성 완료")
        log.summary({
            "총 사용자": f"{total_users}명",
            "총 게시글": f"{total_posts}개",
            "총 댓글": f"{total_replies}개",
            "총 카테고리": f"{total_categories}개"
        })
