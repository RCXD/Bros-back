"""
게시글 데이터 생성기
"""
from pathlib import Path
import sys
import json
import random
from datetime import datetime, timedelta

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.extensions import db
from app.models.user import User, AccountType
from app.models.post import Post
from app.models.category import Category


def generate_posts(app_context, json_file_path):
    """
    JSON 데이터 파일에서 게시글 생성
    
    Args:
        app_context: Flask 앱 컨텍스트
        json_file_path: 게시글 데이터를 포함한 JSON 파일 경로
        
    Returns:
        생성된 게시글 수
    """
    with app_context:
        users = User.query.filter_by(account_type=AccountType.USER).all()
        if not users:
            raise ValueError("사용자를 찾을 수 없습니다. 먼저 사용자를 생성하세요.")
        
        username_to_userid = {user.username: user.user_id for user in users}
        
        # 카테고리가 존재하는지 확인
        category_names = ["STORY", "ROUTE", "REVIEW", "REPORT"]
        categories = {}
        
        for name in category_names:
            category = Category.query.filter_by(category_name=name).first()
            if not category:
                category = Category(category_name=name)
                db.session.add(category)
                db.session.flush()
            categories[name] = category.category_id
        
        db.session.commit()
        
        # JSON 데이터 로드
        json_path = Path(json_file_path)
        if not json_path.exists():
            raise FileNotFoundError(f"게시글 데이터 파일을 찾을 수 없습니다: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        posts = []
        base_time = datetime.now() - timedelta(days=60)
        
        for post_data in data.get("posts", []):
            username = post_data.get("username", "")
            user_id = username_to_userid.get(username, random.choice(users).user_id)
            
            category_name = post_data.get("category", "STORY")
            category_id = categories.get(category_name, categories["STORY"])
            
            post = Post(
                user_id=user_id,
                category_id=category_id,
                content=post_data.get("content", ""),
                view_counts=random.randint(0, 1000),
                created_at=base_time + timedelta(days=random.randint(0, 60)),
            )
            posts.append(post)
        
        db.session.add_all(posts)
        db.session.commit()
        
        return len(posts)


if __name__ == "__main__":
    from app import create_app
    from config import GeneratorConfig
    
    config = GeneratorConfig(use_test_env='--test' in sys.argv)
    config.print_config()
    
    app = create_app()
    
    with app.app_context():
        count = generate_posts(app.app_context(), config.post_json_path)
        print(f"\n생성됨: 게시글 {count}개")
