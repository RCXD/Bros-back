import pytest
from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.category import Category
from datetime import datetime, timedelta
import random
import json
import os


@pytest.mark.no_cleanup
def test_generate_posts(fixture_app):
    """cat*.json 파일에서 게시글 데이터를 로드하여 데이터베이스에 생성"""
    
    with fixture_app.app_context():
        # 기존 사용자 가져오기 및 username -> user_id 매핑 생성
        users = User.query.filter_by(account_type=AccountType.USER).all()
        
        if not users:
            print("\n⚠ 사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("게시글을 생성할 사용자가 없습니다")
        
        # username -> user_id 매핑 생성
        username_to_userid = {user.username: user.user_id for user in users}
        
        # 카테고리가 없으면 생성
        category_names = ["STORY", "ROUTE", "REVIEW", "REPORT"]
        categories = {}
        
        for idx, name in enumerate(category_names):
            category = Category.query.filter_by(category_name=name).first()
            if not category:
                category = Category(category_name=name)
                db.session.add(category)
                db.session.flush()  # ID를 얻기 위해 flush
            categories[idx] = category.category_id
        
        db.session.commit()
        
        # JSON 파일에서 게시글 데이터 로드
        json_dir = os.path.join(os.path.dirname(__file__), "json")
        posts = []
        base_time = datetime.now() - timedelta(days=60)
        total_posts = 0
        
        for cat_idx in range(4):
            json_file = os.path.join(json_dir, f"cat{cat_idx}.json")
            
            if not os.path.exists(json_file):
                print(f"⚠ {json_file} 파일이 없습니다. 건너뜁니다.")
                continue
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            post_list = data.get("posts", [])
            category_name = category_names[cat_idx]
            
            for post_data in post_list:
                # username을 user_id로 변환 (없으면 랜덤 선택)
                username = post_data.get("username", "")
                user_id = username_to_userid.get(username)
                
                if not user_id:
                    user_id = random.choice(users).user_id
                
                # Post 객체 생성
                post = Post(
                    user_id=user_id,
                    category_id=categories[cat_idx],
                    content=post_data.get("content", ""),
                    view_counts=random.randint(0, 1000),
                    created_at=base_time + timedelta(days=random.randint(0, 60)),
                )
                posts.append(post)
            
            total_posts += len(post_list)
            print(f"✓ {category_name}: {len(post_list)}개 게시글 로드")
        
        # 데이터베이스에 저장
        db.session.add_all(posts)
        db.session.commit()
        
        # 게시글이 생성되었는지 확인
        final_count = Post.query.count()
        assert final_count >= total_posts
        
        print(f"\n✓ 총 {total_posts}개 게시글 생성 완료")
        print(f"  데이터베이스의 총 게시글 수: {final_count}")
