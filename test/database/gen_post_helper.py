"""
게시글 생성을 위한 헬퍼 함수들
"""
import os
import json
from app.extensions import db
from app.models.category import Category


def ensure_categories(category_names=None):
    """
    카테고리가 존재하는지 확인하고 없으면 생성
    
    Args:
        category_names: 카테고리 이름 리스트 (기본값: ["STORY", "ROUTE", "REVIEW", "REPORT"])
    
    Returns:
        dict: {index: category_id} 매핑
    """
    if category_names is None:
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
    return categories


def load_posts_from_json(json_dir, category_index):
    """
    JSON 파일에서 게시글 데이터 로드
    
    Args:
        json_dir: JSON 파일이 있는 디렉토리 경로
        category_index: 카테고리 인덱스 (0-3)
    
    Returns:
        list: 게시글 데이터 리스트 (없으면 빈 리스트)
    """
    json_file = os.path.join(json_dir, f"cat{category_index}.json")
    
    if not os.path.exists(json_file):
        return []
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("posts", [])
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠ {json_file} 로드 실패: {e}")
        return []


def create_username_to_userid_map(users):
    """
    사용자 리스트에서 username -> user_id 매핑 생성
    
    Args:
        users: User 객체 리스트
    
    Returns:
        dict: {username: user_id} 매핑
    """
    return {user.username: user.user_id for user in users}
