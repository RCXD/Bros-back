from ..extensions import db


class Friend(db.Model):
    """
    ✅ 즐겨찾기 친구 관계 테이블 (User 기반)
    - user_id : 즐겨찾기를 설정한 사용자
    - friend_id : 즐겨찾기로 등록된 사용자
    """

    __tablename__ = "friends"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

    # -------------------------------------------------------
    # ✅ relationship 설정 (User와의 자기참조 관계)
    # -------------------------------------------------------
    # user : 즐겨찾기를 한 사람 (나 자신)
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("favorite_friends", lazy="dynamic"),
    )

    # friend : 내가 즐겨찾기로 등록한 친구
    friend = db.relationship(
        "User",
        foreign_keys=[friend_id],
        backref=db.backref("favorited_by", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<Friend user_id={self.user_id}, friend_id={self.friend_id}>"
