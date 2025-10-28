import enum
from ..extensions import db
from flask_login import UserMixin, login_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from sqlalchemy import func
from models.follow import Follow
from ..encryption import EncryptedString


class OauthType(enum.Enum):
    NONE = "NONE"
    KAKAO = "KAKAO"
    NAVER = "NAVER"
    GOOGLE = "GOOGLE"


class AccountType(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(db.Model, UserMixin):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(EncryptedString(255), unique=True, nullable=False)
    address = db.Column(EncryptedString(255), nullable=False)
    profile_img = db.Column(db.String(255))  # directory
    nickname = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, nullable=True)
    is_expired = db.Column(db.Boolean, nullable=False, default=False)
    oauth_type = db.Column(db.Enum(OauthType), nullable=False, default=OauthType.NONE)
    account_type = db.Column(
        db.Enum(AccountType), nullable=False, default=AccountType.USER
    )
    follower_count = db.Column(db.Integer)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def calculate_follower(self):
        self.follower_count = (
            db.session.query(func.count())
            .select_from(Follow)
            .join(Follow.following_id == User.user_id)
            .scalar()
        )

    posts = db.relationship("Post", backref="author", lazy=True)
    replies = db.relationship("Reply", backref="author", lazy=True)
    images = db.relationship("Image", backref="uploader", lazy=True)
    accident_reports = db.relationship("AccidentReport", backref="reporter", lazy=True)
