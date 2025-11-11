"""
테스트 데이터베이스에서 생성된 게시글 확인
"""
import pytest
from app.extensions import db
from app.models.post import Post
from app.models.category import Category


@pytest.mark.no_cleanup
def test_verify_posts_exist(fixture_app):
    """데이터베이스에 게시글이 존재하는지 확인"""
    with fixture_app.app_context():
        posts = Post.query.all()
        categories = Category.query.all()
        
        print(f"\n--- 데이터베이스 내용 ---")
        print(f"총 게시글: {len(posts)}")
        print(f"총 카테고리: {len(categories)}")
        
        if categories:
            print("\n카테고리:")
            for category in categories:
                category_posts = Post.query.filter_by(category_id=category.category_id).count()
                print(f"  - {category.category_name}: {category_posts}개 게시글")
        
        if posts:
            print(f"\n샘플 게시글 (처음 5개 표시):")
            for post in posts[:5]:
                print(f"  - 게시글 #{post.post_id}")
                print(f"    사용자 ID: {post.user_id}")
                print(f"    카테고리: {post.category.category_name if post.category else 'N/A'}")
                print(f"    내용: {post.content[:50]}...")
                print(f"    조회수: {post.view_counts}")
                print(f"    생성일: {post.created_at}")
                print()
