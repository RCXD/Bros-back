"""
멘션 더미 데이터 생성
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


def load_mention_data(json_path):
    """mention_data.json에서 멘션 데이터 로드"""
    if not os.path.exists(json_path):
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("mentions", [])


def create_mention_db(app, mention_data, username_to_userid, post_map, reply_map):
    """DB 직접 접근으로 멘션 생성 (LOCAL)"""
    from apps.config.server import db
    from apps.mention.models import Mention, MentionItemType
    from apps.notification.models import (
        Notification,
        NotificationType,
        NotificationItemType,
    )

    log = get_logger()
    mentions = []

    for item in mention_data:
        mentioner_username = item.get("mentioner")
        mentioned_username = item.get("mentioned_user")
        target_type = item.get("target_type")  # "post" or "reply"

        mentioner_id = username_to_userid.get(mentioner_username)
        mentioned_id = username_to_userid.get(mentioned_username)

        if not mentioner_id or not mentioned_id:
            log.debug(
                f"  사용자 없음: {mentioner_username} -> {mentioned_username}, 건너뜀"
            )
            continue

        # 대상 찾기
        item_id = None
        mention_item_type = None

        if target_type == "post":
            target_username = item.get("target_username")
            target_user_id = username_to_userid.get(target_username)
            if target_user_id and target_user_id in post_map:
                posts = post_map[target_user_id]
                if posts:
                    item_id = random.choice(posts)
                    mention_item_type = MentionItemType.POST
        elif target_type == "reply":
            parent_username = item.get("parent_post_username")
            parent_user_id = username_to_userid.get(parent_username)
            if parent_user_id and parent_user_id in reply_map:
                replies = reply_map[parent_user_id]
                if replies:
                    item_id = random.choice(replies)
                    mention_item_type = MentionItemType.REPLY

        if not item_id or not mention_item_type:
            log.debug(f"  대상 없음: {target_type} for {mentioner_username}, 건너뜀")
            continue

        # 중복 확인
        existing = Mention.query.filter_by(
            mentioner_id=mentioner_id,
            mentioned_user_id=mentioned_id,
            item_type=mention_item_type,
            item_id=item_id,
        ).first()

        if existing:
            log.debug(
                f"  중복 멘션: {mentioner_username} -> {mentioned_username}, 건너뜀"
            )
            continue

        # 멘션 생성
        mention = Mention(
            mentioner_id=mentioner_id,
            mentioned_user_id=mentioned_id,
            item_type=mention_item_type,
            item_id=item_id,
            created_at=datetime.now() - timedelta(days=random.randint(0, 30)),
            is_checked=random.choice([True, False]),
        )
        mentions.append(mention)

    if mentions:
        db.session.add_all(mentions)
        db.session.commit()
        log.success(f"  {len(mentions)}개 멘션 생성 완료")

        # 알림 생성
        notifications = []
        for mention in mentions:
            notification = Notification(
                type=NotificationType.MENTION,
                from_user_id=mention.mentioner_id,
                to_user_id=mention.mentioned_user_id,
                item_type=NotificationItemType.MENTION,
                item_id=mention.mention_id,
                created_at=mention.created_at,
                is_checked=mention.is_checked,
                message="회원님을 멘션했습니다.",
            )
            notifications.append(notification)

        if notifications:
            db.session.add_all(notifications)
            db.session.commit()
            log.success(f"  {len(notifications)}개 멘션 알림 생성 완료")
    else:
        log.warning("  생성할 멘션이 없습니다")


def create_mention_api(app, mention_data, username_to_userid, api_url):
    """API 호출로 멘션 생성 (PROD)"""
    import requests

    log = get_logger()
    log.warning("  API 기반 멘션 생성은 아직 구현되지 않았습니다")
    # TODO: POST /mention API 호출 구현


@pytest.mark.no_cleanup
def test_generate_mentions(fixture_app):
    """mention_data.json에서 멘션 데이터를 로드하여 생성"""
    from apps.config.server import db
    from apps.auth.models import User
    from apps.post.models import Post
    from apps.reply.models import Reply

    log = get_logger()

    with fixture_app.app_context():
        log.info(f"\n[6/7] 멘션 생성")

        # 환경 확인
        api_url = fixture_app.config.get("API_BACKEND_URL", "")
        use_test_env = fixture_app.config.get("TESTING", False)

        # 사용자 매핑 생성
        users = User.query.all()
        if not users:
            log.warning("  사용자를 찾을 수 없습니다. gen_user.py를 먼저 실행하세요!")
            pytest.skip("멘션을 생성할 사용자가 없습니다")

        username_to_userid = {user.username: user.user_id for user in users}
        log.debug(f"  {len(users)}명의 사용자 발견")

        # 게시글 매핑 생성 (user_id -> [post_ids])
        posts = Post.query.all()
        if not posts:
            log.warning("  게시글을 찾을 수 없습니다. gen_post.py를 먼저 실행하세요!")
            pytest.skip("멘션을 생성할 게시글이 없습니다")

        post_map = {}
        for post in posts:
            if post.user_id not in post_map:
                post_map[post.user_id] = []
            post_map[post.user_id].append(post.post_id)

        log.debug(f"  {len(posts)}개의 게시글 발견")

        # 댓글 매핑 생성 (post의 user_id -> [reply_ids])
        replies = Reply.query.all()
        if not replies:
            log.warning("  댓글을 찾을 수 없습니다. gen_reply.py를 먼저 실행하세요!")
            pytest.skip("멘션을 생성할 댓글이 없습니다")

        reply_map = {}
        for reply in replies:
            # 댓글이 속한 게시글의 작성자로 매핑
            post = db.session.get(Post, reply.post_id)
            if post:
                if post.user_id not in reply_map:
                    reply_map[post.user_id] = []
                reply_map[post.user_id].append(reply.reply_id)

        log.debug(f"  {len(replies)}개의 댓글 발견")

        # JSON 데이터 로드
        json_path = os.path.join(
            os.path.dirname(__file__), "..", "json", "mention_data.json"
        )
        mention_data = load_mention_data(json_path)

        if not mention_data:
            log.warning("  mention_data.json 파일이 없거나 비어있습니다")
            return

        log.debug(f"  {len(mention_data)}개 멘션 데이터 로드")

        # 환경에 따라 생성 방법 선택
        if use_test_env or not api_url:
            # LOCAL: DB 직접 접근
            log.debug("  LOCAL 환경: DB 직접 접근")
            create_mention_db(
                fixture_app, mention_data, username_to_userid, post_map, reply_map
            )
        else:
            # PROD: API 호출
            log.debug("  PROD 환경: API 호출")
            create_mention_api(fixture_app, mention_data, username_to_userid, api_url)
