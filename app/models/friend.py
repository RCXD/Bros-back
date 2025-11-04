from ..extensions import db
from sqlalchemy import event, PrimaryKeyConstraint
from ..models.follow import Follow


class Friend(db.Model):
    """
    ✅ 즐겨찾기 친구 관계 테이블
    - 한쪽이 팔로우 중이면 즐겨찾기 등록 가능
    - 등록한 사람 쪽에서 언팔로우 시 자동 삭제
    - 유저 삭제 시 CASCADE
    """

    __tablename__ = "friend"

    # ondelete='CASCADE'로 User 삭제 시 Friend 자동 삭제
    # 복합 기본키
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    friend_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "friend_id", name="pk_friend_user_friend"),
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref(
            "favorite_friends", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    friend = db.relationship(
        "User",
        foreign_keys=[friend_id],
        backref=db.backref(
            "favorited_by", lazy="dynamic", cascade="all, delete-orphan"
        ),
    )

    def __repr__(self):
        return f"<Friend user_id={self.user_id}, friend_id={self.friend_id}>"


@event.listens_for(Friend, "before_insert")
def check_follow_before_add(mapper, connection, target):
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
    connection.execute(
        db.text(
            """
            DELETE FROM friends
            WHERE user_id = :u AND friend_id = :f
        """
        ),
        {"u": target.follower_id, "f": target.following_id},
    )
