"""
알림 생성 유틸리티 함수들
각 이벤트 발생 시 자동으로 알림을 생성하기 위한 헬퍼 함수
"""
from apps.config.server import db
from apps.notification.models import Notification, NotificationType


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
    
    notification = Notification(
        type=NotificationType.POST_LIKE,
        from_user_id=from_user_id,
        to_user_id=post.user_id,
        post_id=post.post_id
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
    
    notification = Notification(
        type=NotificationType.FRIEND_REQUEST,
        from_user_id=from_user_id,
        to_user_id=to_user_id
    )
    
    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"친구 요청 알림 생성 실패: {e}")
        return None


def create_reply_notification(from_user_id, post):
    """
    댓글 알림 생성
    
    Args:
        from_user_id: 댓글을 작성한 사용자 ID
        post: Post 객체
    """
    # 자기 게시글에 댓글을 단 경우 알림 생성 안 함
    if from_user_id == post.user_id:
        return None
    
    notification = Notification(
        type=NotificationType.REPLY,
        from_user_id=from_user_id,
        to_user_id=post.user_id,
        post_id=post.post_id
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
    
    notification = Notification(
        type=NotificationType.REPLY_TO_REPLY,
        from_user_id=from_user_id,
        to_user_id=parent_reply.user_id,
        post_id=parent_reply.post_id,
        reply_id=reply_id
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
    
    notification = Notification(
        type=NotificationType.PRODUCT_RECOMMENDATION,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        product_id=product_id
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
    
    notification = Notification(
        type=NotificationType.REPLY_LIKE,
        from_user_id=from_user_id,
        to_user_id=reply.user_id,
        reply_id=reply.reply_id,
        post_id=reply.post_id
    )
    
    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"댓글 좋아요 알림 생성 실패: {e}")
        return None


def create_mention_notification(from_user_id, mentioned_user_id, post_id=None, reply_id=None, mention_id=None):
    """
    멘션 알림 생성
    
    Args:
        from_user_id: 멘션한 사용자 ID
        mentioned_user_id: 멘션된 사용자 ID
        post_id: 관련 게시글 ID (선택)
        reply_id: 관련 댓글 ID (선택)
        mention_id: 멘션 ID (선택)
    """
    # 자기 자신을 멘션한 경우 알림 생성 안 함
    if from_user_id == mentioned_user_id:
        return None
    
    notification = Notification(
        type=NotificationType.MENTION,
        from_user_id=from_user_id,
        to_user_id=mentioned_user_id,
        post_id=post_id,
        reply_id=reply_id,
        mention_id=mention_id
    )
    
    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"멘션 알림 생성 실패: {e}")
        return None


def create_follow_notification(from_user_id, to_user_id):
    """
    팔로우 알림 생성
    
    Args:
        from_user_id: 팔로우를 시작한 사용자 ID
        to_user_id: 팔로우 대상 사용자 ID
    """
    # 자기 자신을 팔로우할 수 없음
    if from_user_id == to_user_id:
        return None
    
    notification = Notification(
        type=NotificationType.FOLLOW,
        from_user_id=from_user_id,
        to_user_id=to_user_id
    )
    
    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"팔로우 알림 생성 실패: {e}")
        return None
