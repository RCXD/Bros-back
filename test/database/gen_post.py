import pytest
from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.category import Category
from datetime import datetime, timedelta
import random


@pytest.mark.no_cleanup
def test_generate_posts(fixture_app):
    """더미 게시글 레코드를 데이터베이스에 생성"""
    n_posts = 20
    
    with fixture_app.app_context():
        # 기존 사용자 가져오기
        users = User.query.filter_by(account_type=AccountType.USER).all()
        
        if not users:
            print("\n⚠ 사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("게시글을 생성할 사용자가 없습니다")
        
        # 카테고리가 없으면 생성
        category_names = ["STORY", "ROUTE", "REVIEW", "REPORT"]
        categories = []
        
        for name in category_names:
            category = Category.query.filter_by(category_name=name).first()
            if not category:
                category = Category(category_name=name)
                db.session.add(category)
            categories.append(category)
        
        db.session.commit()
        
        # 샘플 게시글 내용
        post_contents = [
            "오늘 자전거 타면서 좋은 경로 발견했어요! 공유합니다.",
            "이 구간 공사 중이니 우회하세요.",
            "자전거 도난 방지 팁 알려드립니다.",
            "추천할만한 자전거 가게 있나요?",
            "오늘 날씨 정말 좋네요! 라이딩 최고!",
            "한강 자전거길 정보 공유합니다.",
            "야간 라이딩 시 주의사항",
            "자전거 수리 방법 공유",
            "좋은 자전거 추천 부탁드립니다.",
            "안전 장비 착용 꼭 하세요!",
            "이 길 너무 위험해요. 조심하세요.",
            "자전거 동호회 회원 모집합니다.",
            "주말에 같이 라이딩 하실 분?",
            "자전거 보험 가입 추천드립니다.",
            "교통사고 났을 때 대처방법",
        ]
        
        # 게시글 생성
        posts = []
        base_time = datetime.now() - timedelta(days=30)
        
        for i in range(n_posts):
            post = Post(
                user_id=random.choice(users).user_id,
                category_id=random.choice(categories).category_id,
                content=random.choice(post_contents) + f" (Post #{i+1})",
                view_counts=random.randint(0, 500),
                created_at=base_time + timedelta(days=random.randint(0, 30)),
            )
            posts.append(post)
        
        db.session.add_all(posts)
        db.session.commit()
        
        # 게시글이 생성되었는지 확인
        assert Post.query.count() >= n_posts
        
        print(f"\n✓ 4개 카테고리 생성 완료: {', '.join(category_names)}")
        print(f"✓ {n_posts}개 게시글 생성 완료")
        print(f"  데이터베이스의 총 게시글 수: {Post.query.count()}")
