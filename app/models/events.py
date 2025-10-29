from sqlalchemy import event
from ..extensions import db
from ..models.friend import Friend
from ..models.follow import Follow


@event.listens_for(Friend, "before_insert")
def check_follow_before_add(mapper, connection, target):
    """
    ✅ 즐겨찾기 추가 전에
    'user_id(A)'가 'friend_id(B)'를 팔로우 중인지 확인
    """
    follow_exists = connection.execute(
        db.select(Follow).where(
            (Follow.follower_id == target.user_id)
            & (Follow.following_id == target.friend_id)
        )
    ).first()

    if not follow_exists:
        raise ValueError("팔로우 중인 사용자만 즐겨찾기에 추가할 수 있습니다.")


@event.listens_for(Follow, "after_delete")
def remove_friend_on_unfollow(mapper, connection, target):
    """
    ✅ 팔로우가 끊기면 해당 Friend 관계 자동 삭제
    (즉, follower_id → following_id 관계가 없어졌을 때)
    """
    connection.execute(
        db.text(
            """
            DELETE FROM friends
            WHERE user_id = :u AND friend_id = :f
        """
        ),
        {"u": target.follower_id, "f": target.following_id},
    )
