import pytest
from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply
from datetime import datetime, timedelta
import random


@pytest.mark.no_cleanup
def test_generate_replies(fixture_app):
    """더미 댓글 레코드를 데이터베이스에 생성"""
    n_replies_per_post = 3  # 게시글당 평균 댓글 수
    
    with fixture_app.app_context():
        # 기존 사용자와 게시글 가져오기
        users = User.query.filter_by(account_type=AccountType.USER).all()
        posts = Post.query.all()
        
        if not users:
            print("\n⚠ 사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("댓글을 생성할 사용자가 없습니다")
        
        if not posts:
            print("\n⚠ 게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
            pytest.skip("댓글을 생성할 게시글이 없습니다")
        
        # 샘플 댓글 내용
        reply_contents = [
            "좋은 정보 감사합니다!",
            "저도 그렇게 생각해요.",
            "도움이 많이 되었어요!",
            "공감합니다.",
            "좋은 글이네요!",
            "유용한 정보예요.",
            "저도 궁금했던 내용인데 감사합니다.",
            "완전 동의합니다!",
            "이거 진짜 좋은 것 같아요.",
            "추천드립니다!",
            "저도 같은 경험이 있어요.",
            "정말 유익한 정보네요.",
            "감사합니다! 참고할게요.",
            "좋은 하루 보내세요!",
            "함께해요!",
        ]
        
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
        main_replies = Reply.query.filter_by(parent_id=None).count()
        nested_replies = Reply.query.filter(Reply.parent_id.isnot(None)).count()
        
        print(f"\n✓ {total_replies}개 댓글 생성 완료")
        print(f"  - 일반 댓글: {main_replies}")
        print(f"  - 중첩 댓글: {nested_replies}")
        print(f"  - 게시글당 평균: {total_replies / len(posts):.1f}")
