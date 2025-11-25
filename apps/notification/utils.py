"""
알림 생성 유틸리티 함수들
각 이벤트 발생 시 자동으로 알림을 생성하기 위한 헬퍼 함수
"""

from apps.config.server import db
from apps.notification.models import (
    Notification,
    NotificationType,
    NotificationItemType,
)
from apps.auth.models import User


def create_post_like_notification(from_user_id, post):
    """
    게시글 좋아요 알림 생성

    Args:
        from_user_id: 좋아요를 누른 사용자 ID
        post: Post 객체
    """
    # 자기 자신의 게시글에 좋아요를 누른 경우 알림 생성 안 함
    if from_user_id == post.user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.POST_LIKE,
        from_user_id=from_user_id,
        to_user_id=post.user_id,
        item_type=NotificationItemType.POST,
        item_id=post.post_id,
        message=f"{username}님이 회원님의 게시글을 좋아합니다.",
        # url=f"/post/{post.post_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"게시글 좋아요 알림 생성 실패: {e}")
        return None


def create_friend_request_notification(from_user_id, to_user_id):
    """
    친구 등록 알림 생성

    Args:
        from_user_id: 친구 요청을 보낸 사용자 ID
        to_user_id: 친구 요청을 받은 사용자 ID
    """
    # 자기 자신에게 친구 요청을 보낼 수 없음
    if from_user_id == to_user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.FRIEND_REQUEST,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        item_type=NotificationItemType.USER,
        item_id=from_user_id,
        message=f"{username}님이 당신에게 친구 요청을 보냈습니다.",
        # url=f"/user/{from_user_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"친구 요청 알림 생성 실패: {e}")
        return None


def create_reply_notification(from_user_id, post, reply_id=None):
    """
    댓글 알림 생성

    Args:
        from_user_id: 댓글을 작성한 사용자 ID
        post: Post 객체
        reply_id: 댓글 ID (선택)
    """
    # 자기 게시글에 댓글을 단 경우 알림 생성 안 함
    if from_user_id == post.user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.REPLY,
        from_user_id=from_user_id,
        to_user_id=post.user_id,
        item_type=NotificationItemType.POST,
        item_id=post.post_id,
        message=f"{username}님이 회원님의 게시글에 댓글을 남겼습니다.",
        # url=f"/post/{post.post_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"댓글 알림 생성 실패: {e}")
        return None


def create_reply_to_reply_notification(from_user_id, parent_reply, reply_id):
    """
    대댓글 알림 생성

    Args:
        from_user_id: 대댓글을 작성한 사용자 ID
        parent_reply: 부모 댓글 Reply 객체
        reply_id: 새로 작성된 대댓글 ID
    """
    # 자기 댓글에 대댓글을 단 경우 알림 생성 안 함
    if from_user_id == parent_reply.user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.REPLY_TO_REPLY,
        from_user_id=from_user_id,
        to_user_id=parent_reply.user_id,
        item_type=NotificationItemType.REPLY,
        item_id=parent_reply.reply_id,
        message=f"{username}님이 회원님의 댓글에 대댓글을 남겼습니다.",
        # url=f"/post/{parent_reply.post_id}?reply={parent_reply.reply_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"대댓글 알림 생성 실패: {e}")
        return None


def create_product_recommendation_notification(from_user_id, to_user_id, product_id):
    """
    상품 추천 알림 생성

    Args:
        from_user_id: 상품을 추천한 사용자 ID
        to_user_id: 상품 추천을 받은 사용자 ID
        product_id: 추천된 상품 ID
    """
    # 자기 자신에게 추천할 수 없음
    if from_user_id == to_user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.PRODUCT_RECOMMENDATION,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        item_type=NotificationItemType.PRODUCT,
        item_id=product_id,
        message=f"{username}님이 당신에게 상품을 추천했습니다.",
        # url=f"/product/{product_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"상품 추천 알림 생성 실패: {e}")
        return None


def create_reply_like_notification(from_user_id, reply):
    """
    댓글 좋아요 알림 생성

    Args:
        from_user_id: 좋아요를 누른 사용자 ID
        reply: Reply 객체
    """
    # 자기 댓글에 좋아요를 누른 경우 알림 생성 안 함
    if from_user_id == reply.user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.REPLY_LIKE,
        from_user_id=from_user_id,
        to_user_id=reply.user_id,
        item_type=NotificationItemType.REPLY,
        item_id=reply.reply_id,
        message=f"{username}님이 회원님의 댓글을 좋아합니다.",
        # url=f"/post/{reply.post_id}?reply={reply.reply_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"댓글 좋아요 알림 생성 실패: {e}")
        return None


def create_mention_notification(from_user_id, mentioned_user_id, mention):
    """
    멘션 알림 생성

    Args:
        from_user_id: 멘션한 사용자 ID
        mentioned_user_id: 멘션된 사용자 ID
        mention: Mention 객체
    """
    # 자기 자신을 멘션한 경우 알림 생성 안 함
    if from_user_id == mentioned_user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    # mention의 item_type을 NotificationItemType으로 변환
    from apps.mention.models import MentionItemType

    if mention.item_type == MentionItemType.POST:
        notification_item_type = NotificationItemType.POST
    elif mention.item_type == MentionItemType.REPLY:
        notification_item_type = NotificationItemType.REPLY
    else:
        notification_item_type = NotificationItemType.POST  # 기본값

    # URL 생성 (mention의 item_type에 따라)
    # mention_url = f"/post/{mention.item_id}" if mention.item_type == MentionItemType.POST else f"/post/{mention.item_id}?reply={mention.item_id}"

    notification = Notification(
        type=NotificationType.MENTION,
        from_user_id=from_user_id,
        to_user_id=mentioned_user_id,
        item_type=notification_item_type,
        item_id=mention.item_id,
        message=f"{username}님이 당신을 멘션했습니다.",
        # url=mention_url,  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"멘션 알림 생성 실패: {e}")
        return None


def create_follow_notification(from_user_id, to_user_id, follow_id=None):
    """
    팔로우 알림 생성

    Args:
        from_user_id: 팔로우를 시작한 사용자 ID
        to_user_id: 팔로우 대상 사용자 ID
        follow_id: Follow ID (선택)
    """
    # 자기 자신을 팔로우할 수 없음
    if from_user_id == to_user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.FOLLOW,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        item_type=(
            NotificationItemType.USER
            if follow_id is None
            else NotificationItemType.FOLLOW
        ),
        item_id=from_user_id if follow_id is None else follow_id,
        message=f"{username}님이 당신을 팔로우했습니다.",
        # url=f"/user/{from_user_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"팔로우 알림 생성 실패: {e}")
        return None


def create_unfollow_notification(from_user_id, to_user_id):
    """
    언팔로우 알림 생성

    Args:
        from_user_id: 언팔로우를 한 사용자 ID
        to_user_id: 언팔로우 대상 사용자 ID
    """
    # 자기 자신을 언팔로우할 수 없음
    if from_user_id == to_user_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(from_user_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.UNFOLLOW,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        item_type=NotificationItemType.USER,
        item_id=from_user_id,
        message=f"{username}님이 당신을 언팔로우했습니다.",
        # url=f"/user/{from_user_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"언팔로우 알림 생성 실패: {e}")
        return None


def create_new_post_notification(follower_user_id, post_author_id, post, feed_item):
    """
    새 게시글 알림 생성 (팔로워에게)

    Args:
        follower_user_id: 알림을 받을 팔로워 사용자 ID
        post_author_id: 게시글 작성자 ID
        post: Post 객체
        feed_item: FeedItem 객체

    Returns:
        Notification: 생성된 알림 객체
    """
    # 자기 자신에게는 알림 생성 안 함
    if follower_user_id == post_author_id:
        return None

    # 사용자 정보 조회
    from_user = User.query.get(post_author_id)
    username = from_user.nickname if from_user and from_user.nickname else "Someone"

    notification = Notification(
        type=NotificationType.REPLY,  # 새 게시글은 REPLY 타입 사용 (또는 새로운 타입 추가 가능)
        from_user_id=post_author_id,
        to_user_id=follower_user_id,
        item_type=NotificationItemType.POST,
        item_id=post.post_id,
        message=f"{username}님이 새 게시글을 작성했습니다.",
        # url=f"/post/{post.post_id}",  # 추후 DB 컬럼 추가 시 활성화
    )

    db.session.add(notification)
    try:
        db.session.flush()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"새 게시글 알림 생성 실패: {e}")
        return None
