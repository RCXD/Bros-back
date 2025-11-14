"""
댓글 데이터 생성기
"""
from pathlib import Path
import sys
import random
from datetime import timedelta

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply


# 샘플 댓글 내용
REPLY_CONTENTS = [
    "좋은 정보 감사합니다",
    "저도 그렇게 생각해요",
    "도움이 많이 되었어요",
    "공감합니다",
    "좋은 글이네요",
    "유용한 정보예요",
    "저도 궁금했던 내용인데 감사합니다",
    "완전 동의합니다",
    "이거 진짜 좋은 것 같아요",
    "추천드립니다",
    "저도 같은 경험이 있어요",
    "정말 유익한 정보네요",
    "감사합니다 참고할게요",
    "좋은 하루 보내세요",
]


def generate_replies(app_context, replies_per_post=3):
    """
    게시글에 대한 댓글 생성
    
    Args:
        app_context: Flask 앱 컨텍스트
        replies_per_post: 게시글당 평균 댓글 수
        
    Returns:
        생성된 댓글 수
    """
    with app_context:
        users = User.query.filter_by(account_type=AccountType.USER).all()
        posts = Post.query.all()
        
        if not users:
            raise ValueError("사용자를 찾을 수 없습니다. 먼저 사용자를 생성하세요.")
        if not posts:
            raise ValueError("게시글을 찾을 수 없습니다. 먼저 게시글을 생성하세요.")
        
        replies = []
        
        for post in posts:
            num_replies = random.randint(1, replies_per_post * 2)
            post_base_time = post.created_at
            
            # 일반 댓글 생성
            main_replies = []
            for _ in range(num_replies):
                reply = Reply(
                    post_id=post.post_id,
                    user_id=random.choice(users).user_id,
                    content=random.choice(REPLY_CONTENTS),
                    parent_id=None,
                    created_at=post_base_time + timedelta(hours=random.randint(1, 48)),
                )
                replies.append(reply)
                main_replies.append(reply)
            
            db.session.add_all(main_replies)
            db.session.flush()
            
            # 중첩 댓글 생성
            if len(main_replies) > 1:
                num_nested = random.randint(0, min(3, len(main_replies)))
                for _ in range(num_nested):
                    parent_reply = random.choice(main_replies)
                    nested_reply = Reply(
                        post_id=post.post_id,
                        user_id=random.choice(users).user_id,
                        content=random.choice(REPLY_CONTENTS),
                        parent_id=parent_reply.reply_id,
                        created_at=parent_reply.created_at + timedelta(hours=random.randint(1, 24)),
                    )
                    replies.append(nested_reply)
        
        db.session.add_all(replies)
        db.session.commit()
        
        return len(replies)


if __name__ == "__main__":
    from app import create_app
    from config import GeneratorConfig
    
    config = GeneratorConfig(use_test_env='--test' in sys.argv)
    config.print_config()
    
    app = create_app()
    
    with app.app_context():
        count = generate_replies(app.app_context())
        print(f"\n생성됨: 댓글 {count}개")
