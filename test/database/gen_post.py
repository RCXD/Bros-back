import pytest
from app_legacy.extensions import db
from app_legacy.models.user import User, AccountType
from app_legacy.models.post import Post
from datetime import datetime, timedelta
import random
import os

try:
    from logger import get_logger
    from gen_post_helper import (
        ensure_categories,
        load_posts_from_json,
        create_username_to_userid_map,
    )
except ImportError:
    from test.database.logger import get_logger
    from test.database.gen_post_helper import (
        ensure_categories,
        load_posts_from_json,
        create_username_to_userid_map,
    )


@pytest.mark.no_cleanup
def test_generate_posts(fixture_app):
    """cat*.json 파일에서 게시글 데이터를 로드하여 데이터베이스에 생성"""

    log = get_logger()

    with fixture_app.app_context():
        log.info(f"\n[3/5] 게시글 생성")

        # 기존 사용자 가져오기
        users = User.query.filter_by(account_type=AccountType.USER).all()

        if not users:
            log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("게시글을 생성할 사용자가 없습니다")

        log.debug(f"  {len(users)}명의 사용자 발견")

        # username -> user_id 매핑 생성
        username_to_userid = create_username_to_userid_map(users)

        # 카테고리 확인/생성
        category_names = ["STORY", "ROUTE", "REVIEW", "REPORT"]
        categories = ensure_categories(category_names)
        log.debug(f"  {len(categories)}개 카테고리 준비 완료")

        # JSON 파일에서 게시글 데이터 로드
        json_dir = os.path.join(os.path.dirname(__file__), "json")
        posts = []
        base_time = datetime.now() - timedelta(days=60)
        total_posts = 0

        for cat_idx in range(4):
            post_list = load_posts_from_json(json_dir, cat_idx)

            if not post_list:
                log.debug(f"  {category_names[cat_idx]}: JSON 파일 없음, 건너뜀")
                continue

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
            log.debug(f"  {category_name}: {len(post_list)}개 게시글 로드")

        # 데이터베이스에 저장
        if posts:
            db.session.add_all(posts)
            db.session.commit()

            # 게시글이 생성되었는지 확인
            final_count = Post.query.count()
            log.success(f"  {total_posts}개 게시글 생성 완료 (DB 총: {final_count}개)")
        else:
            log.warning("  생성할 게시글이 없습니다")
