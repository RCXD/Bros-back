# ============================
# models/user.py
# ============================
import enum
from ..extensions import db
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from sqlalchemy import func
from ..models.follow import Follow


class OauthType(enum.Enum):
    NONE = "NONE"
    KAKAO = "KAKAO"
    NAVER = "NAVER"
    GOOGLE = "GOOGLE"


class AccountType(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    profile_img = db.Column(db.String(255))  # directory #기본이미지가 들어가므로 nullable=False 추가 필요함
    # profile_img = db.Column(db.String(255), nullable=False, default="static/default_profile.jpg")
    nickname = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, nullable=True, default=datetime.now)
    is_expired = db.Column(db.Boolean, nullable=False, default=False)
    oauth_type = db.Column(db.Enum(OauthType), nullable=False, default=OauthType.NONE)
    account_type = db.Column(
        db.Enum(AccountType), nullable=False, default=AccountType.USER
    )
    follower_count = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def renew_login(self):
        self.last_login = datetime.now()

    # ============================
    # 변경: join 오류 수정
    # calculate_follower에서 BinaryExpression 직접 join 제거
    # 올바른 join: 모델 + 조건
    # ============================
    def calculate_follower(self):
        self.follower_count = (
            db.session.query(func.count())
            .select_from(Follow)
            .join(User, Follow.follower_id == User.user_id)  # 수정: join(User, 조건)
            .filter(Follow.following_id == self.user_id)     # 현재 사용자를 팔로우하는 수
            .scalar()
        )

    posts = db.relationship("Post", backref="author", lazy=True)
    replies = db.relationship("Reply", backref="author", lazy=True)
    histories = db.relationship("History", backref="user", lazy=True)
    accident_reports = db.relationship("AccidentReport", backref="reporter", lazy=True)
