"""
모든 테스트 데이터를 한 번에 생성하는 마스터 스크립트
테스트 데이터베이스를 사용자, 게시글, 댓글로 채우려면 이것을 실행하세요
"""

import pytest
from apps.auth.models import User, AccountType
from apps.post.models import CategoryType, Post
from apps.reply.models import Reply
from apps.product.models import Product
from apps.place.models import Place
from apps.mention.models import Mention
from apps.notification.models import Notification
from apps.cosmetic.models import CosmeticItem, UserItem
from apps.payment.models import Order
from apps.route.models import Route

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


@pytest.mark.no_cleanup
def test_generate_all_data(fixture_app):
    """모든 테스트 데이터 생성: 사용자, 게시글, 댓글, 이미지"""
    import sys
    import os

    log = get_logger()

    # 임포트를 위해 테스트 디렉토리를 경로에 추가
    test_dir = os.path.dirname(os.path.abspath(__file__))
    if test_dir not in sys.path:
        sys.path.insert(0, test_dir)

    from apps.test.gen.clear_db import clear_database
    from apps.test.gen.gen_user import test_generate_users
    from apps.test.gen.gen_post import test_generate_posts
    from apps.test.gen.gen_reply import test_generate_replies
    from apps.test.gen.gen_images import (
        test_generate_profile_images,
        test_generate_images,
    )
    from apps.test.gen.gen_product import test_generate_products
    from apps.test.gen.gen_place import test_generate_places
    from apps.test.gen.gen_route import test_generate_routes
    from apps.test.gen.gen_mention import test_generate_mentions
    from apps.test.gen.gen_notification import test_generate_notifications
    from apps.test.gen.gen_cosmetic import test_generate_cosmetics

    with fixture_app.app_context():
        verbosity = fixture_app.config.get("VERBOSITY", 1)

        log.section("테스트 데이터 생성")

        # --reset-prev-data 옵션이 있는 경우에만 기존 데이터 정리
        if fixture_app.config.get("RESET_PREV_DATA", False):
            log.info("\n기존 데이터 정리...")
            clear_database(fixture_app)
        else:
            log.debug("기존 데이터 유지 (--reset-prev-data 옵션 없음)")

        # 데이터 생성 단계들은 각 함수에서 자체 로깅
        test_generate_users(fixture_app)
        test_generate_profile_images(fixture_app)
        test_generate_posts(fixture_app)
        test_generate_images(fixture_app)
        test_generate_replies(fixture_app)
        test_generate_products(fixture_app)
        test_generate_places(fixture_app)
        test_generate_routes(fixture_app)
        test_generate_mentions(fixture_app)
        test_generate_notifications(fixture_app)
        test_generate_cosmetics(fixture_app)

        # 요약
        total_users = User.query.count()
        total_posts = Post.query.count()
        total_routes = Route.query.count()
        total_replies = Reply.query.count()
        total_categories = len(CategoryType.ALL)
        total_products = Product.query.count()
        total_places = Place.query.count()
        total_mentions = Mention.query.count()
        total_notifications = Notification.query.count()
        total_cosmetic_items = CosmeticItem.query.count()
        total_user_items = UserItem.query.count()
        total_orders = Order.query.count()

        log.section("생성 완료")
        log.summary(
            {
                "총 사용자": f"{total_users}명",
                "총 게시글": f"{total_posts}개",
                "총 경로": f"{total_routes}개",
                "총 댓글": f"{total_replies}개",
                "총 카테고리": f"{total_categories}개",
                "총 제품": f"{total_products}개",
                "총 장소": f"{total_places}개",
                "총 멘션": f"{total_mentions}개",
                "총 알림": f"{total_notifications}개",
                "총 코스메틱": f"{total_cosmetic_items}개",
                "총 인벤토리": f"{total_user_items}개",
                "총 주문": f"{total_orders}개",
            }
        )
