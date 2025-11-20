"""
알림 더미 데이터 생성
LOCAL 환경: DB 직접 접근
PROD 환경: API 호출
"""

import pytest
import json
import os
import random
from datetime import datetime, timedelta

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


def load_notification_data(json_path):
    """notification_data.json에서 알림 데이터 로드"""
    if not os.path.exists(json_path):
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("notifications", [])


def create_notification_db(
    app, notification_data, username_to_userid, post_map, reply_map
):
    """DB 직접 접근으로 알림 생성 (LOCAL)"""
    from apps.config.server import db
    from apps.notification.models import Notification, NotificationType
    from apps.user.models import Follow
    from apps.post.models import PostLike
    from apps.reply.models import Reply, ReplyLike

    log = get_logger()
    notifications = []

    for item in notification_data:
        notif_type = item.get("type")
        from_username = item.get("from_user")
        to_username = item.get("to_user")

        from_user_id = username_to_userid.get(from_username)
        to_user_id = username_to_userid.get(to_username)

        if not from_user_id or not to_user_id:
            log.debug(f"  사용자 없음: {from_username} -> {to_username}, 건너뜀")
            continue

        # 알림 타입별 처리
        post_id = None
        reply_id = None

        try:
            notification_type = NotificationType[notif_type]
        except KeyError:
            log.debug(f"  알 수 없는 알림 타입: {notif_type}, 건너뜀")
            continue

        # FOLLOW: 팔로우 관계 생성
        if notification_type == NotificationType.FOLLOW:
            existing_follow = Follow.query.filter_by(
                follower_id=from_user_id, followed_id=to_user_id
            ).first()

            if not existing_follow:
                follow = Follow(
                    follower_id=from_user_id,
                    followed_id=to_user_id,
                    created_at=datetime.utcnow()
                    - timedelta(days=random.randint(0, 30)),
                )
                db.session.add(follow)

        # POST_LIKE: 게시글 좋아요 생성
        elif notification_type == NotificationType.POST_LIKE:
            target_username = item.get("target_post_username")
            target_user_id = username_to_userid.get(target_username)

            if target_user_id and target_user_id in post_map:
                posts = post_map[target_user_id]
                if posts:
                    post_id = random.choice(posts)

                    existing_like = PostLike.query.filter_by(
                        user_id=from_user_id, post_id=post_id
                    ).first()

                    if not existing_like:
                        post_like = PostLike(
                            user_id=from_user_id,
                            post_id=post_id,
                            created_at=datetime.utcnow()
                            - timedelta(days=random.randint(0, 30)),
                        )
                        db.session.add(post_like)

        # REPLY: 댓글 생성
        elif notification_type == NotificationType.REPLY:
            target_username = item.get("target_post_username")
            target_user_id = username_to_userid.get(target_username)
            reply_content = item.get("reply_content", "댓글 내용")

            if target_user_id and target_user_id in post_map:
                posts = post_map[target_user_id]
                if posts:
                    post_id = random.choice(posts)

                    reply = Reply(
                        user_id=from_user_id,
                        post_id=post_id,
                        parent_id=None,
                        content=reply_content,
                        created_at=datetime.utcnow()
                        - timedelta(days=random.randint(0, 30)),
                    )
                    db.session.add(reply)
                    db.session.flush()  # reply_id 생성
                    reply_id = reply.reply_id

        # REPLY_TO_REPLY: 대댓글 생성
        elif notification_type == NotificationType.REPLY_TO_REPLY:
            target_username = item.get("target_post_username")
            parent_username = item.get("parent_reply_username")
            reply_content = item.get("reply_content", "대댓글 내용")

            target_user_id = username_to_userid.get(target_username)

            if target_user_id and target_user_id in post_map:
                posts = post_map[target_user_id]
                if posts:
                    post_id = random.choice(posts)

                    # 해당 게시글의 댓글 찾기
                    parent_replies = Reply.query.filter_by(
                        post_id=post_id, parent_id=None
                    ).all()
                    if parent_replies:
                        parent_reply = random.choice(parent_replies)

                        reply = Reply(
                            user_id=from_user_id,
                            post_id=post_id,
                            parent_id=parent_reply.reply_id,
                            content=reply_content,
                            created_at=datetime.utcnow()
                            - timedelta(days=random.randint(0, 30)),
                        )
                        db.session.add(reply)
                        db.session.flush()
                        reply_id = reply.reply_id

        # REPLY_LIKE: 댓글 좋아요 생성
        elif notification_type == NotificationType.REPLY_LIKE:
            target_username = item.get("target_post_username")
            reply_username = item.get("target_reply_username")

            target_user_id = username_to_userid.get(target_username)
            reply_user_id = username_to_userid.get(reply_username)

            if target_user_id and target_user_id in post_map:
                posts = post_map[target_user_id]
                if posts:
                    post_id = random.choice(posts)

                    # 해당 게시글의 댓글 중 reply_user_id가 작성한 것 찾기
                    replies = Reply.query.filter_by(
                        post_id=post_id, user_id=reply_user_id
                    ).all()
                    if replies:
                        reply = random.choice(replies)
                        reply_id = reply.reply_id

                        existing_like = ReplyLike.query.filter_by(
                            user_id=from_user_id, reply_id=reply_id
                        ).first()

                        if not existing_like:
                            reply_like = ReplyLike(
                                user_id=from_user_id,
                                reply_id=reply_id,
                                created_at=datetime.utcnow()
                                - timedelta(days=random.randint(0, 30)),
                            )
                            db.session.add(reply_like)

        # 알림 생성
        notification = Notification(
            type=notification_type,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            post_id=post_id,
            reply_id=reply_id,
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            is_checked=random.choice([True, False]),
        )
        notifications.append(notification)

    if notifications:
        db.session.add_all(notifications)
        db.session.commit()
        log.success(f"  {len(notifications)}개 알림 생성 완료")
    else:
        log.warning("  생성할 알림이 없습니다")


def create_notification_api(app, notification_data, username_to_userid, api_url):
    """API 호출로 알림 생성 (PROD)"""
    import requests

    log = get_logger()
    log.warning("  API 기반 알림 생성은 아직 구현되지 않았습니다")
    # TODO: 각 알림 타입에 맞는 API 호출 구현
    # FOLLOW -> POST /user/{user_id}/follow
    # POST_LIKE -> POST /post/{post_id}/like
    # REPLY -> POST /reply
    # 등등


@pytest.mark.no_cleanup
def test_generate_notifications(fixture_app):
    """notification_data.json에서 알림 데이터를 로드하여 생성"""
    from apps.config.server import db
    from apps.auth.models import User
    from apps.post.models import Post
    from apps.reply.models import Reply

    log = get_logger()

    with fixture_app.app_context():
        log.info(f"\n[7/7] 알림 생성")

        # 환경 확인
        api_url = fixture_app.config.get("API_BACKEND_URL", "")
        use_test_env = fixture_app.config.get("TESTING", False)

        # 사용자 매핑 생성
        users = User.query.all()
        if not users:
            log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("알림을 생성할 사용자가 없습니다")

        username_to_userid = {user.username: user.user_id for user in users}
        log.debug(f"  {len(users)}명의 사용자 발견")

        # 게시글 매핑 생성
        posts = Post.query.all()
        if not posts:
            log.warning("  게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
            pytest.skip("알림을 생성할 게시글이 없습니다")

        post_map = {}
        for post in posts:
            if post.user_id not in post_map:
                post_map[post.user_id] = []
            post_map[post.user_id].append(post.post_id)

        log.debug(f"  {len(posts)}개의 게시글 발견")

        # 댓글 매핑 생성
        replies = Reply.query.all()
        reply_map = {}
        for reply in replies:
            if reply.user_id not in reply_map:
                reply_map[reply.user_id] = []
            reply_map[reply.user_id].append(reply.reply_id)

        log.debug(f"  {len(replies)}개의 댓글 발견")

        # JSON 데이터 로드
        json_path = os.path.join(
            os.path.dirname(__file__), "..", "json", "notification_data.json"
        )
        notification_data = load_notification_data(json_path)

        if not notification_data:
            log.warning("  notification_data.json 파일이 없거나 비어있습니다")
            return

        log.debug(f"  {len(notification_data)}개 알림 데이터 로드")

        # 환경에 따라 생성 방법 선택
        if use_test_env or not api_url:
            # LOCAL: DB 직접 접근
            log.debug("  LOCAL 환경: DB 직접 접근")
            create_notification_db(
                fixture_app, notification_data, username_to_userid, post_map, reply_map
            )
        else:
            # PROD: API 호출
            log.debug("  PROD 환경: API 호출")
            create_notification_api(
                fixture_app, notification_data, username_to_userid, api_url
            )
