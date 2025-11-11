"""
모든 테스트 데이터에 대한 종합 확인
데이터베이스에 생성된 모든 데이터의 요약을 표시합니다
"""
import pytest
from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.reply import Reply
from app.models.category import Category


@pytest.mark.no_cleanup
def test_verify_all_data(fixture_app):
    """데이터베이스의 모든 생성된 데이터 확인"""
    with fixture_app.app_context():
        # 모든 데이터 가져오기
        users = User.query.all()
        regular_users = User.query.filter_by(account_type=AccountType.USER).all()
        admins = User.query.filter_by(account_type=AccountType.ADMIN).all()
        posts = Post.query.all()
        replies = Reply.query.all()
        main_replies = Reply.query.filter_by(parent_id=None).all()
        nested_replies = Reply.query.filter(Reply.parent_id.isnot(None)).all()
        categories = Category.query.all()
        
        print("\n" + "="*60)
        print("데이터베이스 확인 보고서")
        print("="*60)
        
        # 사용자 섹션
        print(f"\n📊 사용자 (총 {len(users)}명)")
        print(f"  ├─ 일반 사용자: {len(regular_users)}명")
        print(f"  └─ 관리자: {len(admins)}명")
        
        if regular_users:
            print(f"\n  샘플 사용자:")
            for user in regular_users[:3]:
                print(f"    • {user.username} ({user.email})")
        
        # 카테고리 섹션
        print(f"\n📊 카테고리 (총 {len(categories)}개)")
        for category in categories:
            count = Post.query.filter_by(category_id=category.category_id).count()
            print(f"  • {category.category_name}: {count}개 게시글")
        
        # 게시글 섹션
        print(f"\n📊 게시글 (총 {len(posts)}개)")
        if posts:
            total_views = sum(post.view_counts for post in posts)
            avg_views = total_views / len(posts)
            print(f"  ├─ 총 조회수: {total_views}")
            print(f"  └─ 게시글당 평균 조회수: {avg_views:.1f}")
            
            print(f"\n  샘플 게시글:")
            for post in posts[:3]:
                replies_count = Reply.query.filter_by(post_id=post.post_id).count()
                print(f"    • 게시글 #{post.post_id}: {post.content[:40]}...")
                print(f"      카테고리: {post.category.category_name if post.category else 'N/A'}")
                print(f"      조회수: {post.view_counts}, 댓글: {replies_count}개")
        
        # 댓글 섹션
        print(f"\n📊 댓글 (총 {len(replies)}개)")
        print(f"  ├─ 일반 댓글: {len(main_replies)}개")
        print(f"  └─ 중첩 댓글: {len(nested_replies)}개")
        
        if posts:
            avg_replies = len(replies) / len(posts)
            print(f"  └─ 게시글당 평균 댓글: {avg_replies:.1f}개")
        
        # 상태 확인
        print("\n" + "="*60)
        if users and posts and replies and categories:
            print("✅ 테스트 데이터베이스가 완전히 채워졌습니다")
        elif not users:
            print("⚠️  경고: 사용자를 찾을 수 없습니다. gen_user.py를 실행하세요")
        elif not posts:
            print("⚠️  경고: 게시글을 찾을 수 없습니다. gen_post.py를 실행하세요")
        elif not replies:
            print("⚠️  경고: 댓글을 찾을 수 없습니다. gen_reply.py를 실행하세요")
        else:
            print("ℹ️  데이터베이스에 일부 데이터가 있지만 불완전할 수 있습니다")
        print("="*60 + "\n")
