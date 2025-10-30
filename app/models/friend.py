from ..extensions import db
from sqlalchemy import event
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

    # -------------------------------------------------------
    # ✅ relationship (User 자기참조)
    # -------------------------------------------------------
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref(
            "favorite_friends",
            lazy="dynamic",
            cascade="all, delete-orphan"
        ),
    )

    friend = db.relationship(
        "User",
        foreign_keys=[friend_id],
        backref=db.backref(
            "favorited_by",
            lazy="dynamic",
            cascade="all, delete-orphan"
        ),
    )

    def __repr__(self):
        return f"<Friend user_id={self.user_id}, friend_id={self.friend_id}>"
