import pytest
from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply
from datetime import datetime, timedelta
import random

try:
    from logger import get_logger
    from gen_reply_helper import get_sample_reply_contents
except ImportError:
    from test.database.logger import get_logger
    from test.database.gen_reply_helper import get_sample_reply_contents


@pytest.mark.no_cleanup
def test_generate_replies(fixture_app):
    """더미 댓글 레코드를 데이터베이스에 생성"""
    n_replies_per_post = 3  # 게시글당 평균 댓글 수
    
    log = get_logger()
    
    with fixture_app.app_context():
        log.info(f"\n[4/5] 댓글 생성")
        
        # 기존 사용자와 게시글 가져오기
        users = User.query.filter_by(account_type=AccountType.USER).all()
        posts = Post.query.all()
        
        if not users:
            log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("댓글을 생성할 사용자가 없습니다")
        
        if not posts:
            log.warning("  게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
            pytest.skip("댓글을 생성할 게시글이 없습니다")
        
        log.debug(f"  {len(users)}명 사용자, {len(posts)}개 게시글 발견")
        
        # 샘플 댓글 내용
        reply_contents = get_sample_reply_contents()
        
        # 각 게시글에 대한 댓글 생성
        replies = []
        
        for post in posts:
            num_replies = random.randint(1, n_replies_per_post * 2)
            post_base_time = post.created_at
            
            # 일반 댓글 생성
            main_replies = []
            for i in range(num_replies):
                reply = Reply(
                    post_id=post.post_id,
                    user_id=random.choice(users).user_id,
                    content=random.choice(reply_contents),
                    parent_id=None,  # 일반 댓글 (중첩 댓글 아님)
                    created_at=post_base_time + timedelta(hours=random.randint(1, 48)),
                )
                replies.append(reply)
                main_replies.append(reply)
            
            # ID를 얻기 위해 세션에 추가
            db.session.add_all(main_replies)
            db.session.flush()
            
            # 중첩 댓글 생성 (댓글에 대한 댓글)
            if len(main_replies) > 1:
                num_nested = random.randint(0, min(3, len(main_replies)))
                for _ in range(num_nested):
                    parent_reply = random.choice(main_replies)
                    nested_reply = Reply(
                        post_id=post.post_id,
                        user_id=random.choice(users).user_id,
                        content=random.choice(reply_contents),
                        parent_id=parent_reply.reply_id,
                        created_at=parent_reply.created_at + timedelta(hours=random.randint(1, 24)),
                    )
                    replies.append(nested_reply)
        
        db.session.add_all(replies)
        db.session.commit()
        
        # 통계 가져오기
        total_replies = Reply.query.count()
        main_replies_count = Reply.query.filter_by(parent_id=None).count()
        nested_replies_count = Reply.query.filter(Reply.parent_id.isnot(None)).count()
        
        log.success(f"  {total_replies}개 댓글 생성 완료")
        log.debug(f"  일반: {main_replies_count}개, 중첩: {nested_replies_count}개")
        log.debug(f"  게시글당 평균: {total_replies / len(posts):.1f}개")
