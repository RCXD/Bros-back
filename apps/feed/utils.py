"""
피드 생성 유틸리티 함수들
팔로워들에게 자동으로 피드를 생성하기 위한 헬퍼 함수
"""

from apps.config.server import db
from apps.feed.models import FeedItem


def create_new_post_feed(user_id, post_id, post_user_id):
    """
    새 게시글 피드 생성 (팔로워에게)

    Args:
        user_id: 피드를 받을 사용자 ID (팔로워)
        post_id: 게시글 ID
        post_user_id: 게시글 작성자 ID

    Returns:
        FeedItem: 생성된 피드 아이템
    """
    # 자기 자신에게는 피드 생성 안 함
    if user_id == post_user_id:
        return None

    feed_item = FeedItem(
        user_id=user_id,
        feed_type="friend_post",
        related_post_id=post_id,
        related_user_id=post_user_id,
    )

    db.session.add(feed_item)
    try:
        db.session.flush()  # feed_id 생성
        return feed_item
    except Exception as e:
        db.session.rollback()
        print(f"피드 생성 실패: {e}")
        return None
