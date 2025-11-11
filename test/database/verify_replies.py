"""
테스트 데이터베이스에서 생성된 댓글 확인
"""
import pytest
from app.extensions import db
from app.models.reply import Reply
from app.models.post import Post


@pytest.mark.no_cleanup
def test_verify_replies_exist(fixture_app):
    """데이터베이스에 댓글이 존재하는지 확인"""
    with fixture_app.app_context():
        replies = Reply.query.all()
        main_replies = Reply.query.filter_by(parent_id=None).all()
        nested_replies = Reply.query.filter(Reply.parent_id.isnot(None)).all()
        posts = Post.query.all()
        
        print(f"\n--- 데이터베이스 내용 ---")
        print(f"총 댓글: {len(replies)}")
        print(f"  - 일반 댓글: {len(main_replies)}")
        print(f"  - 중첩 댓글: {len(nested_replies)}")
        
        if posts:
            print(f"\n게시글당 댓글 수:")
            for post in posts[:5]:  # 처음 5개 게시글만 표시
                post_replies = Reply.query.filter_by(post_id=post.post_id).count()
                print(f"  - 게시글 #{post.post_id}: {post_replies}개 댓글")
        
        if replies:
            print(f"\n샘플 댓글 (처음 5개 표시):")
            for reply in replies[:5]:
                indent = "    " if reply.parent_id else "  "
                reply_type = "↳ 중첩" if reply.parent_id else "일반"
                print(f"{indent}- {reply_type} 댓글 #{reply.reply_id}")
                print(f"{indent}  게시글 ID: {reply.post_id}")
                print(f"{indent}  사용자 ID: {reply.user_id}")
                print(f"{indent}  내용: {reply.content[:40]}...")
                if reply.parent_id:
                    print(f"{indent}  부모 댓글 ID: {reply.parent_id}")
                print()
