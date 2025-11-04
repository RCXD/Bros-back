# models/follow.py
from ..extensions import db

class Follow(db.Model):
    """
     유저 간 팔로우 관계를 나타내는 중간 테이블 (Many-to-Many)
    
    - follower_id : 팔로우 하는 사람 (예: A)
    - following_id : 팔로우 받는 사람 (예: B)
    
    관계:
      A(follower)가 B(following)를 팔로우하면
      Follow(follower_id=A.user_id, following_id=B.user_id) 레코드가 생성됨
    """

    __tablename__ = "follows"

    # ▶ 두 컬럼이 복합 기본키(Primary Key)
    follower_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        primary_key=True
    )
    following_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        primary_key=True
    )

    # 관계 설정
    # follower : 팔로우 하는 유저 (A)
    # following : 팔로우 받는 유저 (B)
    follower = db.relationship(
        "User",
        foreign_keys=[follower_id],
        backref=db.backref("following", lazy="dynamic")  # A.following → A가 팔로우하는 유저 목록
    )

    following = db.relationship(
        "User",
        foreign_keys=[following_id],
        backref=db.backref("followers", lazy="dynamic")  # B.followers → B를 팔로우하는 유저 목록
    )

    def __repr__(self):
        return f"<Follow follower={self.follower_id}, following={self.following_id}>"
